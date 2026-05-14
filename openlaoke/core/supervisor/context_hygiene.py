"""Progressive file writing strategy for context hygiene.

Inspired by Feynman's context management rules:
- Write findings progressively, don't accumulate in memory
- Extract and discard large content immediately
- Return lightweight references instead of full content
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass
class WriteBuffer:
    """Buffer for progressive file writing."""

    file_path: str
    _buffer: list[str] = field(default_factory=list)
    _flush_count: int = 0
    _total_written: int = 0
    flush_threshold: int = 500

    def add(self, content: str) -> None:
        self._buffer.append(content)
        if len(self._buffer) >= self.flush_threshold:
            self.flush()

    def flush(self) -> None:
        if not self._buffer:
            return

        os.makedirs(os.path.dirname(self.file_path), exist_ok=True)

        mode = "a" if self._flush_count > 0 or os.path.exists(self.file_path) else "w"
        with open(self.file_path, mode, encoding="utf-8") as f:
            for chunk in self._buffer:
                f.write(chunk)
                self._total_written += len(chunk)

        self._buffer.clear()
        self._flush_count += 1

    def close(self) -> None:
        self.flush()

    @property
    def stats(self) -> dict:
        return {
            "file": self.file_path,
            "flushes": self._flush_count,
            "bytes_written": self._total_written,
            "buffer_size": len(self._buffer),
        }


def extract_key_quotes(content: str, max_chars: int = 500) -> str:
    """Extract key quotes from large content, discard the rest."""
    lines = content.split("\n")
    quotes = []
    current_len = 0

    for line in lines:
        line = line.strip()
        if len(line) > 50 and ("evidence" in line.lower() or "result" in line.lower()):
            if current_len + len(line) < max_chars:
                quotes.append(line)
                current_len += len(line)
            else:
                break

    return "\n".join(quotes) if quotes else content[:max_chars]
