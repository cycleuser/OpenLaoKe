"""Skill listing and activation commands (Agent Skills standard)."""

from __future__ import annotations

from openlaoke.commands.base import CommandContext, CommandResult, SlashCommand


class SkillCommand(SlashCommand):
    name = "skill"
    description = "List, install or activate a skill"
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
                    message="No skills installed. Add skills to ~/.openlaoke/skills/<name>/SKILL.md,"
                    " or run /skill install <github-url>."
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
            lines.append("Use /skill install <github-url> to add one.")
            return CommandResult(message="\n".join(lines))

        parts = args.split()
        action = parts[0].lower()
        if action in ("install", "add"):
            if len(parts) < 2:
                return CommandResult(
                    success=False,
                    message="Use '/skill install <github-url> [skill-name]'.",
                )
            return await self._install(parts[1], parts[2] if len(parts) > 2 else None)
        if action in ("remove", "rm", "uninstall"):
            if len(parts) < 2:
                return CommandResult(success=False, message="Use '/skill remove <name>'.")
            return await self._remove(parts[1])
        if action == "reload":
            count = rescan_skills()
            return CommandResult(message=f"Reloaded {count} skill(s).")
        if action in ("off", "clear"):
            if len(parts) > 1 and action == "off":
                target = parts[1]
                if target not in ctx.app_state.active_skills:
                    return CommandResult(message=f"Skill not active: {target}")
                ctx.app_state.active_skills.remove(target)
                return CommandResult(message=f"Deactivated skill: {target}")
            ctx.app_state.active_skills.clear()
            return CommandResult(message="All skills deactivated.")
        if action in ("info", "show"):
            if len(parts) < 2:
                return CommandResult(success=False, message="Use '/skill info <name>'.")
            skill = get_skill_registry().get_skill(parts[1])
            if skill is None:
                return CommandResult(success=False, message=f"Unknown skill: {parts[1]}")
            body = getattr(skill, "instructions", "") or getattr(skill, "content", "")
            header = f"{skill.name}: {skill.description}"
            return CommandResult(message=(header + "\n\n" + str(body))[:4000])

        name = parts[0]
        registry = get_skill_registry()
        skill = registry.get_skill(name)
        if skill is None:
            return CommandResult(success=False, message=f"Unknown skill: {name}")
        if name not in ctx.app_state.active_skills:
            ctx.app_state.active_skills.append(name)
        return CommandResult(message=f"Activated skill: {name} — {skill.description[:80]}")

    async def _install(self, url: str, skill_name: str | None) -> CommandResult:
        """Download a skill from a GitHub repository into the skills directory."""
        import httpx

        from openlaoke.core.skill_installer import SkillInstaller
        from openlaoke.core.skill_system import get_skill_registry, rescan_skills

        installer = SkillInstaller()
        try:
            results = await installer.install_from_github(url, skill_name)
        except httpx.HTTPError as exc:
            # A dead network should read as a failed command, not a traceback.
            return CommandResult(success=False, message=f"Download failed: {exc}")
        finally:
            await installer.close()

        if not results:
            return CommandResult(success=False, message=f"Nothing to install from {url}")

        installed = rescan_skills()
        lines = []
        for result in results:
            mark = "ok" if result.success else "failed"
            lines.append(f"[{mark}] {result.skill_name}: {result.message}")
        lines.append("")
        lines.append(f"{installed} skill(s) available. Use /skill <name> to activate one.")

        ok = any(result.success for result in results)
        names = [r.skill_name for r in results if r.success]
        if ok:
            for name in names:
                if get_skill_registry().get_skill(name) is None:
                    lines.append(f"Warning: {name} installed but not loadable (check SKILL.md).")
        return CommandResult(success=ok, message="\n".join(lines))

    async def _remove(self, name: str) -> CommandResult:
        from openlaoke.core.skill_installer import SkillInstaller
        from openlaoke.core.skill_system import rescan_skills

        installer = SkillInstaller()
        try:
            result = installer.remove_skill(name)
        finally:
            await installer.close()

        if not result.success:
            return CommandResult(success=False, message=result.message)
        rescan_skills()
        return CommandResult(message=result.message)


class UseSkillCommand(SlashCommand):
    name = "use-skill"
    description = "Activate a skill by name"
    hidden = True

    async def execute(self, ctx: CommandContext) -> CommandResult:
        command = SkillCommand()
        return await command.execute(ctx)
