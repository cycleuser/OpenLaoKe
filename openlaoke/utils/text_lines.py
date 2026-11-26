"""Line counting shared by the file tools.

A file's line count is reported back to the model ("Created x.py (12 lines)"),
so it should match what a person would say. ``str.count("\\n") + 1`` does not: it
turns the trailing newline that most files end with into a phantom extra line.
"""

from __future__ import annotations


def count_lines(text: str) -> int:
    """Number of lines in *text*, not counting the newline that ends the last one."""
    if not text:
        return 0
    lines = text.count("\n")
    if not text.endswith("\n"):
        lines += 1
    return lines
