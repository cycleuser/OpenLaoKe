"""Repair escape sequences that small models double-escape in tool arguments.

Small local models frequently emit file content with an extra escaping layer,
so a JSON string such as ``"line1\\nline2"`` decodes to the literal characters
``line1\\nline2`` (backslash + n) instead of two lines. This module detects that
shape and turns the literal escapes back into real control characters.

The heuristic is deliberately narrow: it only fires when the string has *no*
real newlines but does contain at least two literal ``\\n`` sequences, and it
backs off when the text contains other intentional escapes (``\\\\`` or
``\\"``).
"""

from __future__ import annotations


def normalize_model_escapes(text: str) -> str:
    """Turn literal ``\\n``/``\\r``/``\\t`` back into real characters.

    Returns the text unchanged when it already has real newlines or shows no
    sign of double escaping.
    """
    if not text:
        return text
    if "\n" in text or "\r" in text:
        return text
    # At least two literal \n: that looks like a document, not a single escape
    # inside a one-line code snippet.
    if text.count("\\n") < 2:
        return text
    # Other escapes present -> the writer probably meant them literally.
    if "\\\\" in text or '\\"' in text:
        return text
    return (
        text.replace("\\r\\n", "\n").replace("\\n", "\n").replace("\\r", "\n").replace("\\t", "\t")
    )
