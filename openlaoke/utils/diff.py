"""Line-by-line unified diff generator.

Port of sekrun's lib/diff.js — pure LCS-based diff without external deps.
"""

from __future__ import annotations


def _lcs_length(a: list[str], b: list[str]) -> list[int]:
    """Compute LCS length using two-row DP (Hunt–Szymanski style)."""
    m, n = len(a), len(b)
    prev = [0] * (n + 1)
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if a[i - 1] == b[j - 1]:
                curr[j] = prev[j - 1] + 1
            else:
                curr[j] = prev[j] if prev[j] > curr[j - 1] else curr[j - 1]
        prev, curr = curr, prev
    return prev


def _backtrack(
    a: list[str], b: list[str], i: int, j: int, c: list[int]
) -> list[dict]:
    if i > 0 and j > 0 and a[i - 1] == b[j - 1]:
        ops = _backtrack(a, b, i - 1, j - 1, c)
        ops.append({"op": "eq", "line": a[i - 1]})
        return ops
    if j > 0 and (i == 0 or c[j] == c[j - 1]):
        ops = _backtrack(a, b, i, j - 1, c)
        ops.append({"op": "ins", "line": b[j - 1]})
        return ops
    if i > 0:
        ops = _backtrack(a, b, i - 1, j, c)
        ops.append({"op": "del", "line": a[i - 1]})
        return ops
    return []


def _compute_ops(old_lines: list[str], new_lines: list[str]) -> list[dict]:
    if not old_lines:
        return [{"op": "ins", "line": l} for l in new_lines]
    if not new_lines:
        return [{"op": "del", "line": l} for l in old_lines]
    c = _lcs_length(old_lines, new_lines)
    return _backtrack(old_lines, new_lines, len(old_lines), len(new_lines), c)


def _build_hunks(ops: list[dict]) -> list[list[dict]]:
    """Group ops into hunks with up to 3 lines of surrounding context."""
    hunks: list[list[dict]] = []
    i = 0
    while i < len(ops):
        if ops[i]["op"] == "eq":
            i += 1
            continue

        # Capture up to 3 preceding eq lines
        before: list[dict] = []
        lookback = i - 1
        while lookback >= 0 and ops[lookback]["op"] == "eq" and len(before) < 3:
            before.insert(0, ops[lookback])
            lookback -= 1

        # Collect the change block (all consecutive non-eq ops)
        change: list[dict] = []
        while i < len(ops) and ops[i]["op"] != "eq":
            change.append(ops[i])
            i += 1

        # Collect up to 3 following eq lines
        after: list[dict] = []
        while i < len(ops) and ops[i]["op"] == "eq" and len(after) < 3:
            after.append(ops[i])
            i += 1

        hunks.append([*before, *change, *after])

    return hunks


def _format_hunks(hunks: list[list[dict]]) -> str:
    """Format hunks into unified diff output."""
    if not hunks:
        return ""

    # Pre-compute old/new line positions for every op in the original sequence
    # First, we need to reconstruct the full positions by walking through all ops
    out: list[str] = []

    for hunk in hunks:
        # Compute positions for this hunk's ops by simulating from scratch
        old_pos: list[int] = []
        new_pos: list[int] = []
        ol, nl = 0, 0
        for op in hunk:
            old_pos.append(ol)
            new_pos.append(nl)
            if op["op"] in ("eq", "del"):
                ol += 1
            if op["op"] in ("eq", "ins"):
                nl += 1

        hdr_old = old_pos[0] + 1
        hdr_new = new_pos[0] + 1

        oc = sum(1 for op in hunk if op["op"] in ("eq", "del"))
        nc = sum(1 for op in hunk if op["op"] in ("eq", "ins"))

        out.append(f"@@ -{hdr_old},{oc} +{hdr_new},{nc} @@")
        for op in hunk:
            if op["op"] == "eq":
                out.append(f" {op['line']}")
            elif op["op"] == "del":
                out.append(f"-{op['line']}")
            else:
                out.append(f"+{op['line']}")

    return "\n".join(out)


def diff_lines(
    file_path: str, old_content: str, new_content: str, file_existed: bool
) -> str:
    """Generate a unified diff string between old and new file content.

    Args:
        file_path: Display path for the file (included in output).
        old_content: Previous file content (empty string for new files).
        new_content: New file content.
        file_existed: Whether the file existed before this operation.

    Returns:
        A unified-diff string suitable for appending to tool results.
    """
    old_lines = old_content.split("\n") if file_existed else []
    new_lines = new_content.split("\n")

    # Strip trailing empty line from split
    if old_lines and old_lines[-1] == "":
        old_lines.pop()
    if new_lines and new_lines[-1] == "":
        new_lines.pop()

    if not file_existed and not new_lines:
        return "(empty new file)"
    if file_existed and old_content == new_content:
        return "(no changes)"

    ops = _compute_ops(old_lines, new_lines)
    hunks = _build_hunks(ops)
    diff_text = _format_hunks(hunks)

    if file_existed:
        return diff_text
    return f"(new file)\n{diff_text}"
