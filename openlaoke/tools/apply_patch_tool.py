"""ApplyPatch tool - multi-file patches, applied all-or-nothing.

Two accepted formats, because both are what models actually emit:

* the Codex envelope (``*** Begin Patch`` / ``*** Add File:`` / ``*** Update File:``
  with ``@@`` hunks / ``*** Delete File:``), and
* a unified diff (``--- a/x`` / ``+++ b/x`` / ``@@ -1,3 +1,4 @@``).

Every file is checked in memory first and written only after every hunk in the
whole patch has matched.  A patch that fails halfway is worse than one that
fails immediately: the model then cannot tell which half landed.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock

MAX_PATCH_BYTES = 2_000_000
_HUNK_HEADER = re.compile(r"^@@\s*-(\d+)(?:,(\d+))?\s*\+(\d+)(?:,(\d+))?\s*@@")


class PatchError(Exception):
    """A patch that cannot be applied as written."""


@dataclass
class Hunk:
    old_start: int
    old_lines: list[str]
    new_lines: list[str]


@dataclass
class FilePatch:
    path: str
    kind: str  # "add" | "update" | "delete"
    hunks: list[Hunk] = field(default_factory=list)
    content: list[str] = field(default_factory=list)


def _strip_newline(line: str) -> str:
    return line[:-1] if line.endswith("\n") else line


def parse_codex(text: str) -> list[FilePatch]:
    """Parse the ``*** Begin Patch`` envelope."""
    lines = [_strip_newline(line) for line in text.splitlines(keepends=True)]
    patches: list[FilePatch] = []
    current: FilePatch | None = None
    in_hunk = False
    hunk_old: list[str] = []
    hunk_new: list[str] = []
    hunk_start = 0
    seen_begin = False

    def flush_hunk() -> None:
        nonlocal hunk_old, hunk_new, in_hunk
        if current is not None and in_hunk and (hunk_old or hunk_new):
            current.hunks.append(Hunk(hunk_start, list(hunk_old), list(hunk_new)))
        hunk_old, hunk_new, in_hunk = [], [], False

    for line in lines:
        if line.startswith("*** Begin Patch"):
            seen_begin = True
            continue
        if line.startswith("*** End Patch"):
            flush_hunk()
            current = None
            continue
        if line.startswith("*** Add File:"):
            flush_hunk()
            current = FilePatch(path=line.split(":", 1)[1].strip(), kind="add")
            patches.append(current)
            continue
        if line.startswith("*** Delete File:"):
            flush_hunk()
            current = FilePatch(path=line.split(":", 1)[1].strip(), kind="delete")
            patches.append(current)
            continue
        if line.startswith("*** Update File:"):
            flush_hunk()
            current = FilePatch(path=line.split(":", 1)[1].strip(), kind="update")
            patches.append(current)
            continue
        if line.startswith("*** Move to:"):
            continue
        if current is None:
            if line.strip():
                raise PatchError(f"unexpected line outside a file section: {line[:80]}")
            continue

        if line.startswith("@@"):
            flush_hunk()
            in_hunk = True
            hunk_start = 0
            header = _HUNK_HEADER.match(line)
            if header:
                hunk_start = int(header.group(1))
            continue

        if current.kind == "add":
            if line.startswith("+"):
                current.content.append(line[1:])
            elif line == "":
                current.content.append("")
            continue

        if current.kind == "update":
            if line.startswith("+"):
                hunk_new.append(line[1:])
            elif line.startswith("-"):
                hunk_old.append(line[1:])
            elif line.startswith(" ") or line == "":
                hunk_old.append(line[1:] if line.startswith(" ") else "")
                hunk_new.append(line[1:] if line.startswith(" ") else "")
            continue

    flush_hunk()
    if not seen_begin:
        raise PatchError("missing '*** Begin Patch'")
    if not patches:
        raise PatchError("patch contains no file sections")
    return patches


def _normalise_diff_path(path: str) -> str:
    """Drop the ``a/`` or ``b/`` prefix that diff tools prepend."""
    if path.startswith(("a/", "b/")) and len(path) > 2:
        return path[2:]
    return path


def parse_unified(text: str) -> list[FilePatch]:
    """Parse a plain unified diff."""
    patches: list[FilePatch] = []
    current: FilePatch | None = None
    hunk: Hunk | None = None
    old_path = ""

    for raw in text.splitlines():
        if raw.startswith("--- "):
            old_path = raw[4:].strip().split("\t")[0]
            if old_path in ("/dev/null",):
                old_path = ""
            continue
        if raw.startswith("+++ "):
            new_path = raw[4:].strip().split("\t")[0]
            raw_path = new_path if new_path != "/dev/null" else old_path
            path = _normalise_diff_path(raw_path)
            old_path = _normalise_diff_path(old_path)
            kind = "add" if not old_path else ("delete" if new_path == "/dev/null" else "update")
            current = FilePatch(path=path, kind=kind)
            patches.append(current)
            hunk = None
            continue
        if current is None:
            continue
        if raw.startswith("@@"):
            header = _HUNK_HEADER.match(raw)
            if not header:
                raise PatchError(f"malformed hunk header: {raw[:80]}")
            hunk = Hunk(int(header.group(1)), [], [])
            current.hunks.append(hunk)
            continue
        if hunk is None:
            continue
        if raw.startswith("+"):
            hunk.new_lines.append(raw[1:])
        elif raw.startswith("-"):
            hunk.old_lines.append(raw[1:])
        elif raw.startswith(" ") or raw == "":
            payload = raw[1:] if raw.startswith(" ") else ""
            hunk.old_lines.append(payload)
            hunk.new_lines.append(payload)

    if not patches:
        raise PatchError("no file sections found in the diff")
    for patch in patches:
        if patch.kind == "update" and not patch.hunks:
            raise PatchError(f"{patch.path}: no hunks")
        if patch.kind == "add":
            # A unified diff expresses a new file as one hunk of additions.
            patch.content = [line for hunk in patch.hunks for line in hunk.new_lines]
    return patches


def _apply_hunks(original: list[str], hunks: list[Hunk], path: str) -> list[str]:
    result = list(original)
    cursor = 0
    for hunk in hunks:
        found_at = -1
        search_from = cursor
        while search_from <= len(result):
            if result[search_from : search_from + len(hunk.old_lines)] == hunk.old_lines:
                found_at = search_from
                break
            search_from += 1
        if found_at < 0:
            preview = " | ".join(hunk.old_lines[:4])
            raise PatchError(f"{path}: hunk does not match (first lines: {preview!r})")
        result[found_at : found_at + len(hunk.old_lines)] = hunk.new_lines
        cursor = found_at + len(hunk.new_lines)
    return result


class ApplyPatchInput(BaseModel):
    patch: str = Field(
        description=(
            "The patch text: either a '*** Begin Patch ... *** End Patch' envelope or a "
            "unified diff with ---/+++/@@ headers"
        )
    )


class ApplyPatchTool(Tool):
    """Apply a multi-file patch atomically."""

    name = "ApplyPatch"
    description = (
        "Apply one patch touching several files at once, either in the '*** Begin Patch' "
        "envelope (*** Add File / *** Update File with @@ hunks / *** Delete File) or as a "
        "unified diff. Every hunk is checked before anything is written, so a patch either "
        "applies completely or not at all. Use Edit for a single substitution."
    )
    input_schema = ApplyPatchInput
    is_read_only = False
    is_destructive = True
    is_concurrency_safe = False
    requires_approval = True

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        text = str(kwargs.get("patch") or "")
        if not text.strip():
            return self._error(ctx, "Error: patch is required")
        if len(text.encode("utf-8")) > MAX_PATCH_BYTES:
            return self._error(ctx, f"Error: patch is larger than {MAX_PATCH_BYTES} bytes")

        from openlaoke.utils.path_safety import resolve_path, validate_path

        cwd = ctx.app_state.get_cwd()
        try:
            patches = parse_codex(text) if "*** Begin Patch" in text else parse_unified(text)
        except PatchError as exc:
            return self._error(ctx, f"Patch rejected: {exc}")

        staged: list[tuple[str, str, str, bool, bool]] = []
        for patch in patches:
            if not patch.path:
                return self._error(ctx, "Patch rejected: a section has no path")
            absolute = resolve_path(patch.path, cwd)
            path_error = validate_path(absolute, cwd)
            if path_error:
                return self._error(ctx, path_error)

            exists = os.path.exists(absolute)
            if patch.kind == "add" and exists:
                return self._error(ctx, f"Patch rejected: {patch.path} already exists")
            if patch.kind in ("update", "delete") and not exists:
                return self._error(ctx, f"Patch rejected: {patch.path} does not exist")

            before = ""
            if exists:
                try:
                    with open(absolute, encoding="utf-8", errors="replace") as handle:
                        before = handle.read()
                except OSError as exc:
                    return self._error(ctx, f"Patch rejected: cannot read {patch.path}: {exc}")

            if patch.kind == "add":
                after = "".join(line + "\n" for line in patch.content)
            elif patch.kind == "delete":
                after = ""
            else:
                original_lines = before.splitlines()
                try:
                    updated = _apply_hunks(original_lines, patch.hunks, patch.path)
                except PatchError as exc:
                    return self._error(ctx, f"Patch rejected: {exc}")
                after = "".join(line + "\n" for line in updated)
                if before.endswith("\n") is False and original_lines:
                    after = after.rstrip("\n")
            staged.append((absolute, before, after, patch.kind == "add", patch.kind == "delete"))

        from openlaoke.core.edit_stats import record_edit

        touched: list[str] = []
        for absolute, before, after, created, deleted in staged:
            try:
                if deleted:
                    os.remove(absolute)
                else:
                    os.makedirs(os.path.dirname(absolute) or ".", exist_ok=True)
                    with open(absolute, "w", encoding="utf-8") as handle:
                        handle.write(after)
            except OSError as exc:
                return self._error(ctx, f"Patch failed while writing {absolute}: {exc}")
            record_edit(ctx.app_state, absolute, before, after, created)
            touched.append(os.path.relpath(absolute, cwd))

        summary = "\n".join(f"  {path}" for path in touched)
        kinds = {
            "added" if created else ("deleted" if deleted else "updated")
            for _absolute, _before, _after, created, deleted in staged
        }
        kind_note = ", ".join(sorted(kinds))
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Patch applied: {len(touched)} file(s) {kind_note}\n{summary}",
        )

    @staticmethod
    def _error(ctx: ToolContext, message: str) -> ToolResultBlock:
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=message, is_error=True)


def register(registry: ToolRegistry) -> None:
    registry.register(ApplyPatchTool())
