"""
Built-in utilities available to the agent via `import tools`.
The executor automatically adds this module to sys.path.
"""

import os
import subprocess
import shutil


def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def write_file(path: str, content: str) -> None:
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            if f.read() == content:
                print(f"[tools] skip {path} (unchanged)")
                return
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[tools] wrote {path} ({len(content)} chars)")


def append_file(path: str, content: str) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(content)
    print(f"[tools] appended {path} ({len(content)} chars)")


def patch_file(path: str, old: str, new: str, count: int = 1) -> int:
    """Replace `old` with `new` in file. Returns number of replacements made."""
    text = read_file(path)
    updated = text.replace(old, new, count)
    n = text.count(old) if count < 0 else min(text.count(old), count)
    if n == 0:
        print(f"[tools] patch_file: pattern not found in {path}")
        return 0
    write_file(path, updated)
    print(f"[tools] patched {path} ({n} replacement(s))")
    return n


def delete_file(path: str) -> None:
    os.remove(path)
    print(f"[tools] deleted {path}")


def make_dirs(path: str) -> None:
    os.makedirs(path, exist_ok=True)
    print(f"[tools] created dirs {path}")


def list_dir(path: str = ".") -> list[str]:
    return os.listdir(path)


def file_exists(path: str) -> bool:
    return os.path.exists(path)


def run_shell(cmd: str, timeout: int = 30) -> tuple[str, str, int]:
    """Run a shell command. Returns (stdout, stderr, returncode)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, timeout=timeout
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print("[stderr]", result.stderr, end="")
    return result.stdout, result.stderr, result.returncode
