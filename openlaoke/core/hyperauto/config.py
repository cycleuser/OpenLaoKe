"""Configuration for HyperAuto system."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlaoke.core.hyperauto.types import HyperAutoMode


@dataclass
class HyperAutoConfig:
    """Configuration for HyperAuto agent.

    Attributes:
        mode: Operating mode (semi_auto, full_auto, hyper_auto)
        max_iterations: Maximum number of iterations before stopping
        auto_create_skills: Automatically create skills when needed
        auto_init_projects: Automatically initialize project structures
        auto_search_code: Automatically search for relevant code
        auto_install_deps: Automatically install dependencies
        auto_run_tests: Automatically run tests after changes
        auto_commit: Automatically commit changes (default: False for safety)
        confidence_threshold: Minimum confidence for auto-decisions
        reflection_enabled: Enable self-reflection after tasks
        learning_enabled: Enable learning from past executions
        max_parallel_tasks: Maximum parallel sub-tasks
        timeout_per_task: Timeout in seconds per sub-task
        rollback_on_failure: Rollback changes on failure
        dry_run: Simulate without making actual changes
        verbose: Enable verbose logging
        skill_templates: Templates for auto-generated skills
        project_templates: Templates for project initialization
    """

    mode: HyperAutoMode = HyperAutoMode.FULL_AUTO
    max_iterations: int = 100
    auto_create_skills: bool = True
    auto_init_projects: bool = True
    auto_search_code: bool = True
    auto_install_deps: bool = True
    auto_run_tests: bool = True
    auto_commit: bool = False
    confidence_threshold: float = 0.8
    reflection_enabled: bool = True
    learning_enabled: bool = True
    max_parallel_tasks: int = 5
    timeout_per_task: float = 300.0
    rollback_on_failure: bool = True
    dry_run: bool = False
    verbose: bool = False
    skill_templates: dict[str, str] = field(default_factory=dict)
    project_templates: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "max_iterations": self.max_iterations,
            "auto_create_skills": self.auto_create_skills,
            "auto_init_projects": self.auto_init_projects,
            "auto_search_code": self.auto_search_code,
            "auto_install_deps": self.auto_install_deps,
            "auto_run_tests": self.auto_run_tests,
            "auto_commit": self.auto_commit,
            "confidence_threshold": self.confidence_threshold,
            "reflection_enabled": self.reflection_enabled,
            "learning_enabled": self.learning_enabled,
            "max_parallel_tasks": self.max_parallel_tasks,
            "timeout_per_task": self.timeout_per_task,
            "rollback_on_failure": self.rollback_on_failure,
            "dry_run": self.dry_run,
            "verbose": self.verbose,
            "skill_templates": self.skill_templates,
            "project_templates": self.project_templates,
        }

    @classmethod
    def semi_auto(cls) -> HyperAutoConfig:
        """Create a semi-auto config (asks for confirmation)."""
        return cls(
            mode=HyperAutoMode.SEMI_AUTO,
            confidence_threshold=1.0,
            max_parallel_tasks=1,
            verbose=True,
        )

    @classmethod
    def full_auto(cls) -> HyperAutoConfig:
        """Create a full-auto config (autonomous with safety limits)."""
        return cls(
            mode=HyperAutoMode.FULL_AUTO,
            confidence_threshold=0.8,
            max_parallel_tasks=5,
        )

    @classmethod
    def hyper_auto(cls) -> HyperAutoConfig:
        """Create a hyper-auto config (maximum autonomy)."""
        return cls(
            mode=HyperAutoMode.HYPER_AUTO,
            confidence_threshold=0.6,
            max_parallel_tasks=10,
            auto_commit=True,
            reflection_enabled=True,
            learning_enabled=True,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> HyperAutoConfig:
        """Create config from dictionary."""
        mode_str = data.get("mode", "full_auto")
        mode = HyperAutoMode(mode_str) if isinstance(mode_str, str) else HyperAutoMode.FULL_AUTO

        return cls(
            mode=mode,
            max_iterations=data.get("max_iterations", 100),
            auto_create_skills=data.get("auto_create_skills", True),
            auto_init_projects=data.get("auto_init_projects", True),
            auto_search_code=data.get("auto_search_code", True),
            auto_install_deps=data.get("auto_install_deps", True),
            auto_run_tests=data.get("auto_run_tests", True),
            auto_commit=data.get("auto_commit", False),
            confidence_threshold=data.get("confidence_threshold", 0.8),
            reflection_enabled=data.get("reflection_enabled", True),
            learning_enabled=data.get("learning_enabled", True),
            max_parallel_tasks=data.get("max_parallel_tasks", 5),
            timeout_per_task=data.get("timeout_per_task", 300.0),
            rollback_on_failure=data.get("rollback_on_failure", True),
            dry_run=data.get("dry_run", False),
            verbose=data.get("verbose", False),
            skill_templates=data.get("skill_templates", {}),
            project_templates=data.get("project_templates", {}),
        )
