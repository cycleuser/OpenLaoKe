"""Skill listing and activation commands (Agent Skills standard)."""

from __future__ import annotations

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand


class SkillCommand(SlashCommand):
    name = "skill"
    description = "List or activate a skill"
    aliases = ["skills"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        from openlaoke.core.skill_system import get_skill_registry, rescan_skills

        args = ctx.args.strip()
        if not args:
            rescan_skills()
            registry = get_skill_registry()
            names = registry.list_skills()
            if not names:
                return CommandResult(
                    message="No skills installed. Add skills to ~/.openlaoke/skills/<name>/SKILL.md."
                )
            lines = ["Available skills:"]
            active = set(ctx.app_state.active_skills)
            for name in sorted(names):
                skill = registry.get_skill(name)
                desc = (skill.description[:60] + "...") if skill and skill.description else ""
                marker = "*" if name in active else " "
                lines.append(f" {marker} {name:<24} {desc}")
            lines.append("")
            lines.append("Use /skill <name> to activate.")
            return CommandResult(message="\n".join(lines))

        parts = args.split()
        action = parts[0].lower()
        if action == "reload":
            count = rescan_skills()
            return CommandResult(message=f"Reloaded {count} skill(s).")
        if action in ("off", "clear"):
            ctx.app_state.active_skills.clear()
            return CommandResult(message="All skills deactivated.")

        name = parts[0]
        registry = get_skill_registry()
        skill = registry.get_skill(name)
        if skill is None:
            return CommandResult(success=False, message=f"Unknown skill: {name}")
        if name not in ctx.app_state.active_skills:
            ctx.app_state.active_skills.append(name)
        return CommandResult(message=f"Activated skill: {name} — {skill.description[:80]}")


class UseSkillCommand(SlashCommand):
    name = "use-skill"
    description = "Activate a skill by name"
    hidden = True

    async def execute(self, ctx: CommandContext) -> CommandResult:
        command = SkillCommand()
        return await command.execute(ctx)
