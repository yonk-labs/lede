"""Text cleaners: clean_text (markdown + filler + boilerplate) and strip_think
(reasoning-model <think>...</think> blocks).

Both functions are deterministic and stdlib-only.
"""
import re

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks and trim surrounding whitespace.

    Mirrors strip_think(text) from extractive_functions.sql.
    """
    if text is None:
        return ""
    return _THINK_RE.sub("", text).strip()
