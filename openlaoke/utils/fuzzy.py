"""Fuzzy matching for edits that are right except for whitespace.

A model that reproduces a block correctly but re-indents it, or leaves trailing
spaces on two lines, currently gets "text not found" and burns a turn guessing.
Three increasingly generous comparisons cover almost every real case:

1. exact,
2. line-wise, ignoring trailing whitespace only,
3. whitespace-normalised (any run of spaces, tabs and newlines is one space).

Nothing here is semantic: a changed word never matches. The caller is told which
step succeeded so it can say so in the tool result instead of pretending the
edit was exact.
"""

from __future__ import annotations

from dataclasses import dataclass

MODE_EXACT = "exact"
MODE_TRAILING = "trailing-whitespace-insensitive"
MODE_NORMALISED = "whitespace-normalised"


@dataclass(frozen=True)
class FuzzyMatch:
    start: int
    end: int
    mode: str


def find_fuzzy(haystack: str, needle: str) -> FuzzyMatch | None:
    """Locate ``needle`` in ``haystack``, tolerating whitespace differences."""
    if not needle:
        return None

    index = haystack.find(needle)
    if index >= 0:
        return FuzzyMatch(index, index + len(needle), MODE_EXACT)

    trailing = _match_ignoring_trailing(haystack, needle)
    if trailing is not None:
        return trailing

    return _match_normalised(haystack, needle)


def _match_ignoring_trailing(haystack: str, needle: str) -> FuzzyMatch | None:
    haystack_lines = haystack.splitlines(keepends=True)
    needle_lines = needle.splitlines()
    if not needle_lines:
        return None

    trimmed_needle = [line.rstrip() for line in needle_lines]
    width = len(trimmed_needle)

    offsets: list[int] = []
    cursor = 0
    for line in haystack_lines:
        offsets.append(cursor)
        cursor += len(line)

    for start in range(0, len(haystack_lines) - width + 1):
        window = haystack_lines[start : start + width]
        if [line.rstrip() for line in window] != trimmed_needle:
            continue
        begin = offsets[start]
        end = offsets[start + width - 1] + len(window[-1])
        # Trim the newline the window may have carried, so the replacement keeps
        # the surrounding line structure unchanged.
        while end > begin and haystack[end - 1] in "\r\n":
            end -= 1
        return FuzzyMatch(begin, end, MODE_TRAILING)
    return None


def _match_normalised(haystack: str, needle: str) -> FuzzyMatch | None:
    normalised, origin = _normalise(haystack)
    wanted, _ = _normalise(needle)
    wanted = wanted.strip()
    if not wanted:
        return None

    index = normalised.find(wanted)
    if index < 0:
        return None
    start = origin[index]
    last = index + len(wanted) - 1
    end = origin[last] + 1
    return FuzzyMatch(start, end, MODE_NORMALISED)


def _normalise(text: str) -> tuple[str, list[int]]:
    """Collapse whitespace and remember where each kept character came from."""
    parts: list[str] = []
    origin: list[int] = []
    in_space = False
    for position, char in enumerate(text):
        if char.isspace():
            if not in_space:
                parts.append(" ")
                origin.append(position)
                in_space = True
            continue
        parts.append(char)
        origin.append(position)
        in_space = False
    return "".join(parts), origin
