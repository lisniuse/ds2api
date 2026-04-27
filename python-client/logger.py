"""
Session logger — writes one JSON-Lines file per session to the logs/ directory.
Each line is a timestamped event, easy to grep/parse for debugging.
"""

import json
import os
from datetime import datetime

_LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")


class AgentLogger:
    def __init__(self) -> None:
        os.makedirs(_LOG_DIR, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(_LOG_DIR, f"session_{ts}.jsonl")
        self._f = open(self.path, "w", encoding="utf-8")

    # ── internal ──────────────────────────────────────────────────────────────

    def _w(self, event: str, **data) -> None:
        entry = {"ts": datetime.now().isoformat(timespec="milliseconds"), "event": event, **data}
        self._f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        self._f.flush()

    # ── public API ────────────────────────────────────────────────────────────

    def session_start(self, model: str, base_url: str, work_dir: str, args) -> None:
        self._w("session_start", model=model, base_url=base_url, work_dir=work_dir,
                quiet=args.quiet, silent=args.silent, no_stream=args.no_stream,
                max_steps=args.max_steps)

    def task_start(self, task: str) -> None:
        self._w("task_start", task=task)

    def step_start(self, step: int) -> None:
        self._w("step_start", step=step)

    def model_reply(self, step: int, reply: str) -> None:
        self._w("model_reply", step=step, chars=len(reply), reply=reply)

    def code_extracted(self, step: int, code: str) -> None:
        self._w("code_extracted", step=step, lines=len(code.splitlines()), code=code)

    def execution_result(self, step: int, output: str, done: bool, error: str | None = None) -> None:
        self._w("execution_result", step=step, output=output, done=done, error=error)

    def task_complete(self, steps: int) -> None:
        self._w("task_complete", steps=steps)

    def task_interrupted(self) -> None:
        self._w("task_interrupted")

    def task_max_steps(self, max_steps: int) -> None:
        self._w("task_max_steps", max_steps=max_steps)

    def session_end(self) -> None:
        if self._f.closed:
            return
        self._w("session_end")
        self._f.close()
