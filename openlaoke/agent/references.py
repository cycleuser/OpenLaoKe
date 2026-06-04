"""@-reference resolver for file and directory injection.

Resolves ``@path/to/file`` and ``@dir/`` to inline content blocks
appended to the user message. MCP ``@server:uri`` references are handled
separately by the MCP client.

Usage from prompt preprocessing::

    from openlaoke.agent.references import resolve_references
    user_text = resolve_references(user_text, cwd=".")
"""

from __future__ import annotations

import os
import re
from pathlib import Path

_REF_RE = re.compile(r"(?<!\w)@([^\s,;:]+)(?!\w)")


def resolve_references(text: str, cwd: str = ".", max_chars: int = 4000) -> str:
    """Replace ``@path`` references in text with file/directory content.

    - ``@path/to/file`` → inline file content (capped at max_chars)
    - ``@path/to/dir/`` → directory listing
    - ``@server:uri`` → left unresolved (handled by MCP layer)
    - ``@mention`` where path doesn't exist → left as-is
    """
    if "@" not in text:
        return text

    def _replace(match: re.Match[str]) -> str:
        ref = match.group(1)
        if ":" in ref and not ref.startswith((".", "/", "~")):
            return match.group(0)  # MCP resource, skip

        path = Path(os.path.expanduser(ref))
        if not path.is_absolute():
            path = Path(cwd) / ref
        path = path.resolve()

        if path.is_file():
            try:
                body = path.read_text(encoding="utf-8", errors="replace")
                if len(body) > max_chars:
                    body = body[:max_chars] + f"\n\n... (truncated, {len(body)} bytes total)"
                return f"[Content of {path}]\n\n{body}\n[/Content]"
            except OSError:
                return match.group(0)
        elif path.is_dir():
            try:
                entries = sorted(os.listdir(path))
                dirs = [e + "/" for e in entries if os.path.isdir(os.path.join(path, e))]
                files = [e for e in entries if not os.path.isdir(os.path.join(path, e))]
                listing = "\n".join(dirs + files)
                return f"[Directory {path}]\n\n{listing}\n[/Directory]"
            except OSError:
                return match.group(0)
        return match.group(0)  # doesn't exist, leave as text

    return _REF_RE.sub(_replace, text)
