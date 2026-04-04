"""Multi-Agent coordinator for managing agent collaboration."""

from __future__ import annotations

import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from openlaoke.core.multi_agent.agent_pool import AgentPool
from openlaoke.core.multi_agent.communication import AgentMailbox, Message, MessageType
from openlaoke.core.multi_agent.conflict_resolution import (
    Conflict,
    ConflictResolution,
    ConflictResolver,
)
from openlaoke.core.multi_agent.task_distribution import Assignment, Priority, TaskDistributor
from openlaoke.core.multi_agent.team import Team, TeamResult
from openlaoke.types.core_types import TaskStatus, TaskType

if TYPE_CHECKING:
    from openlaoke.core.state import AppState

logger = logging.getLogger(__name__)

MAX_CONCURRENT_AGENTS = 3
DEFAULT_TIMEOUT = 15 * 60


@dataclass
class GlobalState:
    """Global state shared across all agents."""

    session_id: str = ""
    active_agents: int = 0
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    start_time: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "active_agents": self.active_agents,
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "start_time": self.start_time,
            "metadata": self.metadata,
        }


@dataclass
class Task:
    """Task representation for multi-agent system."""

    id: str = field(default_factory=lambda: f"task_{uuid4().hex[:8]}")
    description: str = ""
    task_type: TaskType = TaskType.LOCAL_AGENT
    priority: Priority = Priority.MEDIUM
    assigned_agent: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class AgentCoordinator:
    """Multi-Agent coordinator for managing agent collaboration.

    This class orchestrates multiple agents working together on complex tasks.
    It manages agent lifecycle, task distribution, communication, and conflict resolution.
    """

    def __init__(
        self,
        max_agents: int = MAX_CONCURRENT_AGENTS,
        timeout: int = DEFAULT_TIMEOUT,
        app_state: AppState | None = None,
    ):
        """Initialize the coordinator.

        Args:
            max_agents: Maximum number of concurrent agents.
            timeout: Default timeout for agent execution in seconds.
            app_state: Optional application state for integration.
        """
        self.max_agents = max_agents
        self.timeout = timeout
        self.app_state = app_state

        self.agent_pool = AgentPool(max_agents=max_agents)
        self.mailbox = AgentMailbox()
        self.task_distributor = TaskDistributor()
        self.conflict_resolver = ConflictResolver()

        self._task_queue: asyncio.PriorityQueue[tuple[Priority, Task]] = asyncio.PriorityQueue()
        self._tasks: dict[str, Task] = {}
        self._assignments: dict[str, Assignment] = {}
        self._global_state = GlobalState(session_id=f"coord_{uuid4().hex[:8]}")

        self._executor = ThreadPoolExecutor(max_workers=max_agents, thread_name_prefix="agent-")
        self._running = False
        self._lock = asyncio.Lock()

    async def spawn_agent(
        self,
        agent_type: str,
        task: Task,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Spawn a new agent for a specific task.

        Args:
            agent_type: Type of agent to spawn (coordinator, explorer, implementer, etc.).
            task: Task for the agent to execute.
            config: Optional agent configuration.

        Returns:
            Agent ID of the spawned agent.
        """
        async with self._lock:
            if self.agent_pool.active_count >= self.max_agents:
                raise RuntimeError(f"Maximum concurrent agents ({self.max_agents}) reached")

            agent_id = await self.agent_pool.acquire(agent_type, task, config or {})
            self._global_state.active_agents = self.agent_pool.active_count

            logger.info(f"Spawned agent {agent_id} of type {agent_type} for task {task.id}")
            return agent_id

    async def dispatch_task(self, task: Task) -> Assignment:
        """Dispatch a task to an available agent.

        Args:
            task: Task to dispatch.

        Returns:
            Assignment details.
        """
        task.status = TaskStatus.PENDING
        task.start_time = time.time()
        self._tasks[task.id] = task
        self._global_state.total_tasks += 1

        assignment = await self.task_distributor.distribute(task, self.agent_pool)
        self._assignments[task.id] = assignment

        if assignment.agent_id:
            task.assigned_agent = assignment.agent_id
            task.status = TaskStatus.RUNNING
            await self.mailbox.send(
                Message(
                    sender="coordinator",
                    recipients=[assignment.agent_id],
                    content=f"Task assigned: {task.description}",
                    message_type=MessageType.TASK,
                    metadata={"task_id": task.id},
                )
            )
            logger.info(f"Dispatched task {task.id} to agent {assignment.agent_id}")

        return assignment

    async def collect_results(self, task_id: str) -> list[Any]:
        """Collect results from all agents working on a task.

        Args:
            task_id: Task ID to collect results for.

        Returns:
            List of results from agents.
        """
        results: list[Any] = []

        messages = await self.mailbox.get_messages(f"result_{task_id}")
        for msg in messages:
            if msg.message_type == MessageType.RESULT:
                results.append(msg.content)

        task = self._tasks.get(task_id)
        if task:
            task.status = TaskStatus.COMPLETED
            task.end_time = time.time()
            if results:
                task.result = results
            self._global_state.completed_tasks += 1

        return results

    async def resolve_conflicts(self, conflicts: list[Conflict]) -> list[ConflictResolution]:
        """Resolve conflicts between agents.

        Args:
            conflicts: List of conflicts to resolve.

        Returns:
            List of conflict resolutions.
        """
        resolutions = []
        for conflict in conflicts:
            resolution = await self.conflict_resolver.resolve(conflict)
            resolutions.append(resolution)

            await self.broadcast(
                Message(
                    sender="coordinator",
                    content=f"Conflict resolved: {resolution.resolution}",
                    message_type=MessageType.SYSTEM,
                    metadata={"conflict_id": conflict.id, "resolution": resolution.to_dict()},
                )
            )

            logger.info(f"Resolved conflict {conflict.id}: {resolution.strategy.value}")

        return resolutions

    async def coordinate_team(self, team: Team) -> TeamResult:
        """Coordinate a team of agents working together.

        Args:
            team: Team configuration with members and roles.

        Returns:
            Team execution result.
        """
        team_tasks: list[Task] = []

        for member in team.members:
            task = Task(
                description=f"Team task for {member.role.value}",
                priority=Priority.HIGH,
                metadata={"team_id": team.id, "role": member.role.value},
            )
            team_tasks.append(task)

        assignments: list[Assignment] = []
        for task in team_tasks:
            assignment = await self.dispatch_task(task)
            assignments.append(assignment)

        await asyncio.gather(*[self._wait_for_task(t.id) for t in team_tasks])

        results = {}
        for task in team_tasks:
            task_results = await self.collect_results(task.id)
            results[task.id] = task_results

        success = all(t.status == TaskStatus.COMPLETED for t in team_tasks)

        return TeamResult(
            team_id=team.id,
            success=success,
            results=results,
            assignments={a.task_id: a for a in assignments},
        )

    async def broadcast(self, message: Message) -> None:
        """Broadcast a message to all active agents.

        Args:
            message: Message to broadcast.
        """
        active_agents = self.agent_pool.list_active()
        message.recipients = [a.agent_id for a in active_agents]
        await self.mailbox.send(message)

        logger.debug(f"Broadcast message to {len(message.recipients)} agents")

    async def sync_state(self) -> GlobalState:
        """Synchronize and return the global state.

        Returns:
            Current global state.
        """
        self._global_state.active_agents = self.agent_pool.active_count
        return self._global_state

    async def shutdown(self) -> None:
        """Gracefully shutdown the coordinator and all agents."""
        self._running = False

        await self.agent_pool.release_all()

        self._executor.shutdown(wait=True)

        logger.info("Coordinator shutdown complete")

    async def _wait_for_task(self, task_id: str, timeout: float | None = None) -> None:
        """Wait for a task to complete.

        Args:
            task_id: Task ID to wait for.
            timeout: Optional timeout in seconds.
        """
        timeout = timeout or self.timeout
        start = time.time()

        while True:
            task = self._tasks.get(task_id)
            if not task:
                return

            if task.status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.KILLED):
                return

            if time.time() - start > timeout:
                task.status = TaskStatus.FAILED
                task.error = "Task timeout"
                logger.error(f"Task {task_id} timed out after {timeout}s")
                return

            await asyncio.sleep(0.1)
