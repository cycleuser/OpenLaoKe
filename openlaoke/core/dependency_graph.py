"""Dependency graph for plan steps - enables parallel execution of independent steps.

Inspired by smallcode's dependency_graph.js.
Analyzes plan steps for file overlaps and produces execution groups.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import StrEnum


class DepKind(StrEnum):
    FILE_OVERLAP = "file_overlap"
    SEQUENTIAL = "sequential"
    SAME_FILE = "same_file"
    NONE = "none"


@dataclass
class PlanStep:
    step_id: int
    description: str
    files_touched: list[str] = field(default_factory=list)
    tools_used: list[str] = field(default_factory=list)
    depends_on: list[int] = field(default_factory=list)


@dataclass
class ExecutionGroup:
    group_id: int
    step_ids: list[int]
    can_parallelize: bool = True


_FILE_PATTERN = re.compile(r'(?:file|path|module)[\s:=]+["\']?([^\s"\')\],;]+)', re.IGNORECASE)
_FILE_EXT = re.compile(r'\b(\w+\.(?:py|js|ts|rs|go|java|cpp|c|h|hpp|css|html|json|yaml|yml|toml|md|txt))\b')


def parse_plan(text: str) -> list[PlanStep]:
    """Parse a numbered plan into structured steps with file detection."""
    steps: list[PlanStep] = []

    pattern = re.compile(r"(?:^|\n)\s*(\d+)[.)]\s*(.+)")
    for match in pattern.finditer(text):
        step_id = int(match.group(1))
        description = match.group(2).strip()

        files: list[str] = []
        for m in _FILE_PATTERN.finditer(description):
            files.append(m.group(1))
        for m in _FILE_EXT.finditer(description):
            f = m.group(1)
            if f not in files:
                files.append(f)

        tools = _detect_tools(description)
        steps.append(PlanStep(step_id=step_id, description=description, files_touched=files, tools_used=tools))

    return steps


def _detect_tools(description: str) -> list[str]:
    tools = []
    tool_patterns = [
        (r'\b(?:read|view|open)\b', 'read_file'),
        (r'\b(?:write|create|make|generate)\b', 'write_file'),
        (r'\b(?:edit|modify|change|update|fix|patch)\b', 'edit_file'),
        (r'\b(?:run|execute|test|build)\b', 'bash'),
        (r'\b(?:find|search|locate)\b', 'search'),
        (r'\b(?:install|setup|configure)\b', 'install'),
    ]
    for pattern, tool in tool_patterns:
        if re.search(pattern, description, re.IGNORECASE) and tool not in tools:
            tools.append(tool)
    return tools


def build_dependency_graph(steps: list[PlanStep]) -> list[ExecutionGroup]:
    """Build execution groups from plan steps based on file dependencies.

    Steps that touch different files can run in parallel.
    Steps touching the same files must run sequentially.
    """
    if not steps:
        return []

    groups: list[ExecutionGroup] = []
    current_group = ExecutionGroup(group_id=0, step_ids=[], can_parallelize=True)
    touched_files: set[str] = set()

    for step in steps:
        step_files = set(step.files_touched)

        # If no files specified, treat as sequential (play it safe)
        if not step_files:
            new_group = ExecutionGroup(
                group_id=len(groups), step_ids=[step.step_id], can_parallelize=False
            )
            groups.append(new_group)
            continue

        # Check for file overlap with current group
        if step_files & touched_files:
            new_group = ExecutionGroup(
                group_id=len(groups), step_ids=[step.step_id], can_parallelize=False
            )
            groups.append(new_group)
            touched_files = step_files
        else:
            if current_group.step_ids:
                groups.append(current_group)
                current_group = ExecutionGroup(
                    group_id=len(groups), step_ids=[], can_parallelize=True
                )
            current_group.step_ids.append(step.step_id)
            touched_files |= step_files

    if current_group.step_ids:
        groups.append(current_group)

    # Mark groups with >1 step as parallelizable
    for g in groups:
        if len(g.step_ids) > 1:
            g.can_parallelize = True

    return groups


def find_parallel_steps(steps: list[PlanStep]) -> list[list[int]]:
    """Find groups of steps that can be executed in parallel."""
    groups = build_dependency_graph(steps)
    return [g.step_ids for g in groups if g.can_parallelize and len(g.step_ids) > 1]
