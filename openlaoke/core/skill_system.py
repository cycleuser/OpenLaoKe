"""Skill system for loading and managing agent skills.

Compatible with Claude Code and OpenCode skill formats.
"""

from __future__ import annotations

import os
import re
import yaml
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
        metadata = {}
        body = content
        
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                frontmatter = parts[1].strip()
                body = parts[2].strip()
                try:
                    metadata = yaml.safe_load(frontmatter) or {}
                except yaml.YAMLError:
                    pass
        
        name = metadata.get("name", path.stem if path else "unknown")
        description = metadata.get("description", "")
        if isinstance(description, str):
            description = description.strip()
        version = metadata.get("version", "1.0.0")
        allowed_tools = metadata.get("allowed-tools", metadata.get("allowed_tools", []))
        
        return cls(
            name=name,
            description=description,
            version=str(version),
            allowed_tools=allowed_tools if isinstance(allowed_tools, list) else [],
            content=body,
            path=path,
            metadata=metadata,
        )
    
    def get_preamble(self) -> str | None:
        """Extract preamble bash code block if present."""
        match = re.search(r'```bash\n(.*?)\n```', self.content, re.DOTALL)
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
    
    Searches in order:
    1. ~/.config/opencode/skills (OpenCode)
    2. ~/.claude/skills (Claude Code)
    3. ~/.opencode/skills (alternative OpenCode path)
    4. ~/.openlaoke/skills (OpenLaoKe)
    """
    home = Path.home()
    dirs = []
    
    opencode_config_skills = home / ".config" / "opencode" / "skills"
    if opencode_config_skills.exists():
        dirs.append(opencode_config_skills)
    
    claude_skills = home / ".claude" / "skills"
    if claude_skills.exists():
        dirs.append(claude_skills)
    
    opencode_skills = home / ".opencode" / "skills"
    if opencode_skills.exists():
        dirs.append(opencode_skills)
    
    openlaoke_skills = home / ".openlaoke" / "skills"
    if openlaoke_skills.exists():
        dirs.append(openlaoke_skills)
    
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