"""
DS2API Python Agent - Interactive Terminal

Usage:
  python agent.py [options] [task]

Options:
  -q, --quiet       Hide code panel; show only a one-line summary per step
  -s, --silent      Hide both streaming output and code panel (only show execution result)
  --no-stream       Don't stream model tokens live; wait and print all at once
  --model MODEL     Override model from .env
  --max-steps N     Max steps per task (default from .env / config)
"""

import sys
import io
import argparse
import subprocess
import httpx
import atexit

# Force UTF-8 on Windows for all I/O
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")
    sys.stdin  = io.TextIOWrapper(sys.stdin.buffer,  encoding="utf-8", errors="replace")

from openai import OpenAI

import config
from extractor import extract_code
from executor import execute
from logger import AgentLogger

from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.history import InMemoryHistory

from rich.console import Console
from rich.syntax import Syntax
from rich.panel import Panel
from rich.rule import Rule
from rich.text import Text
from rich.theme import Theme

# ── theme ─────────────────────────────────────────────────────────────────────

THEME = Theme({
    "step":   "bold cyan",
    "code":   "bold yellow",
    "result": "bold green",
    "error":  "bold red",
    "done":   "bold green",
    "prompt": "bold white",
})

console = Console(theme=THEME, highlight=False)


# ── client ────────────────────────────────────────────────────────────────────

def build_client(model: str | None = None) -> tuple[OpenAI, str]:
    effective_model = model or config.MODEL
    client = OpenAI(
        base_url=config.BASE_URL,
        api_key=config.API_KEY,
        http_client=httpx.Client(trust_env=False),
    )
    return client, effective_model


# ── chat helpers ──────────────────────────────────────────────────────────────

def chat_stream(client: OpenAI, model: str, messages: list[dict], silent: bool) -> str:
    stream = client.chat.completions.create(model=model, messages=messages, stream=True)
    chunks = []
    if not silent:
        console.print()
    for chunk in stream:
        delta = chunk.choices[0].delta.content
        if delta:
            chunks.append(delta)
            if not silent:
                console.print(delta, end="", style="dim cyan", markup=False)
    if not silent:
        console.print()
    return "".join(chunks)


def chat_wait(client: OpenAI, model: str, messages: list[dict]) -> str:
    with console.status("[dim]waiting for model...[/dim]", spinner="dots"):
        resp = client.chat.completions.create(model=model, messages=messages, stream=False)
    return resp.choices[0].message.content or ""


# ── helpers ───────────────────────────────────────────────────────────────────

def code_summary(code: str, max_len: int = 72) -> str:
    first = next((l for l in code.splitlines() if l.strip()), "")
    lines = len(code.splitlines())
    summary = first if len(first) <= max_len else first[:max_len - 1] + "…"
    return f"{summary}  [dim]({lines} lines)[/dim]"



# ── agent loop ────────────────────────────────────────────────────────────────

def run_task(
    client: OpenAI,
    model: str,
    task: str,
    args: argparse.Namespace,
    messages: list[dict],
    log: AgentLogger,
) -> None:
    messages.append({"role": "user", "content": task})
    log.task_start(task)

    quiet     = args.quiet or args.silent
    silent    = args.silent
    stream    = not args.no_stream
    max_steps = args.max_steps

    step = 0
    while True:
        step += 1
        console.print(Rule(f"[step]Step {step}[/step]", style="cyan"))
        log.step_start(step)

        if step > max_steps:
            console.print(f"[error]✗ Reached max steps ({max_steps}), stopping.[/error]\n")
            log.task_max_steps(max_steps)
            messages.pop()
            break

        # ── call model ──
        if stream:
            if quiet:
                with console.status("[dim]thinking...[/dim]", spinner="dots"):
                    reply = chat_stream(client, model, messages, silent=True)
            else:
                console.print("[dim]▸ model[/dim]", end="")
                reply = chat_stream(client, model, messages, silent=False)
        else:
            reply = chat_wait(client, model, messages)

        log.model_reply(step, reply)

        # ── done signal check ──
        if reply.strip() == "done":
            console.print(f"\n[done]✓ Task completed in {step} step(s)[/done]\n")
            log.task_complete(step)
            messages.append({"role": "assistant", "content": reply})
            break

        # ── extract code ──
        code = extract_code(reply)
        log.code_extracted(step, code)

        if quiet:
            console.print(f"[code]▸ code[/code]  {code_summary(code)}")
        else:
            console.print()
            console.print(Panel(
                Syntax(code, "python", theme="monokai", line_numbers=True),
                title="[code]Code to execute[/code]",
                border_style="yellow",
            ))

        # ── execute ──
        exec_error = None
        try:
            with console.status("[dim]executing...[/dim]", spinner="point"):
                output = execute(code)
        except subprocess.TimeoutExpired:
            output = f"[timeout] execution exceeded {config.EXEC_TIMEOUT}s"
            exec_error = "TimeoutExpired"
        except Exception as e:
            output = f"[error] {e}"
            exec_error = str(e)

        log.execution_result(step, output, False, exec_error)

        is_error  = output.startswith(("[error]", "[timeout]", "[stderr]"))
        border    = "red" if is_error else "white"
        title_tag = "error" if is_error else "result"
        if output.strip():
            console.print(Panel(
                Text(output),
                title=f"[{title_tag}]Output[/{title_tag}]",
                border_style=border,
            ))

        messages.append({"role": "assistant", "content": reply})
        messages.append({"role": "user", "content": f"执行结果：\n{output}"})


# ── REPL ──────────────────────────────────────────────────────────────────────

BANNER = """[bold cyan]
  ██████  ███████ ██████   █████  ██████  ██
  ██   ██ ██      ╚════██ ██   ██ ██   ██ ██
  ██   ██ ███████  █████  ███████ ██████  ██
  ██   ██      ██ ██      ██   ██ ██      ██
  ██████  ███████ ███████ ██   ██ ██      ██
[/bold cyan]
[dim]  DeepSeek Python Agent  ·  model: {model}  ·  {url}[/dim]
[dim]  log: {log}[/dim]
[dim]  Enter 发送，↑↓ 翻历史。Ctrl+C 取消输入，Ctrl+D / "exit" 退出。[/dim]
"""


def _read_input(history: InMemoryHistory) -> str:
    try:
        return pt_prompt("> ", history=history)
    except Exception as e:
        if "NoConsoleScreenBufferError" in type(e).__name__ or "xterm" in str(e).lower():
            return input("> ")
        raise


def repl(client: OpenAI, model: str, args: argparse.Namespace, messages: list[dict], log: AgentLogger) -> None:
    console.print(BANNER.format(model=model, url=config.BASE_URL, log=log.path))
    history = InMemoryHistory()
    while True:
        try:
            task = _read_input(history).strip()
        except KeyboardInterrupt:
            continue          # Ctrl+C cancels current input, show prompt again
        except EOFError:
            console.print("\n[dim]Bye.[/dim]")
            log.session_end()
            sys.exit(0)

        if not task:
            continue
        if task.lower() in {"exit", "quit", "q"}:
            console.print("[dim]Bye.[/dim]")
            log.session_end()
            sys.exit(0)

        try:
            run_task(client, model, task, args, messages, log)
        except KeyboardInterrupt:
            if messages and messages[-1]["role"] == "user":
                messages.pop()
            log.task_interrupted()
            console.print("\n[dim]Task interrupted. Enter a new task or type exit.[/dim]\n")


# ── entry point ───────────────────────────────────────────────────────────────

def parse_args() -> tuple[argparse.Namespace, str | None]:
    parser = argparse.ArgumentParser(
        prog="agent",
        description="DS2API Python Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("task",          nargs="*",                              help="Task to run (omit for interactive mode)")
    parser.add_argument("-q", "--quiet", action="store_true",                    help="Hide code panel, show one-line summary")
    parser.add_argument("-s", "--silent",action="store_true",                    help="Hide code panel and model stream")
    parser.add_argument("--no-stream",   action="store_true",                    help="Wait for full reply instead of streaming")
    parser.add_argument("--model",       default=None,                           help="Override model (e.g. deepseek-v4-pro)")
    parser.add_argument("--max-steps",   default=config.MAX_STEPS, type=int,    help=f"Max steps per task (default: {config.MAX_STEPS})")
    ns = parser.parse_args()
    task = " ".join(ns.task) if ns.task else None
    return ns, task


def main() -> None:
    args, task = parse_args()
    client, model = build_client(args.model)

    log = AgentLogger()
    atexit.register(log.session_end)  # flush on unexpected exit
    log.session_start(model, config.BASE_URL, config.WORK_DIR, args)

    messages: list[dict] = [{"role": "system", "content": config.SYSTEM_PROMPT}]

    if task:
        console.print(BANNER.format(model=model, url=config.BASE_URL, log=log.path))
        try:
            run_task(client, model, task, args, messages, log)
        except KeyboardInterrupt:
            log.task_interrupted()
            console.print("\n[dim]Interrupted.[/dim]")

    repl(client, model, args, messages, log)


if __name__ == "__main__":
    main()
