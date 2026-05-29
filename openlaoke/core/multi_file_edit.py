"""Multi-file edit coordination.

When 3+ files are edited in a single turn, injects a coordination header
to prevent small models from forgetting files during multi-file work.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MultiFileEditCoordinator:
    min_files_for_header: int = 3
    _edited_files_this_turn: list[str] = field(default_factory=list)
    _header_injected: bool = False
    _enabled: bool = True

    def track_edit(self, file_path: str) -> None:
        if file_path not in self._edited_files_this_turn:
            self._edited_files_this_turn.append(file_path)

    def should_inject_header(self) -> bool:
        if not self._enabled:
            return False
        if self._header_injected:
            return False
        return len(self._edited_files_this_turn) >= self.min_files_for_header

    def get_header(self) -> str:
        self._header_injected = True
        files = self._edited_files_this_turn
        lines = [f"[MULTI-FILE-EDIT] This turn requires coordinated changes to {len(files)} files."]
        lines.append(f"Files to edit: {', '.join(files)}")
        lines.append(
            "Complete ALL files before responding. Do not skip any. "
            "Check each file for cross-file consistency (imports, exports, shared types)."
        )
        return "\n".join(lines)

    def reset_turn(self) -> None:
        self._edited_files_this_turn.clear()
        self._header_injected = False

    @property
    def edited_files(self) -> list[str]:
        return list(self._edited_files_this_turn)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
