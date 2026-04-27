import os
import subprocess
import sys
from config import EXEC_TIMEOUT, WORK_DIR

# Directory containing tools.py so the agent can `import tools`
_TOOLS_DIR = os.path.dirname(os.path.abspath(__file__))

# Injected at the top of every code block so `import tools` always works
_PRELUDE = f"import sys; sys.path.insert(0, {_TOOLS_DIR!r})\n"


def execute(code: str) -> str:
    """
    Execute Python code in a subprocess.
    Returns (output, done) where done=True only when '[done]' is in stdout
    AND the process exited cleanly (returncode == 0).
    """
    result = subprocess.run(
        [sys.executable, "-c", _PRELUDE + code],
        capture_output=True,
        text=True,
        timeout=EXEC_TIMEOUT,
        cwd=WORK_DIR,
    )

    stdout = result.stdout
    stderr = result.stderr.strip()

    parts = []
    if stdout:
        parts.append(stdout)
    if stderr:
        parts.append(f"[stderr]\n{stderr}")

    output = "\n".join(parts).strip() or "(no output)"

    return output
