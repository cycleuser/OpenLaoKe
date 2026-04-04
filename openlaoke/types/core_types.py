"""Shared type definitions for OpenLaoKe."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4


class PermissionMode(StrEnum):
    """Permission modes for tool execution."""

    DEFAULT = "default"
    AUTO = "auto"
    BYPASS = "bypass"


class HyperAutoMode(StrEnum):
    """HyperAuto operation modes."""

    SEMI_AUTO = "semi_auto"
    FULL_AUTO = "full_auto"
    HYPER_AUTO = "hyper_auto"


class PermissionResult(StrEnum):
    """Result of a permission check."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class TaskType(StrEnum):
    """Types of tasks that can be executed."""

    LOCAL_BASH = "local_bash"
    LOCAL_AGENT = "local_agent"
    REMOTE_AGENT = "remote_agent"
    IN_PROCESS_TEAMMATE = "in_process_teammate"
    LOCAL_WORKFLOW = "local_workflow"
    MONITOR_MCP = "monitor_mcp"
    DREAM = "dream"


class TaskStatus(StrEnum):
    """Lifecycle states for tasks."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    KILLED = "killed"


def is_terminal_task_status(status: TaskStatus) -> bool:
    """True when a task is in a terminal state and will not transition further."""
    return status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED)


@dataclass
class TaskId:
    """Generates and parses task IDs with type prefixes."""

    PREFIXES: dict[str, str] = field(
        default_factory=lambda: {
            TaskType.LOCAL_BASH: "b",
            TaskType.LOCAL_AGENT: "a",
            TaskType.REMOTE_AGENT: "r",
            TaskType.IN_PROCESS_TEAMMATE: "t",
            TaskType.LOCAL_WORKFLOW: "w",
            TaskType.MONITOR_MCP: "m",
            TaskType.DREAM: "d",
        }
    )

    def generate(self, task_type: TaskType) -> str:
        prefix = self.PREFIXES.get(task_type, "x")
        return f"{prefix}_{uuid4().hex[:8]}"

    def parse_type(self, task_id: str) -> str | None:
        prefix = task_id.split("_")[0] if "_" in task_id else task_id[0]
        for task_type, p in self.PREFIXES.items():
            if p == prefix:
                return task_type
        return None


@dataclass
class AgentId:
    """Identifier for an agent/subagent instance."""

    id: str = field(default_factory=lambda: uuid4().hex[:12])
    parent_id: str | None = None
    name: str = "agent"

    def __str__(self) -> str:
        return self.id


@dataclass
class ToolUseBlock:
    """Represents a tool use request from the model."""

    id: str
    name: str
    input: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "tool_use",
            "id": self.id,
            "name": self.name,
            "input": self.input,
        }


@dataclass
class ToolResultBlock:
    """Represents the result of a tool execution."""

    tool_use_id: str
    content: str | list[dict[str, Any]]
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "tool_result",
            "tool_use_id": self.tool_use_id,
            "content": self.content,
            "is_error": self.is_error,
        }


@dataclass
class ToolProgress:
    """Progress information for a running tool."""

    tool_use_id: str
    tool_name: str
    message: str
    percentage: float | None = None
    spinner: str = "dots"


class MessageRole(StrEnum):
    """Roles in the conversation message list."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class BaseMessage:
    """Base message in the conversation."""

    role: MessageRole
    timestamp: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {"role": self.role.value, "timestamp": self.timestamp}


@dataclass
class UserMessage(BaseMessage):
    """Message from the user."""

    content: str = ""
    images: list[str] = field(default_factory=list)
    attachments: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "user",
            "content": self.content,
            "images": self.images,
        }


@dataclass
class AssistantMessage(BaseMessage):
    """Message from the assistant (model response)."""

    content: str = ""
    tool_uses: list[ToolUseBlock] = field(default_factory=list)
    stop_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "assistant",
            "content": self.content,
            "tool_uses": [tu.to_dict() for tu in self.tool_uses],
            "stop_reason": self.stop_reason,
        }


@dataclass
class SystemMessage(BaseMessage):
    """System-generated message (e.g., tool output, status)."""

    content: str = ""
    subtype: str = "info"

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "system",
            "content": self.content,
            "subtype": self.subtype,
        }


@dataclass
class ProgressMessage(BaseMessage):
    """Real-time progress update."""

    content: str = ""
    tool_use_id: str = ""
    tool_name: str = ""
    percentage: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "progress",
            "content": self.content,
            "tool_use_id": self.tool_use_id,
            "tool_name": self.tool_name,
        }


@dataclass
class AttachmentMessage(BaseMessage):
    """Message with file attachments."""

    content: str = ""
    file_paths: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            **super().to_dict(),
            "type": "attachment",
            "content": self.content,
            "file_paths": self.file_paths,
        }


Message = UserMessage | AssistantMessage | SystemMessage | ProgressMessage | AttachmentMessage


@dataclass
class TaskState:
    """Runtime state of a task."""

    id: str
    type: TaskType
    status: TaskStatus = TaskStatus.PENDING
    description: str = ""
    tool_use_id: str | None = None
    start_time: float = 0.0
    end_time: float | None = None
    total_paused_ms: float = 0.0
    output_file: str = ""
    output_offset: int = 0
    notified: bool = False
    output: str = ""
    exit_code: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "status": self.status.value,
            "description": self.description,
            "tool_use_id": self.tool_use_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_paused_ms": self.total_paused_ms,
            "output_file": self.output_file,
            "output_offset": self.output_offset,
            "notified": self.notified,
            "exit_code": self.exit_code,
        }


@dataclass
class ValidationResult:
    """Result of input validation."""

    result: bool
    message: str = ""
    error_code: int = 0


@dataclass
class TokenUsage:
    """Token usage tracking for API calls."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_creation_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def accumulate(self, other: TokenUsage) -> None:
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_creation_tokens += other.cache_creation_tokens

    def to_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_creation_tokens": self.cache_creation_tokens,
        }


@dataclass
class CostInfo:
    """Cost tracking for API calls."""

    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_creation_cost: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.input_cost + self.output_cost + self.cache_read_cost + self.cache_creation_cost
