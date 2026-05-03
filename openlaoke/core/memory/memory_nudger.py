"""Memory nudger - detects when to persist memories from conversation."""

from __future__ import annotations

import re

from openlaoke.core.memory.memory_entry import MemoryEntry, MemoryType


class MemoryNudger:
    CORRECTION_PATTERNS = [
        re.compile(r"(?:no[,!]?\s+)?(?:you\s+should|please\s+)?use\s+(.+)", re.I),
        re.compile(r"don'?t\s+use\s+(.+?)[,.]\s+use\s+(.+)", re.I),
        re.compile(r"(?:actually|instead)[,.]?\s+use\s+(.+)", re.I),
        re.compile(r"next\s+time[,.]?\s+use\s+(.+)", re.I),
        re.compile(r"(?:I\s+)?prefer\s+(.+)", re.I),
        re.compile(r"always\s+use\s+(.+)", re.I),
    ]

    PREFERENCE_PATTERNS = [
        re.compile(r"my\s+(\w+)\s+is\s+(.+)", re.I),
        re.compile(r"I\s+am\s+(\w+)\s+(.+)", re.I),
        re.compile(r"I\s+work\s+(?:in|at|as)\s+(.+)", re.I),
        re.compile(r"I'?m\s+in\s+(\w+)\s+timezone", re.I),
        re.compile(r"my\s+timezone\s+is\s+(.+)", re.I),
    ]

    def analyze(
        self,
        user_message: str,
        tool_error: str | None = None,
        session_id: str = "",
    ) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []

        entries.extend(self._detect_corrections(user_message))
        entries.extend(self._detect_preferences(user_message))

        if tool_error:
            if "Command not found" in tool_error or "not recognized" in tool_error:
                entries.append(
                    MemoryEntry(
                        memory_type=MemoryType.LESSON,
                        key="command_not_found",
                        content=tool_error[:200],
                        trigger="tool_execution_failed",
                        source_session=session_id,
                    )
                )

            if "Permission denied" in tool_error:
                entries.append(
                    MemoryEntry(
                        memory_type=MemoryType.LESSON,
                        key="permission_denied",
                        content=tool_error[:200],
                        trigger="tool_permission_failed",
                        source_session=session_id,
                    )
                )

        return entries

    def analyze_repeated_pattern(
        self, recent_failures: list[str], session_id: str = ""
    ) -> MemoryEntry | None:
        if len(recent_failures) < 3:
            return None
        first = recent_failures[0][:100]
        if all(first[:50].lower() in f.lower() for f in recent_failures[1:]):
            return MemoryEntry(
                memory_type=MemoryType.PATTERN,
                key="repeated_failure",
                content=f"Avoid repeated failure: {first}",
                trigger=f"consecutive_failures_{len(recent_failures)}",
                confidence=0.8,
                source_session=session_id,
            )
        return None

    def _detect_corrections(self, text: str) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for pattern in self.CORRECTION_PATTERNS:
            m = pattern.search(text)
            if m:
                if m.lastindex and m.lastindex >= 2:
                    tool_or_method = (m.group(1) + " " + m.group(2)).strip()
                else:
                    tool_or_method = m.group(1).strip()
                if len(tool_or_method) > 5:
                    entries.append(
                        MemoryEntry(
                            memory_type=MemoryType.CORRECTION,
                            key=f"use_{tool_or_method[:50]}",
                            content=f"User prefers: {tool_or_method}",
                            trigger="user_correction",
                            tags=["correction", "user_preference"],
                        )
                    )
        return entries

    def _detect_preferences(self, text: str) -> list[MemoryEntry]:
        entries: list[MemoryEntry] = []
        for pattern in self.PREFERENCE_PATTERNS:
            m = pattern.search(text)
            if m:
                key = m.group(1).strip().lower()
                val = m.group(2).strip()
                if len(val) > 1:
                    entries.append(
                        MemoryEntry(
                            memory_type=MemoryType.PREFERENCE,
                            key=f"user_{key}",
                            content=f"User {key}: {val}",
                            trigger="preference_detection",
                            tags=["preference", key],
                        )
                    )
        return entries
