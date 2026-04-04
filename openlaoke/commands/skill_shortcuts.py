"""Skill shortcut commands - directly invoke skills like /browse, /qa, etc."""

from __future__ import annotations

from openlaoke.commands.base import SlashCommand, CommandContext, CommandResult
from openlaoke.core.skill_system import load_skill, list_available_skills


class SkillShortcutCommand(SlashCommand):
    """Dynamically created skill shortcut command."""
    
    def __init__(self, skill_name: str, description: str = ""):
        self.name = skill_name
        self.description = description or f"Activate {skill_name} skill"
        self.aliases = []
    
    async def execute(self, ctx: CommandContext) -> CommandResult:
        """Execute skill activation."""
        skill = load_skill(self.name)
        if not skill:
            return CommandResult(
                success=False,
                message=f"Skill not found: {self.name}"
            )
        
        if hasattr(ctx.app_state, 'active_skills'):
            if self.name not in ctx.app_state.active_skills:
                ctx.app_state.active_skills.append(self.name)
        
        msg = f"✓ Skill activated: {skill.name}"
        if skill.description:
            desc = skill.description[:80]
            if len(skill.description) > 80:
                desc += "..."
            msg += f"\n  {desc}"
        
        return CommandResult(success=True, message=msg)


def register_skill_shortcuts(registry: dict) -> None:
    """Register shortcuts for all available skills."""
    skills = list_available_skills()
    
    for skill_name in skills:
        skill = load_skill(skill_name)
        if skill:
            desc = skill.description[:80] if skill.description else ""
            cmd = SkillShortcutCommand(skill_name, desc)
            registry[skill_name] = cmd