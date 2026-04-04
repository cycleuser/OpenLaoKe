"""Auto-generate skills based on task analysis.

This module provides automatic skill generation capabilities:
1. Analyze skill requirements from task descriptions
2. Design skill templates automatically
3. Generate SKILL.md files
4. Validate generated skills
5. Register new skills to the system
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import yaml

from openlaoke.core.skill_system import Skill, SkillRegistry, get_skill_registry, rescan_skills
from openlaoke.types.core_types import ValidationResult


@dataclass
class SkillParameter:
    """A parameter definition for a skill."""

    name: str
    type: str = "string"
    required: bool = True
    description: str = ""
    default: str | None = None
    choices: list[str] = field(default_factory=list)


@dataclass
class SkillTrigger:
    """A trigger pattern for skill activation."""

    command: str
    description: str = ""
    examples: list[str] = field(default_factory=list)


@dataclass
class SkillRequirement:
    """Identified requirement for a new skill."""

    task_type: str
    description: str
    keywords: list[str] = field(default_factory=list)
    suggested_tools: list[str] = field(default_factory=list)
    complexity: str = "medium"
    requires_files: bool = False
    requires_network: bool = False
    requires_code_analysis: bool = False


@dataclass
class SkillDesign:
    """Design specification for a skill to generate."""

    name: str
    description: str
    version: str = "1.0.0"
    triggers: list[SkillTrigger] = field(default_factory=list)
    parameters: list[SkillParameter] = field(default_factory=list)
    when_to_use: str = ""
    capabilities: list[str] = field(default_factory=list)
    prerequisites: list[str] = field(default_factory=list)
    examples: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    workflow_steps: list[str] = field(default_factory=list)


@dataclass
class GenerationResult:
    """Result of skill generation."""

    success: bool
    skill_name: str = ""
    skill_path: Path | None = None
    message: str = ""
    errors: list[str] = field(default_factory=list)


class SkillGenerator:
    """Automatically generate skills based on task analysis."""

    TASK_PATTERNS: dict[str, dict[str, Any]] = {
        "code_review": {
            "keywords": ["review", "code review", "check code", "analyze code", "pr review"],
            "tools": ["read", "grep", "glob", "bash"],
            "complexity": "medium",
        },
        "testing": {
            "keywords": ["test", "testing", "write tests", "add tests", "unit test"],
            "tools": ["bash", "read", "write", "glob"],
            "complexity": "medium",
        },
        "refactoring": {
            "keywords": ["refactor", "restructure", "clean up", "improve code"],
            "tools": ["read", "edit", "bash", "grep"],
            "complexity": "high",
        },
        "documentation": {
            "keywords": ["document", "docs", "readme", "documentation", "docstring"],
            "tools": ["read", "write", "glob", "grep"],
            "complexity": "low",
        },
        "debugging": {
            "keywords": ["debug", "fix bug", "error", "issue", "problem", "traceback"],
            "tools": ["bash", "read", "grep", "glob"],
            "complexity": "high",
        },
        "deployment": {
            "keywords": ["deploy", "deployment", "release", "ship", "publish"],
            "tools": ["bash", "read", "write"],
            "complexity": "high",
        },
        "git_workflow": {
            "keywords": ["git", "commit", "branch", "merge", "rebase", "pull request"],
            "tools": ["bash"],
            "complexity": "medium",
        },
        "project_setup": {
            "keywords": ["setup", "initialize", "create project", "scaffold", "new project"],
            "tools": ["bash", "write", "glob"],
            "complexity": "medium",
        },
        "api_integration": {
            "keywords": ["api", "integration", "http", "request", "endpoint", "rest"],
            "tools": ["bash", "read", "write", "webfetch"],
            "complexity": "high",
        },
        "code_generation": {
            "keywords": ["generate", "create code", "write code", "scaffold"],
            "tools": ["write", "read", "glob"],
            "complexity": "medium",
        },
    }

    TOOL_DESCRIPTIONS: dict[str, str] = {
        "read": "Read files from the filesystem",
        "write": "Write files to the filesystem",
        "edit": "Edit existing files",
        "bash": "Execute shell commands",
        "grep": "Search file contents",
        "glob": "Find files by pattern",
        "webfetch": "Fetch content from URLs",
        "skill": "Load specialized skills",
    }

    def __init__(self, skill_dir: Path | None = None):
        self.skill_dir = skill_dir or Path.home() / ".openlaoke" / "skills"
        self.skill_dir.mkdir(parents=True, exist_ok=True)
        self._registry: SkillRegistry | None = None

    @property
    def registry(self) -> SkillRegistry:
        """Get or initialize the skill registry."""
        if self._registry is None:
            self._registry = get_skill_registry()
        return self._registry

    def analyze_skill_needs(self, task_description: str) -> list[SkillRequirement]:
        """Analyze a task description to identify required skills.

        Args:
            task_description: Natural language description of the task

        Returns:
            List of identified skill requirements
        """
        requirements: list[SkillRequirement] = []
        task_lower = task_description.lower()
        matched_patterns: set[str] = set()

        for pattern_name, pattern_info in self.TASK_PATTERNS.items():
            keywords = pattern_info.get("keywords", [])
            matched_keywords = [kw for kw in keywords if kw in task_lower]

            if matched_keywords:
                requirement = SkillRequirement(
                    task_type=pattern_name,
                    description=f"Task involves {pattern_name.replace('_', ' ')}",
                    keywords=matched_keywords,
                    suggested_tools=pattern_info.get("tools", []),
                    complexity=pattern_info.get("complexity", "medium"),
                    requires_code_analysis=pattern_name
                    in ["code_review", "refactoring", "debugging"],
                    requires_network=pattern_name == "api_integration",
                    requires_files=pattern_name not in ["git_workflow"],
                )
                requirements.append(requirement)
                matched_patterns.add(pattern_name)

        if not requirements:
            inferred = self._infer_requirement_from_text(task_description)
            if inferred:
                requirements.append(inferred)

        return requirements

    def _infer_requirement_from_text(self, text: str) -> SkillRequirement | None:
        """Infer skill requirements from arbitrary text."""
        text_lower = text.lower()

        tools: list[str] = []
        if any(w in text_lower for w in ["file", "read", "write", "edit"]):
            tools.extend(["read", "write", "edit"])
        if any(w in text_lower for w in ["command", "run", "execute", "shell"]):
            tools.append("bash")
        if any(w in text_lower for w in ["search", "find", "grep", "pattern"]):
            tools.extend(["grep", "glob"])
        if any(w in text_lower for w in ["url", "http", "web", "api", "fetch"]):
            tools.append("webfetch")

        if not tools:
            tools = ["bash", "read", "write"]

        return SkillRequirement(
            task_type="custom",
            description=f"Custom task: {text[:100]}",
            keywords=[w for w in text.split()[:5] if len(w) > 3],
            suggested_tools=list(set(tools)),
            complexity="medium",
        )

    def design_skill(self, requirement: SkillRequirement, custom_name: str = "") -> SkillDesign:
        """Design a skill based on requirements.

        Args:
            requirement: The skill requirement to design for
            custom_name: Optional custom name for the skill

        Returns:
            SkillDesign object with the skill specification
        """
        name = custom_name or self._generate_skill_name(requirement)

        description = self._generate_description(requirement)

        triggers = self._generate_triggers(requirement, name)

        parameters = self._generate_parameters(requirement)

        when_to_use = self._generate_when_to_use(requirement)

        capabilities = self._generate_capabilities(requirement)

        workflow_steps = self._generate_workflow(requirement)

        return SkillDesign(
            name=name,
            description=description,
            triggers=triggers,
            parameters=parameters,
            when_to_use=when_to_use,
            capabilities=capabilities,
            allowed_tools=requirement.suggested_tools,
            workflow_steps=workflow_steps,
        )

    def _generate_skill_name(self, requirement: SkillRequirement) -> str:
        """Generate a skill name from requirements."""
        base_name = requirement.task_type.replace(" ", "-").replace("_", "-")
        timestamp = datetime.now().strftime("%Y%m%d%H%M")
        return f"auto-{base_name}-{timestamp}"

    def _generate_description(self, requirement: SkillRequirement) -> str:
        """Generate skill description."""
        task_type = requirement.task_type.replace("_", " ")
        complexity = requirement.complexity

        desc_parts = [f"Auto-generated skill for {task_type} tasks."]

        if requirement.keywords:
            keywords_str = ", ".join(requirement.keywords[:3])
            desc_parts.append(f"Keywords: {keywords_str}.")

        desc_parts.append(f"Complexity: {complexity}.")

        if requirement.requires_code_analysis:
            desc_parts.append("Requires code analysis capabilities.")

        if requirement.requires_network:
            desc_parts.append("Requires network access.")

        return " ".join(desc_parts)

    def _generate_triggers(self, requirement: SkillRequirement, name: str) -> list[SkillTrigger]:
        """Generate command triggers for the skill."""
        triggers: list[SkillTrigger] = []

        base_cmd = f"/{name.replace('auto-', '').split('-')[0]}"

        for keyword in requirement.keywords[:3]:
            cmd = f"/{keyword.replace(' ', '-').lower()}"
            trigger = SkillTrigger(
                command=cmd,
                description=f"Trigger when user mentions '{keyword}'",
                examples=[f"{cmd} <args>"],
            )
            triggers.append(trigger)

        triggers.append(
            SkillTrigger(
                command=base_cmd,
                description=f"Primary command for {requirement.task_type}",
                examples=[f"{base_cmd} [options]"],
            )
        )

        return triggers

    def _generate_parameters(self, requirement: SkillRequirement) -> list[SkillParameter]:
        """Generate parameters based on task type."""
        params: list[SkillParameter] = []

        if requirement.requires_files:
            params.append(
                SkillParameter(
                    name="target",
                    type="string",
                    required=True,
                    description="Target file or directory path",
                )
            )

        if requirement.requires_code_analysis:
            params.extend(
                [
                    SkillParameter(
                        name="scope",
                        type="string",
                        required=False,
                        description="Scope of analysis (file, directory, project)",
                        default="file",
                        choices=["file", "directory", "project"],
                    ),
                    SkillParameter(
                        name="depth",
                        type="integer",
                        required=False,
                        description="Analysis depth level",
                        default="1",
                    ),
                ]
            )

        if requirement.requires_network:
            params.append(
                SkillParameter(
                    name="url",
                    type="string",
                    required=False,
                    description="Target URL for network operations",
                )
            )

        params.append(
            SkillParameter(
                name="verbose",
                type="boolean",
                required=False,
                description="Enable verbose output",
                default="false",
            )
        )

        return params

    def _generate_when_to_use(self, requirement: SkillRequirement) -> str:
        """Generate when-to-use description."""
        parts = [f"Use when the task involves {requirement.task_type.replace('_', ' ')}."]

        if requirement.keywords:
            keywords = ", ".join(f'"{kw}"' for kw in requirement.keywords[:4])
            parts.append(f"Triggered by keywords: {keywords}.")

        if requirement.complexity == "high":
            parts.append("Recommended for complex tasks requiring careful analysis.")

        return " ".join(parts)

    def _generate_capabilities(self, requirement: SkillRequirement) -> list[str]:
        """Generate list of capabilities."""
        capabilities: list[str] = []

        for tool in requirement.suggested_tools:
            desc = self.TOOL_DESCRIPTIONS.get(tool, f"Use {tool} tool")
            capabilities.append(desc)

        if requirement.requires_code_analysis:
            capabilities.extend(
                [
                    "Analyze code structure and patterns",
                    "Identify potential issues",
                    "Generate improvement suggestions",
                ]
            )

        if requirement.requires_network:
            capabilities.extend(
                [
                    "Make HTTP requests",
                    "Fetch remote content",
                    "Process API responses",
                ]
            )

        capabilities.append("Execute multi-step workflows")

        return list(set(capabilities))

    def _generate_workflow(self, requirement: SkillRequirement) -> list[str]:
        """Generate workflow steps."""
        steps: list[str] = []

        task_type = requirement.task_type

        if task_type == "code_review":
            steps = [
                "Read and understand the target code",
                "Analyze code structure and patterns",
                "Check for potential issues and bugs",
                "Verify coding standards compliance",
                "Generate review feedback",
            ]
        elif task_type == "testing":
            steps = [
                "Analyze existing code structure",
                "Identify test cases to implement",
                "Write comprehensive tests",
                "Run tests to verify functionality",
                "Fix any failing tests",
            ]
        elif task_type == "debugging":
            steps = [
                "Reproduce the issue",
                "Analyze error messages and logs",
                "Identify root cause",
                "Implement fix",
                "Verify the fix works",
            ]
        elif task_type == "documentation":
            steps = [
                "Analyze code structure",
                "Generate documentation content",
                "Write documentation files",
                "Verify documentation accuracy",
            ]
        elif task_type == "refactoring":
            steps = [
                "Analyze current code structure",
                "Design refactoring approach",
                "Apply refactoring changes",
                "Run tests to verify changes",
                "Clean up and optimize",
            ]
        else:
            steps = [
                "Analyze task requirements",
                "Plan execution approach",
                "Execute main workflow",
                "Verify results",
                "Report completion",
            ]

        return steps

    def generate_skill_content(self, design: SkillDesign) -> str:
        """Generate SKILL.md content from design.

        Args:
            design: The skill design specification

        Returns:
            Complete SKILL.md file content
        """
        frontmatter = self._generate_frontmatter(design)
        content = self._generate_content(design)

        return f"---\n{frontmatter}\n---\n\n{content}"

    def _generate_frontmatter(self, design: SkillDesign) -> str:
        """Generate YAML frontmatter."""
        metadata: dict[str, Any] = {
            "name": design.name,
            "description": design.description,
            "version": design.version,
        }

        if design.triggers:
            metadata["triggers"] = [
                {"command": t.command, "description": t.description} for t in design.triggers
            ]

        if design.parameters:
            metadata["parameters"] = [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "description": p.description,
                    **({"default": p.default} if p.default else {}),
                    **({"choices": p.choices} if p.choices else {}),
                }
                for p in design.parameters
            ]

        if design.allowed_tools:
            metadata["allowed-tools"] = design.allowed_tools

        return cast(str, yaml.dump(metadata, default_flow_style=False, sort_keys=False).strip())

    def _generate_content(self, design: SkillDesign) -> str:
        """Generate skill content body."""
        sections: list[str] = []

        sections.append(f"# {design.name.replace('-', ' ').title()}\n")
        sections.append(f"{design.description}\n")

        if design.when_to_use:
            sections.append("## When to Use\n")
            sections.append(f"{design.when_to_use}\n")

        if design.capabilities:
            sections.append("## Capabilities\n")
            for cap in design.capabilities:
                sections.append(f"- {cap}")
            sections.append("")

        if design.workflow_steps:
            sections.append("## Workflow\n")
            for i, step in enumerate(design.workflow_steps, 1):
                sections.append(f"{i}. {step}")
            sections.append("")

        if design.parameters:
            sections.append("## Parameters\n")
            for param in design.parameters:
                req_str = "required" if param.required else "optional"
                sections.append(
                    f"- **{param.name}** ({param.type}, {req_str}): {param.description}"
                )
                if param.default:
                    sections.append(f"  - Default: `{param.default}`")
                if param.choices:
                    sections.append(f"  - Choices: {', '.join(param.choices)}")
            sections.append("")

        if design.triggers:
            sections.append("## Triggers\n")
            for trigger in design.triggers:
                sections.append(f"- `{trigger.command}`: {trigger.description}")
            sections.append("")

        if design.examples:
            sections.append("## Examples\n")
            for example in design.examples:
                sections.append(f"```\n{example}\n```\n")

        sections.append("---\n")
        sections.append("*This skill was auto-generated by SkillGenerator.*\n")

        return "\n".join(sections)

    def validate_skill(self, content: str) -> ValidationResult:
        """Validate generated skill content.

        Args:
            content: The skill content to validate

        Returns:
            ValidationResult indicating success or failure
        """
        errors: list[str] = []

        if not content or len(content.strip()) < 50:
            return ValidationResult(
                result=False,
                message="Skill content is too short",
                error_code=1,
            )

        if not content.startswith("---"):
            errors.append("Missing YAML frontmatter")

        parts = content.split("---", 2)
        if len(parts) < 3:
            errors.append("Invalid frontmatter format")

        if len(parts) >= 3:
            frontmatter = parts[1].strip()
            try:
                metadata = yaml.safe_load(frontmatter)
                if not metadata:
                    errors.append("Empty frontmatter")
                else:
                    if "name" not in metadata:
                        errors.append("Missing 'name' in frontmatter")
                    if "description" not in metadata:
                        errors.append("Missing 'description' in frontmatter")
            except yaml.YAMLError as e:
                errors.append(f"Invalid YAML in frontmatter: {e}")

        body = parts[2].strip() if len(parts) >= 3 else content

        if len(body) < 100:
            errors.append("Skill body content is too short")

        if not re.search(r"^#+\s+", body, re.MULTILINE):
            errors.append("Missing markdown headers in body")

        if errors:
            return ValidationResult(
                result=False,
                message="; ".join(errors),
                error_code=2,
            )

        return ValidationResult(result=True, message="Skill validation passed")

    def register_skill(self, content: str, name: str, overwrite: bool = False) -> GenerationResult:
        """Register a new skill to the system.

        Args:
            content: The SKILL.md content
            name: Name for the skill
            overwrite: Whether to overwrite existing skill

        Returns:
            GenerationResult with registration status
        """
        skill_path = self.skill_dir / name / "SKILL.md"

        if skill_path.exists() and not overwrite:
            return GenerationResult(
                success=False,
                skill_name=name,
                skill_path=skill_path,
                message=f"Skill '{name}' already exists. Use overwrite=True to replace.",
                errors=["Skill already exists"],
            )

        validation = self.validate_skill(content)
        if not validation.result:
            return GenerationResult(
                success=False,
                skill_name=name,
                message=f"Validation failed: {validation.message}",
                errors=[validation.message],
            )

        try:
            skill_path.parent.mkdir(parents=True, exist_ok=True)
            skill_path.write_text(content, encoding="utf-8")

            skill_count = rescan_skills()

            return GenerationResult(
                success=True,
                skill_name=name,
                skill_path=skill_path,
                message=f"Skill '{name}' registered successfully. Total skills: {skill_count}",
            )

        except Exception as e:
            return GenerationResult(
                success=False,
                skill_name=name,
                message=f"Failed to register skill: {e}",
                errors=[str(e)],
            )

    def auto_generate_for_task(
        self,
        task: str,
        custom_name: str = "",
        register: bool = True,
    ) -> list[Skill]:
        """Auto-generate skills for a given task.

        This is the main entry point for automatic skill generation.

        Args:
            task: Task description to analyze
            custom_name: Optional custom name for the skill
            register: Whether to register generated skills

        Returns:
            List of generated Skill objects
        """
        requirements = self.analyze_skill_needs(task)
        generated_skills: list[Skill] = []

        for requirement in requirements:
            design = self.design_skill(requirement, custom_name)
            content = self.generate_skill_content(design)

            if register:
                result = self.register_skill(content, design.name)
                if result.success:
                    skill = Skill.from_content(content, result.skill_path)
                    if skill:
                        generated_skills.append(skill)
            else:
                skill = Skill.from_content(content)
                if skill:
                    generated_skills.append(skill)

        return generated_skills

    def generate_skill_from_template(
        self,
        name: str,
        description: str,
        triggers: list[str] | None = None,
        capabilities: list[str] | None = None,
        workflow: list[str] | None = None,
        tools: list[str] | None = None,
        when_to_use: str = "",
        parameters: list[dict[str, Any]] | None = None,
    ) -> GenerationResult:
        """Generate a skill from explicit template parameters.

        Args:
            name: Skill name
            description: Skill description
            triggers: List of trigger commands
            capabilities: List of capabilities
            workflow: List of workflow steps
            tools: List of allowed tools
            when_to_use: When to use description
            parameters: List of parameter definitions

        Returns:
            GenerationResult with generation status
        """
        design = SkillDesign(
            name=name,
            description=description,
            when_to_use=when_to_use or f"Use when you need to {description.lower()}",
            capabilities=capabilities or ["Execute tasks"],
            allowed_tools=tools or ["bash", "read", "write"],
            workflow_steps=workflow or ["Execute task", "Verify results"],
        )

        if triggers:
            design.triggers = [
                SkillTrigger(command=t, description=f"Trigger for {t}") for t in triggers
            ]

        if parameters:
            design.parameters = [
                SkillParameter(
                    name=p.get("name", "param"),
                    type=p.get("type", "string"),
                    required=p.get("required", True),
                    description=p.get("description", ""),
                    default=p.get("default"),
                    choices=p.get("choices", []),
                )
                for p in parameters
            ]

        content = self.generate_skill_content(design)
        return self.register_skill(content, name)

    def list_generated_skills(self) -> list[dict[str, Any]]:
        """List all auto-generated skills."""
        skills: list[dict[str, Any]] = []

        if not self.skill_dir.exists():
            return skills

        for skill_dir in sorted(self.skill_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue

            content = skill_file.read_text(encoding="utf-8")

            if "auto-generated by SkillGenerator" in content.lower():
                skill = Skill.from_file(skill_file)
                if skill:
                    skills.append(
                        {
                            "name": skill.name,
                            "description": skill.description,
                            "path": str(skill_file),
                        }
                    )

        return skills

    def remove_generated_skill(self, name: str) -> bool:
        """Remove an auto-generated skill.

        Args:
            name: Name of the skill to remove

        Returns:
            True if removed successfully
        """
        import shutil

        skill_path = self.skill_dir / name
        if skill_path.exists():
            shutil.rmtree(skill_path)
            rescan_skills()
            return True
        return False
