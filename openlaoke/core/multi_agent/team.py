"""Team management for multi-agent collaboration."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

if TYPE_CHECKING:
    from openlaoke.core.multi_agent.task_distribution import Assignment

logger = logging.getLogger(__name__)


class AgentRole(StrEnum):
    """Roles that agents can have in a team."""

    LEADER = "leader"
    COORDINATOR = "coordinator"
    EXPLORER = "explorer"
    IMPLEMENTER = "implementer"
    REVIEWER = "reviewer"
    TESTER = "tester"
    RESEARCHER = "researcher"
    ANALYZER = "analyzer"
    SUPPORTER = "supporter"


class TeamStatus(StrEnum):
    """Status of a team."""

    FORMING = "forming"
    ACTIVE = "active"
    WORKING = "working"
    COMPLETED = "completed"
    FAILED = "failed"
    DISBANDED = "disbanded"


@dataclass
class TeamMember:
    """Member of a team with specific role."""

    agent_id: str
    role: AgentRole
    capabilities: list[str] = field(default_factory=list)
    load: int = 0
    status: str = "idle"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "capabilities": self.capabilities,
            "load": self.load,
            "status": self.status,
            "metadata": self.metadata,
        }


@dataclass
class TeamConfig:
    """Configuration for a team."""

    name: str = ""
    max_members: int = 10
    require_leader: bool = True
    auto_assign_roles: bool = True
    collaboration_mode: str = "parallel"


@dataclass
class Team:
    """Team of agents working together.

    Attributes:
        id: Unique team identifier.
        name: Team name.
        members: List of team members.
        status: Current team status.
        config: Team configuration.
        created_at: When the team was created.
        tasks_completed: Number of tasks completed.
        metadata: Additional team metadata.
    """

    id: str = field(default_factory=lambda: f"team_{uuid4().hex[:8]}")
    name: str = ""
    members: list[TeamMember] = field(default_factory=list)
    status: TeamStatus = TeamStatus.FORMING
    config: TeamConfig = field(default_factory=TeamConfig)
    created_at: float = field(default_factory=time.time)
    tasks_completed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "members": [m.to_dict() for m in self.members],
            "status": self.status.value,
            "config": {
                "name": self.config.name,
                "max_members": self.config.max_members,
                "require_leader": self.config.require_leader,
            },
            "created_at": self.created_at,
            "tasks_completed": self.tasks_completed,
            "metadata": self.metadata,
        }

    def get_member(self, agent_id: str) -> TeamMember | None:
        """Get a team member by agent ID.

        Args:
            agent_id: Agent ID to look up.

        Returns:
            TeamMember if found, None otherwise.
        """
        for member in self.members:
            if member.agent_id == agent_id:
                return member
        return None

    def get_leader(self) -> TeamMember | None:
        """Get the team leader.

        Returns:
            TeamMember if leader found, None otherwise.
        """
        for member in self.members:
            if member.role == AgentRole.LEADER:
                return member
        return None

    def get_members_by_role(self, role: AgentRole) -> list[TeamMember]:
        """Get all members with a specific role.

        Args:
            role: Role to filter by.

        Returns:
            List of members with that role.
        """
        return [m for m in self.members if m.role == role]

    def add_member(
        self,
        agent_id: str,
        role: AgentRole,
        capabilities: list[str] | None = None,
    ) -> bool:
        """Add a member to the team.

        Args:
            agent_id: Agent ID to add.
            role: Role for the member.
            capabilities: Optional list of capabilities.

        Returns:
            True if member was added, False if team is full.
        """
        if len(self.members) >= self.config.max_members:
            logger.warning(f"Team {self.id} is full (max: {self.config.max_members})")
            return False

        if self.get_member(agent_id):
            logger.warning(f"Agent {agent_id} is already in team {self.id}")
            return False

        member = TeamMember(
            agent_id=agent_id,
            role=role,
            capabilities=capabilities or [],
        )
        self.members.append(member)
        logger.info(f"Added agent {agent_id} with role {role.value} to team {self.id}")
        return True

    def remove_member(self, agent_id: str) -> bool:
        """Remove a member from the team.

        Args:
            agent_id: Agent ID to remove.

        Returns:
            True if member was removed, False if not found.
        """
        for i, member in enumerate(self.members):
            if member.agent_id == agent_id:
                self.members.pop(i)
                logger.info(f"Removed agent {agent_id} from team {self.id}")
                return True
        return False

    def update_member_role(self, agent_id: str, new_role: AgentRole) -> bool:
        """Update a member's role.

        Args:
            agent_id: Agent ID to update.
            new_role: New role for the member.

        Returns:
            True if role was updated, False if member not found.
        """
        member = self.get_member(agent_id)
        if member:
            old_role = member.role
            member.role = new_role
            logger.info(f"Updated agent {agent_id} role from {old_role.value} to {new_role.value}")
            return True
        return False

    def update_member_status(self, agent_id: str, status: str) -> bool:
        """Update a member's status.

        Args:
            agent_id: Agent ID to update.
            status: New status for the member.

        Returns:
            True if status was updated, False if member not found.
        """
        member = self.get_member(agent_id)
        if member:
            member.status = status
            return True
        return False

    def increment_member_load(self, agent_id: str) -> bool:
        """Increment a member's task load.

        Args:
            agent_id: Agent ID to update.

        Returns:
            True if load was incremented, False if member not found.
        """
        member = self.get_member(agent_id)
        if member:
            member.load += 1
            return True
        return False

    def decrement_member_load(self, agent_id: str) -> bool:
        """Decrement a member's task load.

        Args:
            agent_id: Agent ID to update.

        Returns:
            True if load was decremented, False if member not found.
        """
        member = self.get_member(agent_id)
        if member:
            member.load = max(0, member.load - 1)
            return True
        return False

    def get_active_members(self) -> list[TeamMember]:
        """Get all active members.

        Returns:
            List of members with active status.
        """
        return [m for m in self.members if m.status == "active"]

    def get_available_members(self) -> list[TeamMember]:
        """Get all available members (idle or low load).

        Returns:
            List of available members.
        """
        return [m for m in self.members if m.status in ("idle", "active") and m.load < 3]


@dataclass
class TeamResult:
    """Result of team execution.

    Attributes:
        team_id: ID of the team that executed.
        success: Whether execution was successful.
        results: Task results by task ID.
        assignments: Task assignments by task ID.
        duration: Execution duration in seconds.
        metadata: Additional result metadata.
    """

    team_id: str = ""
    success: bool = False
    results: dict[str, Any] = field(default_factory=dict)
    assignments: dict[str, Assignment] = field(default_factory=dict)
    duration: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "team_id": self.team_id,
            "success": self.success,
            "results": self.results,
            "assignments": {k: v.to_dict() for k, v in self.assignments.items()},
            "duration": self.duration,
            "metadata": self.metadata,
        }


class TeamManager:
    """Manages multiple teams and their lifecycle.

    Provides team creation, management, and tracking functionality.
    """

    def __init__(self, max_teams: int = 10):
        """Initialize the team manager.

        Args:
            max_teams: Maximum number of concurrent teams.
        """
        self.max_teams = max_teams
        self._teams: dict[str, Team] = {}
        self._results: dict[str, TeamResult] = {}
        self._team_history: list[Team] = []

    def create_team(
        self,
        name: str,
        config: TeamConfig | None = None,
        members: list[tuple[str, AgentRole]] | None = None,
    ) -> Team:
        """Create a new team.

        Args:
            name: Team name.
            config: Optional team configuration.
            members: Optional list of (agent_id, role) tuples.

        Returns:
            Created team.
        """
        if len(self._teams) >= self.max_teams:
            raise RuntimeError(f"Maximum teams ({self.max_teams}) reached")

        config = config or TeamConfig(name=name)
        team = Team(
            name=name,
            config=config,
        )

        if members:
            for agent_id, role in members:
                team.add_member(agent_id, role)

        self._teams[team.id] = team
        logger.info(f"Created team {team.id} with name '{name}'")
        return team

    def get_team(self, team_id: str) -> Team | None:
        """Get a team by ID.

        Args:
            team_id: Team ID to look up.

        Returns:
            Team if found, None otherwise.
        """
        return self._teams.get(team_id)

    def list_teams(self, status: TeamStatus | None = None) -> list[Team]:
        """List all teams, optionally filtered by status.

        Args:
            status: Optional status to filter by.

        Returns:
            List of teams.
        """
        teams = list(self._teams.values())
        if status:
            teams = [t for t in teams if t.status == status]
        return teams

    def disband_team(self, team_id: str) -> bool:
        """Disband a team.

        Args:
            team_id: Team ID to disband.

        Returns:
            True if team was disbanded, False if not found.
        """
        team = self._teams.get(team_id)
        if not team:
            return False

        team.status = TeamStatus.DISBANDED
        self._team_history.append(team)
        del self._teams[team_id]

        logger.info(f"Disbanded team {team_id}")
        return True

    def record_result(self, team_id: str, result: TeamResult) -> None:
        """Record a team execution result.

        Args:
            team_id: Team ID.
            result: Team execution result.
        """
        self._results[team_id] = result

        team = self._teams.get(team_id)
        if team:
            if result.success:
                team.status = TeamStatus.COMPLETED
            else:
                team.status = TeamStatus.FAILED
            team.tasks_completed += len(result.results)

    def get_result(self, team_id: str) -> TeamResult | None:
        """Get a team's result.

        Args:
            team_id: Team ID.

        Returns:
            TeamResult if found, None otherwise.
        """
        return self._results.get(team_id)

    def get_stats(self) -> dict[str, Any]:
        """Get team management statistics.

        Returns:
            Dictionary with statistics.
        """
        status_counts: dict[str, int] = {}
        for team in self._teams.values():
            status_key = team.status.value
            status_counts[status_key] = status_counts.get(status_key, 0) + 1

        return {
            "total_teams": len(self._teams),
            "max_teams": self.max_teams,
            "disbanded_teams": len(self._team_history),
            "by_status": status_counts,
            "total_results": len(self._results),
        }

    def clear_history(self) -> None:
        """Clear team history."""
        self._team_history.clear()
