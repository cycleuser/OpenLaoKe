"""Skill shortcut commands - directly invoke skills like /browse, /qa, etc."""

from __future__ import annotations

from dataclasses import dataclass

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand
from openlaoke.core.skill_system import list_available_skills, load_skill


@dataclass
class SkillActivationResult(CommandResult):
    """Result that includes skill activation info for continued processing."""

    skill_name: str = ""
    skill_content: str = ""
    should_continue_chat: bool = False


class SkillShortcutCommand(SlashCommand):
    """Dynamically created skill shortcut command."""

    def __init__(self, skill_name: str, description: str = ""):
        self.name = skill_name
        self.description = description or f"Activate {skill_name} skill"
        self.aliases = []

    async def execute(self, ctx: CommandContext) -> CommandResult:
        """Execute skill activation and continue with user input if provided."""
        skill = load_skill(self.name)
        if not skill:
            return CommandResult(success=False, message=f"Skill not found: {self.name}")

        if hasattr(ctx.app_state, "active_skills") and self.name not in ctx.app_state.active_skills:
            ctx.app_state.active_skills.append(self.name)

        msg = f"✓ Skill activated: {skill.name}"
        if skill.description:
            desc = skill.description[:80]
            if len(skill.description) > 80:
                desc += "..."
            msg += f"\n  {desc}"

        result = SkillActivationResult(
            success=True,
            message=msg,
            skill_name=self.name,
            skill_content=skill.content,
            should_continue_chat=bool(ctx.args),
        )

        return result


def register_skill_shortcuts(registry: dict) -> None:
    """Register shortcuts for all available skills."""
    skills = list_available_skills()

    for skill_name in skills:
        skill = load_skill(skill_name)
        if skill:
            desc = skill.description[:80] if skill.description else ""
            cmd = SkillShortcutCommand(skill_name, desc)
            registry[skill_name] = cmd
