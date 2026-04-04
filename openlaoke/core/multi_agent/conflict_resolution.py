"""Conflict resolution system for multi-agent coordination."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class ConflictType(StrEnum):
    """Types of conflicts that can occur."""

    RESOURCE = "resource"
    TASK = "task"
    DECISION = "decision"
    COMMUNICATION = "communication"
    STATE = "state"
    PRIORITY = "priority"


class ResolutionStrategy(StrEnum):
    """Strategies for resolving conflicts."""

    FIRST_WINS = "first_wins"
    LAST_WINS = "last_wins"
    PRIORITY_WINS = "priority_wins"
    VOTING = "voting"
    COORDINATOR_DECIDES = "coordinator_decides"
    MERGE = "merge"
    COMPROMISE = "compromise"
    ESCALATE = "escalate"


@dataclass
class Conflict:
    """Represents a conflict between agents.

    Attributes:
        id: Unique conflict identifier.
        conflict_type: Type of conflict.
        agents_involved: IDs of agents involved in the conflict.
        description: Human-readable description.
        resources: Resources involved in the conflict.
        created_at: When the conflict was detected.
        metadata: Additional conflict metadata.
    """

    id: str = field(default_factory=lambda: f"conflict_{uuid4().hex[:8]}")
    conflict_type: ConflictType = ConflictType.TASK
    agents_involved: list[str] = field(default_factory=list)
    description: str = ""
    resources: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "conflict_type": self.conflict_type.value,
            "agents_involved": self.agents_involved,
            "description": self.description,
            "resources": self.resources,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


@dataclass
class ConflictResolution:
    """Represents the resolution of a conflict.

    Attributes:
        conflict_id: ID of the resolved conflict.
        strategy: Strategy used to resolve.
        resolution: The actual resolution outcome.
        winner: Agent that won the conflict (if applicable).
        resolved_at: When the conflict was resolved.
        metadata: Additional resolution metadata.
    """

    conflict_id: str = ""
    strategy: ResolutionStrategy = ResolutionStrategy.COORDINATOR_DECIDES
    resolution: str = ""
    winner: str | None = None
    resolved_at: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.value,
            "resolution": self.resolution,
            "winner": self.winner,
            "resolved_at": self.resolved_at,
            "metadata": self.metadata,
        }


class ConflictResolver:
    """Resolves conflicts between agents.

    Provides multiple resolution strategies and tracks conflict history.
    """

    def __init__(
        self,
        default_strategy: ResolutionStrategy = ResolutionStrategy.COORDINATOR_DECIDES,
        max_history: int = 100,
    ):
        """Initialize the conflict resolver.

        Args:
            default_strategy: Default resolution strategy.
            max_history: Maximum number of conflicts to keep in history.
        """
        self.default_strategy = default_strategy
        self.max_history = max_history

        self._conflicts: list[Conflict] = []
        self._resolutions: list[ConflictResolution] = []
        self._pending: dict[str, Conflict] = {}

    async def detect(
        self,
        agents: list[str],
        resources: list[str] | None = None,
        conflict_type: ConflictType | None = None,
    ) -> Conflict | None:
        """Detect a potential conflict between agents.

        Args:
            agents: List of agent IDs to check.
            resources: Optional list of resources.
            conflict_type: Optional conflict type.

        Returns:
            Detected conflict or None.
        """
        if len(agents) < 2:
            return None

        if not conflict_type:
            conflict_type = ConflictType.RESOURCE if resources else ConflictType.TASK

        conflict = Conflict(
            conflict_type=conflict_type,
            agents_involved=agents,
            resources=resources or [],
            description=f"Potential {conflict_type.value} conflict detected",
        )

        self._pending[conflict.id] = conflict
        logger.info(f"Detected conflict {conflict.id} between agents {agents}")

        return conflict

    async def resolve(
        self,
        conflict: Conflict,
        strategy: ResolutionStrategy | None = None,
        context: dict[str, Any] | None = None,
    ) -> ConflictResolution:
        """Resolve a conflict using the specified strategy.

        Args:
            conflict: Conflict to resolve.
            strategy: Optional override strategy.
            context: Additional context for resolution.

        Returns:
            Conflict resolution.
        """
        strategy = strategy or self.default_strategy

        resolution = ConflictResolution(
            conflict_id=conflict.id,
            strategy=strategy,
        )

        resolution = await self._apply_strategy(conflict, resolution, strategy, context or {})

        self._conflicts.append(conflict)
        self._resolutions.append(resolution)

        if conflict.id in self._pending:
            del self._pending[conflict.id]

        if len(self._conflicts) > self.max_history:
            self._conflicts = self._conflicts[-self.max_history :]
        if len(self._resolutions) > self.max_history:
            self._resolutions = self._resolutions[-self.max_history :]

        logger.info(f"Resolved conflict {conflict.id} using {strategy.value} strategy")
        return resolution

    async def _apply_strategy(
        self,
        conflict: Conflict,
        resolution: ConflictResolution,
        strategy: ResolutionStrategy,
        context: dict[str, Any],
    ) -> ConflictResolution:
        """Apply a resolution strategy.

        Args:
            conflict: Conflict to resolve.
            resolution: Resolution object to populate.
            strategy: Strategy to apply.
            context: Resolution context.

        Returns:
            Populated resolution.
        """
        if strategy == ResolutionStrategy.FIRST_WINS:
            resolution.winner = conflict.agents_involved[0]
            resolution.resolution = f"First agent {resolution.winner} wins"

        elif strategy == ResolutionStrategy.LAST_WINS:
            resolution.winner = conflict.agents_involved[-1]
            resolution.resolution = f"Last agent {resolution.winner} wins"

        elif strategy == ResolutionStrategy.PRIORITY_WINS:
            priorities = context.get("priorities", {})
            winner = max(
                conflict.agents_involved,
                key=lambda a: priorities.get(a, 0),
            )
            resolution.winner = winner
            resolution.resolution = f"Highest priority agent {winner} wins"

        elif strategy == ResolutionStrategy.VOTING:
            votes = context.get("votes", {})
            winner = max(
                conflict.agents_involved,
                key=lambda a: votes.get(a, 0),
            )
            resolution.winner = winner
            resolution.resolution = f"Agent {winner} wins by vote"

        elif strategy == ResolutionStrategy.COORDINATOR_DECIDES:
            decision = context.get("coordinator_decision", conflict.agents_involved[0])
            resolution.winner = decision
            resolution.resolution = f"Coordinator decided: agent {decision} wins"

        elif strategy == ResolutionStrategy.MERGE:
            resolution.resolution = "Resources merged between agents"
            resolution.metadata["merged_resources"] = conflict.resources

        elif strategy == ResolutionStrategy.COMPROMISE:
            resolution.resolution = "Agents agreed to compromise"
            resolution.metadata["compromise_terms"] = context.get("compromise_terms", [])

        elif strategy == ResolutionStrategy.ESCALATE:
            resolution.resolution = "Conflict escalated to higher authority"
            resolution.metadata["escalated_to"] = context.get("escalated_to", "system")

        return resolution

    def get_conflict(self, conflict_id: str) -> Conflict | None:
        """Get a conflict by ID.

        Args:
            conflict_id: Conflict ID to look up.

        Returns:
            Conflict if found, None otherwise.
        """
        for conflict in self._conflicts:
            if conflict.id == conflict_id:
                return conflict
        return self._pending.get(conflict_id)

    def get_resolution(self, conflict_id: str) -> ConflictResolution | None:
        """Get a resolution by conflict ID.

        Args:
            conflict_id: Conflict ID to look up.

        Returns:
            Resolution if found, None otherwise.
        """
        for resolution in self._resolutions:
            if resolution.conflict_id == conflict_id:
                return resolution
        return None

    def get_pending_conflicts(self) -> list[Conflict]:
        """Get all pending conflicts.

        Returns:
            List of pending conflicts.
        """
        return list(self._pending.values())

    def get_history(self, limit: int | None = None) -> list[tuple[Conflict, ConflictResolution]]:
        """Get conflict resolution history.

        Args:
            limit: Optional limit on number of entries.

        Returns:
            List of (conflict, resolution) tuples.
        """
        history = list(zip(self._conflicts, self._resolutions, strict=False))
        if limit:
            return history[-limit:]
        return history

    def get_stats(self) -> dict[str, Any]:
        """Get conflict resolution statistics.

        Returns:
            Dictionary with statistics.
        """
        type_counts: dict[str, int] = {}
        for conflict in self._conflicts:
            type_key = conflict.conflict_type.value
            type_counts[type_key] = type_counts.get(type_key, 0) + 1

        strategy_counts: dict[str, int] = {}
        for resolution in self._resolutions:
            strategy_key = resolution.strategy.value
            strategy_counts[strategy_key] = strategy_counts.get(strategy_key, 0) + 1

        return {
            "total_conflicts": len(self._conflicts),
            "pending_conflicts": len(self._pending),
            "by_type": type_counts,
            "by_strategy": strategy_counts,
        }

    def clear_history(self) -> None:
        """Clear conflict resolution history."""
        self._conflicts.clear()
        self._resolutions.clear()
        self._pending.clear()
