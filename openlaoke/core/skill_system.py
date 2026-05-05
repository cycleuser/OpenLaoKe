"""Skill system for loading and managing agent skills.

Compatible with Claude Code and OpenCode skill formats.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


def _sanitize_frontmatter(frontmatter: str) -> str:
    """Sanitize YAML frontmatter that contains invalid syntax.

    Mirrors OpenCode's fallbackSanitization: when a value contains colons,
    convert it to a block scalar (|-) so the YAML parser can handle it.
    """
    lines = frontmatter.splitlines()
    result = []

    for line in lines:
        stripped = line.strip()

        # Skip comments and empty lines
        if stripped.startswith("#") or stripped == "":
            result.append(line)
            continue

        # Skip continuation lines (indented)
        if line.startswith((" ", "\t")):
            result.append(line)
            continue

        # Match key: value pattern
        kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)$", line)
        if not kv:
            result.append(line)
            continue

        key = kv.group(1)
        value = kv.group(2).strip()

        # Skip if value is empty, already quoted, or uses block scalar
        if not value or value in (">", "|") or value.startswith(('"', "'")):
            result.append(line)
            continue

        # If value contains a colon, convert to block scalar
        if ":" in value:
            result.append(f"{key}: |-")
            result.append(f"  {value}")
            continue

        result.append(line)

    return "\n".join(result)


@dataclass
class Skill:
    """A skill definition loaded from SKILL.md file."""

    name: str
    description: str = ""
    version: str = "1.0.0"
    allowed_tools: list[str] = field(default_factory=list)
    content: str = ""
    path: Path | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> Skill | None:
        """Load a skill from SKILL.md file."""
        if not path.exists():
            return None

        try:
            content = path.read_text(encoding="utf-8")
            return cls.from_content(content, path)
        except Exception as e:
            print(f"Error loading skill {path}: {e}")
            return None

    @classmethod
    def from_content(cls, content: str, path: Path | None = None) -> Skill:
        """Parse skill from content string."""
        metadata: dict[str, str] = {}
        body = content

        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                body = parts[2].strip()

                # Try parsing YAML directly first
                try:
                    metadata = yaml.safe_load(frontmatter) or {}
                except yaml.YAMLError:
                    # Fallback: sanitize frontmatter like OpenCode does
                    try:
                        sanitized = _sanitize_frontmatter(frontmatter)
                        metadata = yaml.safe_load(sanitized) or {}
                    except yaml.YAMLError:
                        # Last resort: manual key-value extraction
                        metadata = cls._extract_frontmatter_manual(frontmatter)

        # Determine skill name: prefer frontmatter, fallback to directory name
        name = metadata.get("name", "")
        if not name or name == "SKILL":
            # Use parent directory name as fallback
            if path and path.parent:
                name = path.parent.name
            elif path:
                name = path.stem
            else:
                name = "unknown"

        description = metadata.get("description", "")
        if isinstance(description, str):
            description = description.strip()
        version = metadata.get("version", "1.0.0")
        _raw_tools: str | list[str] = metadata.get(
            "allowed-tools", metadata.get("allowed_tools", [])
        )
        allowed_tools: list[str] = _raw_tools if isinstance(_raw_tools, list) else [str(_raw_tools)]

        return cls(
            name=name,
            description=description,
            version=str(version),
            allowed_tools=allowed_tools if isinstance(allowed_tools, list) else [],
            content=body,
            path=path,
            metadata=metadata,
        )

    @staticmethod
    def _extract_frontmatter_manual(frontmatter: str) -> dict[str, Any]:
        """Extract key-value pairs from broken frontmatter as last resort."""
        result = {}
        for line in frontmatter.splitlines():
            kv = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*)\s*:\s*(.*)$", line.strip())
            if kv:
                key = kv.group(1)
                value = kv.group(2).strip()
                if value:
                    result[key] = value
        return result

    def get_preamble(self) -> str | None:
        """Extract preamble bash code block if present."""
        match = re.search(r"```bash\n(.*?)\n```", self.content, re.DOTALL)
        if match:
            return match.group(1)
        return None

    def get_system_prompt(self) -> str:
        """Get the skill content as system prompt."""
        return self.content


class SkillRegistry:
    """Registry for managing loaded skills."""

    def __init__(self):
        self._skills: dict[str, Skill] = {}
        self._skill_dirs: list[Path] = []

    def add_skill_directory(self, directory: Path | str) -> int:
        """Add a directory to search for skills. Returns count of skills loaded."""
        directory = Path(directory).expanduser()
        if not directory.exists():
            return 0

        self._skill_dirs.append(directory)
        return self._load_skills_from_dir(directory)

    def _load_skills_from_dir(self, directory: Path) -> int:
        """Load all skills from a directory."""
        count = 0

        for skill_dir in directory.iterdir():
            if not skill_dir.is_dir():
                continue

            skill_file = skill_dir / "SKILL.md"
            if skill_file.exists():
                skill = Skill.from_file(skill_file)
                if skill and skill.name:
                    self._skills[skill.name] = skill
                    count += 1

        return count

    def get_skill(self, name: str) -> Skill | None:
        """Get a skill by name."""
        return self._skills.get(name)

    def list_skills(self) -> list[str]:
        """List all available skill names."""
        return list(self._skills.keys())

    def get_all_skills(self) -> list[Skill]:
        """Get all loaded skills."""
        return list(self._skills.values())

    def get_skill_prompt(self, name: str) -> str | None:
        """Get the system prompt for a skill."""
        skill = self.get_skill(name)
        if skill:
            return skill.get_system_prompt()
        return None

    def has_skill(self, name: str) -> bool:
        """Check if a skill is loaded."""
        return name in self._skills


def get_default_skill_dirs() -> list[Path]:
    """Get default skill directories to search.

    Loads in priority order (later dirs overwrite earlier ones):
    1. ~/.claude/skills (Claude Code) - lowest priority
    2. ~/.openlaoke/skills (OpenLaoKe installed)
    3. ~/.config/opencode/skills (OpenCode) - highest priority
    4. ~/.opencode/skills (alternative OpenCode path)
    """
    home = Path.home()
    dirs = []

    # Load Claude first (lowest priority)
    claude_skills = home / ".claude" / "skills"
    if claude_skills.exists():
        dirs.append(claude_skills)

    # Then OpenLaoKe installed skills
    openlaoke_skills = home / ".openlaoke" / "skills"
    if openlaoke_skills.exists():
        dirs.append(openlaoke_skills)

    # OpenCode overrides (highest priority - these are the originals)
    opencode_config_skills = home / ".config" / "opencode" / "skills"
    if opencode_config_skills.exists():
        dirs.append(opencode_config_skills)

    opencode_skills = home / ".opencode" / "skills"
    if opencode_skills.exists():
        dirs.append(opencode_skills)

    return dirs


_global_registry: SkillRegistry | None = None


def get_skill_registry() -> SkillRegistry:
    """Get the global skill registry, initializing if needed."""
    global _global_registry

    if _global_registry is None:
        _global_registry = SkillRegistry()

        for skill_dir in get_default_skill_dirs():
            _global_registry.add_skill_directory(skill_dir)

    return _global_registry


def rescan_skills() -> int:
    """Rescan all skill directories and reload skills. Returns count of skills loaded."""
    global _global_registry
    _global_registry = SkillRegistry()

    for skill_dir in get_default_skill_dirs():
        _global_registry.add_skill_directory(skill_dir)

    return len(_global_registry.list_skills())


def load_skill(name: str) -> Skill | None:
    """Load a specific skill by name."""
    return get_skill_registry().get_skill(name)


def list_available_skills() -> list[str]:
    """List all available skill names."""
    return get_skill_registry().list_skills()


def get_skill_system_prompt(skill_names: list[str]) -> str:
    """Get combined system prompt for multiple skills."""
    registry = get_skill_registry()
    prompts = []

    for name in skill_names:
        skill = registry.get_skill(name)
        if skill:
            prompts.append(f"\n## Skill: {skill.name}\n\n{skill.content}")

    return "\n".join(prompts)
