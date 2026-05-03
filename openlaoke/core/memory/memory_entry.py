"""Memory entry data structures for the persistent memory system."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import uuid4


class MemoryType(StrEnum):
    PREFERENCE = "preference"   # user preferences (editor, shell, etc.)
    CORRECTION = "correction"   # user corrected a mistake
    STYLE = "style"            # communication/response style
    FACT = "fact"              # user facts (name, role, timezone)
    LESSON = "lesson"          # learned from tool failures
    PATTERN = "pattern"        # recurring patterns (rg -> powershell)
    EXPECTATION = "expectation"  # what user expects from the agent


@dataclass
class MemoryEntry:
    id: str = field(default_factory=lambda: str(uuid4()))
    memory_type: MemoryType = MemoryType.FACT
    key: str = ""
    content: str = ""
    trigger: str = ""  # what triggered this memory (e.g., "bash tool failed")
    tags: list[str] = field(default_factory=list)
    confidence: float = 1.0  # 0.0-1.0, how certain we are
    hit_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    source_session: str = ""  # session_id that created this

    def access(self) -> None:
        self.last_accessed = time.time()
        self.hit_count += 1

    def decay(self) -> None:
        elapsed_days = (time.time() - self.last_accessed) / 86400
        self.confidence = max(0.1, self.confidence - elapsed_days * 0.01)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "memory_type": str(self.memory_type),
            "key": self.key,
            "content": self.content,
            "trigger": self.trigger,
            "tags": self.tags,
            "confidence": self.confidence,
            "hit_count": self.hit_count,
            "created_at": self.created_at,
            "last_accessed": self.last_accessed,
            "source_session": self.source_session,
        }

    @classmethod
    def from_dict(cls, data: dict) -> MemoryEntry:
        return cls(
            id=data.get("id", str(uuid4())),
            memory_type=MemoryType(data.get("memory_type", "fact")),
            key=data.get("key", ""),
            content=data.get("content", ""),
            trigger=data.get("trigger", ""),
            tags=data.get("tags", []),
            confidence=data.get("confidence", 1.0),
            hit_count=data.get("hit_count", 0),
            created_at=data.get("created_at", time.time()),
            last_accessed=data.get("last_accessed", time.time()),
            source_session=data.get("source_session", ""),
        )
