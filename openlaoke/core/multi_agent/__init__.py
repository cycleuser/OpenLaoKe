"""Multi-Agent collaboration system for OpenLaoKe."""

from __future__ import annotations

from openlaoke.core.multi_agent.agent_pool import AgentPool, AgentState, AgentType
from openlaoke.core.multi_agent.communication import (
    AgentMailbox,
    Message,
    MessagePriority,
    MessageType,
)
from openlaoke.core.multi_agent.conflict_resolution import (
    Conflict,
    ConflictResolution,
    ConflictResolver,
    ConflictType,
    ResolutionStrategy,
)
from openlaoke.core.multi_agent.coordinator import AgentCoordinator, GlobalState, Task
from openlaoke.core.multi_agent.task_distribution import (
    Assignment,
    AssignmentStrategy,
    Priority,
    TaskDistributor,
)
from openlaoke.core.multi_agent.team import (
    AgentRole,
    Team,
    TeamMember,
    TeamResult,
    TeamStatus,
)

__all__ = [
    "AgentCoordinator",
    "AgentPool",
    "AgentState",
    "AgentType",
    "AgentMailbox",
    "Message",
    "MessageType",
    "MessagePriority",
    "Conflict",
    "ConflictType",
    "ConflictResolution",
    "ConflictResolver",
    "ResolutionStrategy",
    "TaskDistributor",
    "Assignment",
    "AssignmentStrategy",
    "Priority",
    "Task",
    "Team",
    "TeamMember",
    "TeamResult",
    "AgentRole",
    "TeamStatus",
    "GlobalState",
]
