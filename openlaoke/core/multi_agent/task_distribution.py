"""Task distribution system for multi-agent coordination."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openlaoke.core.multi_agent.agent_pool import AgentPool, AgentState
    from openlaoke.core.multi_agent.coordinator import Task

logger = logging.getLogger(__name__)


class Priority(StrEnum):
    """Priority levels for tasks."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

    def __lt__(self, other: str) -> bool:
        if isinstance(other, Priority):
            order = {"low": 0, "medium": 1, "high": 2, "urgent": 3}
            return order[self.value] < order[other.value]
        return NotImplemented

    def __le__(self, other: str) -> bool:
        if isinstance(other, Priority):
            return self == other or self < other
        return NotImplemented

    def __gt__(self, other: str) -> bool:
        if isinstance(other, Priority):
            return not self <= other
        return NotImplemented

    def __ge__(self, other: str) -> bool:
        if isinstance(other, Priority):
            return not self < other
        return NotImplemented


class AssignmentStrategy(StrEnum):
    """Strategies for task assignment."""

    FIRST_AVAILABLE = "first_available"
    ROUND_ROBIN = "round_robin"
    LEAST_LOADED = "least_loaded"
    SPECIALIZED = "specialized"
    PRIORITY_BASED = "priority_based"


@dataclass
class Assignment:
    """Task assignment details."""

    assignment_id: str = field(default_factory=lambda: f"assign_{uuid4().hex[:8]}")
    task_id: str = ""
    agent_id: str | None = None
    strategy: AssignmentStrategy = AssignmentStrategy.FIRST_AVAILABLE
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "assignment_id": self.assignment_id,
            "task_id": self.task_id,
            "agent_id": self.agent_id,
            "strategy": self.strategy.value,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class TaskDistributorConfig:
    """Configuration for task distributor."""

    strategy: AssignmentStrategy = AssignmentStrategy.LEAST_LOADED
    max_retries: int = 3
    retry_delay: float = 5.0
    priority_boost_timeout: float = 60.0


class TaskDistributor:
    """Distributes tasks among available agents.

    Provides multiple distribution strategies:
    - First available: Assign to first available agent
    - Round robin: Distribute evenly in rotation
    - Least loaded: Assign to agent with least tasks
    - Specialized: Match task type to agent specialization
    - Priority based: High priority tasks get dedicated agents
    """

    def __init__(self, config: TaskDistributorConfig | None = None):
        """Initialize the task distributor.

        Args:
            config: Optional distributor configuration.
        """
        self.config = config or TaskDistributorConfig()
        self._round_robin_index = 0
        self._assignment_history: list[Assignment] = []

    async def distribute(
        self,
        task: Task,
        agent_pool: AgentPool,
        strategy: AssignmentStrategy | None = None,
    ) -> Assignment:
        """Distribute a task to an available agent.

        Args:
            task: Task to distribute.
            agent_pool: Agent pool to distribute to.
            strategy: Optional override strategy.

        Returns:
            Assignment details.
        """
        strategy = strategy or self.config.strategy

        assignment = Assignment(
            task_id=task.id,
            strategy=strategy,
        )

        active_agents = agent_pool.list_active()
        if not active_agents:
            assignment.agent_id = None
            assignment.metadata["reason"] = "No available agents"
            logger.warning(f"No available agents for task {task.id}")
            self._assignment_history.append(assignment)
            return assignment

        agent_id = await self._select_agent(task, active_agents, strategy)

        if agent_id:
            assignment.agent_id = agent_id
            logger.info(
                f"Assigned task {task.id} to agent {agent_id} using {strategy.value} strategy"
            )
        else:
            assignment.agent_id = None
            assignment.metadata["reason"] = "Agent selection failed"
            logger.warning(f"Failed to select agent for task {task.id}")

        self._assignment_history.append(assignment)
        return assignment

    async def _select_agent(
        self,
        task: Task,
        active_agents: list[AgentState],
        strategy: AssignmentStrategy,
    ) -> str | None:
        """Select an agent based on the distribution strategy.

        Args:
            task: Task to assign.
            active_agents: List of active agent states.
            strategy: Distribution strategy.

        Returns:
            Selected agent ID or None.
        """
        if not active_agents:
            return None

        if strategy == AssignmentStrategy.FIRST_AVAILABLE:
            return str(active_agents[0].agent_id)

        if strategy == AssignmentStrategy.ROUND_ROBIN:
            self._round_robin_index = (self._round_robin_index + 1) % len(active_agents)
            return str(active_agents[self._round_robin_index].agent_id)

        if strategy == AssignmentStrategy.LEAST_LOADED:
            return self._select_least_loaded(active_agents)

        if strategy == AssignmentStrategy.SPECIALIZED:
            return self._select_specialized(task, active_agents)

        if strategy == AssignmentStrategy.PRIORITY_BASED:
            return self._select_priority_based(task, active_agents)

        return str(active_agents[0].agent_id)

    def _select_least_loaded(self, active_agents: list[AgentState]) -> str:
        """Select agent with least current load.

        Args:
            active_agents: List of active agent states.

        Returns:
            Agent ID with least tasks.
        """
        task_counts: dict[str, int] = {}
        for assignment in self._assignment_history:
            if assignment.agent_id:
                task_counts[assignment.agent_id] = task_counts.get(assignment.agent_id, 0) + 1

        min_load = float("inf")
        selected_agent = str(active_agents[0].agent_id)

        for agent in active_agents:
            load = task_counts.get(agent.agent_id, 0)
            if load < min_load:
                min_load = load
                selected_agent = str(agent.agent_id)

        return selected_agent

    def _select_specialized(self, task: Task, active_agents: list[AgentState]) -> str | None:
        """Select agent based on task type specialization.

        Args:
            task: Task to assign.
            active_agents: List of active agent states.

        Returns:
            Specialized agent ID or None.
        """
        task_type_map = {
            "explorer": ["explorer", "researcher"],
            "implementer": ["implementer", "coordinator"],
            "reviewer": ["reviewer", "analyzer"],
            "tester": ["tester", "reviewer"],
        }

        task_type_str = str(task.metadata.get("task_type", ""))
        preferred_types = task_type_map.get(task_type_str, ["implementer"])

        for pref_type in preferred_types:
            for agent in active_agents:
                if hasattr(agent, "agent_type") and agent.agent_type.value == pref_type:
                    return str(agent.agent_id)

        return self._select_least_loaded(active_agents)

    def _select_priority_based(self, task: Task, active_agents: list[AgentState]) -> str:
        """Select agent based on task priority.

        Args:
            task: Task to assign.
            active_agents: List of active agent states.

        Returns:
            Agent ID for priority task.
        """
        if task.priority == Priority.URGENT:
            idle_agents = [a for a in active_agents if not a.current_task]
            if idle_agents:
                return str(idle_agents[0].agent_id)

        if task.priority == Priority.HIGH:
            low_load_agents = []
            for agent in active_agents:
                assignments = [a for a in self._assignment_history if a.agent_id == agent.agent_id]
                if len(assignments) < 2:
                    low_load_agents.append(agent)
            if low_load_agents:
                return str(low_load_agents[0].agent_id)

        return self._select_least_loaded(active_agents)

    def get_history(self, limit: int | None = None) -> list[Assignment]:
        """Get assignment history.

        Args:
            limit: Optional limit on number of assignments.

        Returns:
            List of past assignments.
        """
        if limit:
            return self._assignment_history[-limit:]
        return self._assignment_history.copy()

    def clear_history(self) -> None:
        """Clear assignment history."""
        self._assignment_history.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get distribution statistics.

        Returns:
            Dictionary with distribution statistics.
        """
        agent_counts: dict[str, int] = {}
        for assignment in self._assignment_history:
            if assignment.agent_id:
                agent_counts[assignment.agent_id] = agent_counts.get(assignment.agent_id, 0) + 1

        strategy_counts: dict[str, int] = {}
        for assignment in self._assignment_history:
            strategy_key = assignment.strategy.value
            strategy_counts[strategy_key] = strategy_counts.get(strategy_key, 0) + 1

        return {
            "total_assignments": len(self._assignment_history),
            "assignments_by_agent": agent_counts,
            "assignments_by_strategy": strategy_counts,
            "round_robin_index": self._round_robin_index,
        }
