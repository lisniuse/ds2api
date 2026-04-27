import re


_FENCE_RE = re.compile(r"```(?:python)?\s*\n(.*?)```", re.DOTALL)


def extract_code(text: str) -> str:
    """
    Extract Python code from LLM response.
    Handles both fenced code blocks (```python ... ```) and raw code output.
    Multiple blocks are concatenated in order.
    """
    blocks = _FENCE_RE.findall(text)
    if blocks:
        return "\n\n".join(b.strip() for b in blocks)

    # No fences — assume the entire response is code
    return text.strip()
