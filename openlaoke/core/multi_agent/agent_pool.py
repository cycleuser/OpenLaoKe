"""Agent pool for managing agent lifecycle and resources."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


class AgentType(StrEnum):
    """Types of agents in the system."""

    COORDINATOR = "coordinator"
    EXPLORER = "explorer"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    RESEARCHER = "researcher"
    ANALYZER = "analyzer"


@dataclass
class AgentState:
    """Runtime state of an agent."""

    agent_id: str
    agent_type: AgentType
    status: str = "idle"
    current_task: str | None = None
    start_time: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "status": self.status,
            "current_task": self.current_task,
            "start_time": self.start_time,
            "last_activity": self.last_activity,
            "metadata": self.metadata,
        }

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()


class AgentPool:
    """Manages a pool of agents with lifecycle and resource management.

    This class provides:
    - Agent lifecycle management (acquire, release)
    - Concurrent agent limit enforcement
    - Timeout control
    - Resource isolation
    """

    def __init__(
        self,
        max_agents: int = 3,
        default_timeout: int = 900,
    ):
        """Initialize the agent pool.

        Args:
            max_agents: Maximum number of concurrent agents (default: 3).
            default_timeout: Default timeout for agent execution in seconds (default: 900 = 15 minutes).
        """
        self.max_agents = max_agents
        self.default_timeout = default_timeout

        self._agents: dict[str, AgentState] = {}
        self._lock = asyncio.Lock()
        self._semaphore = asyncio.Semaphore(max_agents)

    @property
    def active_count(self) -> int:
        """Get the count of active agents."""
        return len([a for a in self._agents.values() if a.status == "active"])

    @property
    def total_count(self) -> int:
        """Get the total count of agents (active + idle)."""
        return len(self._agents)

    async def acquire(
        self,
        agent_type: str | AgentType,
        task: Any | None = None,
        config: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> str:
        """Acquire an agent from the pool.

        Args:
            agent_type: Type of agent to acquire.
            task: Optional task to assign to the agent.
            config: Optional configuration for the agent.
            timeout: Optional timeout in seconds.

        Returns:
            Agent ID of the acquired agent.

        Raises:
            RuntimeError: If maximum agents reached or acquisition fails.
        """
        if isinstance(agent_type, str):
            try:
                agent_type = AgentType(agent_type)
            except ValueError:
                agent_type = AgentType.IMPLEMENTER

        timeout = timeout or self.default_timeout

        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout)
        except TimeoutError as err:
            raise RuntimeError(
                f"Timeout waiting for available agent slot (max: {self.max_agents})"
            ) from err

        async with self._lock:
            agent_id = f"agent_{uuid4().hex[:8]}"
            state = AgentState(
                agent_id=agent_id,
                agent_type=agent_type,
                status="active",
                current_task=task.id if task and hasattr(task, "id") else None,
                metadata=config or {},
            )
            self._agents[agent_id] = state

            logger.info(f"Acquired agent {agent_id} of type {agent_type.value}")
            return agent_id

    async def release(self, agent_id: str) -> None:
        """Release an agent back to the pool.

        Args:
            agent_id: ID of the agent to release.
        """
        async with self._lock:
            if agent_id not in self._agents:
                logger.warning(f"Attempted to release unknown agent {agent_id}")
                return

            state = self._agents[agent_id]
            state.status = "released"
            state.current_task = None

            del self._agents[agent_id]
            self._semaphore.release()

            logger.info(f"Released agent {agent_id}")

    async def release_all(self) -> None:
        """Release all agents in the pool."""
        async with self._lock:
            agent_ids = list(self._agents.keys())

        for agent_id in agent_ids:
            await self.release(agent_id)

        logger.info(f"Released all {len(agent_ids)} agents")

    def get_agent(self, agent_id: str) -> AgentState | None:
        """Get an agent's state by ID.

        Args:
            agent_id: Agent ID to look up.

        Returns:
            AgentState if found, None otherwise.
        """
        return self._agents.get(agent_id)

    def list_active(self) -> list[AgentState]:
        """List all active agents.

        Returns:
            List of active agent states.
        """
        return [a for a in self._agents.values() if a.status == "active"]

    def list_all(self) -> list[AgentState]:
        """List all agents in the pool.

        Returns:
            List of all agent states.
        """
        return list(self._agents.values())

    async def update_agent_status(
        self,
        agent_id: str,
        status: str,
        task: Any | None = None,
    ) -> None:
        """Update an agent's status.

        Args:
            agent_id: Agent ID to update.
            status: New status value.
            task: Optional task to assign.
        """
        async with self._lock:
            if agent_id not in self._agents:
                return

            state = self._agents[agent_id]
            state.status = status
            state.update_activity()

            if task:
                state.current_task = task.id if hasattr(task, "id") else str(task)

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics.

        Returns:
            Dictionary with pool statistics.
        """
        agents = list(self._agents.values())
        return {
            "max_agents": self.max_agents,
            "total_count": len(agents),
            "active_count": len([a for a in agents if a.status == "active"]),
            "idle_count": len([a for a in agents if a.status == "idle"]),
            "agents_by_type": self._count_by_type(agents),
        }

    def _count_by_type(self, agents: list[AgentState]) -> dict[str, int]:
        """Count agents by type.

        Args:
            agents: List of agent states.

        Returns:
            Dictionary with count by agent type.
        """
        counts: dict[str, int] = {}
        for agent in agents:
            type_name = agent.agent_type.value
            counts[type_name] = counts.get(type_name, 0) + 1
        return counts
