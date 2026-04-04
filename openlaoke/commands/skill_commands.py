"""Skill command for managing and installing skills."""

from __future__ import annotations

from openlaoke.commands.base import SlashCommand, CommandContext, CommandResult
from openlaoke.core.skill_system import list_available_skills, load_skill, get_skill_registry, get_default_skill_dirs, rescan_skills
from openlaoke.core.skill_installer import SkillInstaller


_installer: SkillInstaller | None = None


def get_installer() -> SkillInstaller:
    global _installer
    if _installer is None:
        _installer = SkillInstaller()
    return _installer


class SkillCommand(SlashCommand):
    """Command to manage and install skills."""

    name = "skill"
    description = "Manage skills: list, install, remove, info"
    aliases = ["skills"]

    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()

        if not args:
            return await self._list_skills(ctx)

        parts = args.split(None, 1)
        subcmd = parts[0].lower()
        subargs = parts[1] if len(parts) > 1 else ""

        if subcmd in ("list", "ls"):
            return await self._list_skills(ctx)
        elif subcmd in ("install", "add", "i"):
            return await self._install_skill(ctx, subargs)
        elif subcmd in ("remove", "rm", "uninstall"):
            return await self._remove_skill(ctx, subargs)
        elif subcmd in ("info", "show"):
            return await self._show_skill(ctx, subargs)
        elif subcmd in ("help", "?"):
            return self._show_help()
        elif subcmd in ("dirs", "sources"):
            return self._show_sources()
        else:
            return await self._show_skill(ctx, subcmd)

    async def _list_skills(self, ctx: CommandContext) -> CommandResult:
        installer = get_installer()
        installed = installer.list_installed()
        all_skills = list_available_skills()
        registry = get_skill_registry()

        msg = f"\n  Available skills ({len(all_skills)}):"
        msg += f"\n  Installed: {len(installed)} | From dirs: {len(all_skills) - len(installed)}"
        msg += "\n"

        if installed:
            msg += "\n  [Installed]"
            for skill in installed:
                desc = skill.description[:50] if skill.description else ""
                msg += f"\n    /{skill.name:25} - {desc}"

        extra = [s for s in all_skills if not any(i.name == s for i in installed)]
        if extra:
            msg += "\n\n  [Loaded from skill dirs]"
            for name in sorted(extra):
                skill = registry.get_skill(name)
                if skill:
                    desc = skill.description[:50] if skill.description else ""
                    msg += f"\n    /{name:25} - {desc}"

        msg += "\n\n  Use /skill install <url> to install new skills"
        msg += "\n  Use /skill help for more commands"
        return CommandResult(success=True, message=msg)

    async def _install_skill(self, ctx: CommandContext, args: str) -> CommandResult:
        if not args:
            msg = "\n  Usage: /skill install <url_or_repo>"
            msg += "\n"
            msg += "\n  Examples:"
            msg += "\n    /skill install https://github.com/cycleuser/Skills"
            msg += "\n    /skill install https://github.com/cycleuser/Skills/ humanizer"
            msg += "\n    /skill install https://raw.githubusercontent.com/..."
            return CommandResult(success=True, message=msg)

        parts = args.split(None, 1)
        repo_url = parts[0]
        skill_name = parts[1] if len(parts) > 1 else None

        installer = get_installer()

        msg = f"\n  Installing skills from: {repo_url}"
        if skill_name:
            msg += f" (filtering: {skill_name})"
        msg += "\n"
        print(msg)

        try:
            results = await installer.install_from_github(repo_url, skill_name)
        except Exception as e:
            return CommandResult(success=False, message=f"\n  Installation failed: {e}")

        # Rescan skills to pick up newly installed skills
        total = rescan_skills()

        # Re-register skill shortcuts in the command registry
        from openlaoke.commands.skill_shortcuts import SkillShortcutCommand
        from openlaoke.commands.registry import get_command
        for skill_name in list_available_skills():
            skill = load_skill(skill_name)
            if skill and not get_command(skill_name):
                desc = skill.description[:80] if skill.description else ""
                from openlaoke.commands.registry import _commands
                _commands[skill_name] = SkillShortcutCommand(skill_name, desc)

        success_count = sum(1 for r in results if r.success)
        fail_count = sum(1 for r in results if not r.success)

        msg = f"\n  Installation complete: {success_count} succeeded, {fail_count} failed"
        msg += f"\n  Total skills available: {total}"

        for r in results:
            if r.success:
                msg += f"\n    [green]✓[/green] {r.skill_name}: {r.message}"
            else:
                msg += f"\n    [red]✗[/red] {r.skill_name}: {r.message}"

        if success_count > 0:
            msg += "\n\n  Skills are now available! Use /<skill_name> to activate."
            msg += "\n  Use /skill list to see all available skills."

        return CommandResult(success=success_count > 0, message=msg)

    async def _remove_skill(self, ctx: CommandContext, args: str) -> CommandResult:
        if not args:
            return CommandResult(success=True, message="\n  Usage: /skill remove <skill_name>")

        installer = get_installer()
        result = installer.remove_skill(args)

        if result.success:
            msg = f"\n  [green]✓[/green] Removed skill: {args}"
        else:
            msg = f"\n  [red]✗[/red] {result.message}"

        return CommandResult(success=result.success, message=msg)

    async def _show_skill(self, ctx: CommandContext, name: str) -> CommandResult:
        skill = load_skill(name)

        if not skill:
            return CommandResult(
                success=False,
                message=f"\n  Skill not found: {name}\n  Use /skill list to see available skills.",
            )

        msg = f"\n  Skill: {skill.name}"
        msg += f"\n  Version: {skill.version}"
        if skill.description:
            msg += f"\n\n  {skill.description}"
        if skill.allowed_tools:
            msg += f"\n\n  Allowed tools: {', '.join(skill.allowed_tools)}"
        if skill.path:
            msg += f"\n\n  Path: {skill.path}"

        return CommandResult(success=True, message=msg)

    def _show_help(self) -> CommandResult:
        msg = """
  Skill management commands:
    /skill                  List all available skills
    /skill list             List all available skills
    /skill install <url>    Install skills from a GitHub repo
    /skill remove <name>    Remove an installed skill
    /skill info <name>      Show details of a specific skill
    /skill dirs             Show skill source directories
    /skill help             Show this help message

  Install examples:
    /skill install https://github.com/cycleuser/Skills
    /skill install https://github.com/cycleuser/Skills/ humanizer

  Quick activation:
    /<skill_name>           Activate a skill directly (Tab to autocomplete)

  Skill sources:
    ~/.claude/skills/       (Claude Code skills)
    ~/.config/opencode/skills/  (OpenCode skills)
    ~/.openlaoke/skills/    (OpenLaoKe installed skills)
"""
        return CommandResult(success=True, message=msg)

    def _show_sources(self) -> CommandResult:
        dirs = get_default_skill_dirs()
        msg = "\n  Skill source directories:"
        for d in dirs:
            msg += f"\n    {d}"
        msg += f"\n\n  OpenLaoKe install dir: {get_installer().install_dir}"
        return CommandResult(success=True, message=msg)


class UseSkillCommand(SlashCommand):
    """Command to activate a skill for the current session."""
    
    name = "use"
    description = "Activate a skill for the current session"
    
    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip()
        
        if not args:
            msg = "  Usage: /use <skill_name>"
            msg += "\n  Use /skill list to see available skills."
            msg += "\n  Tip: You can also use /<skill_name> directly!"
            return CommandResult(success=True, message=msg)
        
        skill = load_skill(args)
        if not skill:
            msg = f"  Skill not found: {args}"
            msg += "\n  Use /skill list to see available skills."
            return CommandResult(success=True, message=msg)
        
        if hasattr(ctx.app_state, 'active_skills'):
            if args not in ctx.app_state.active_skills:
                ctx.app_state.active_skills.append(args)
        
        msg = f"  ✓ Skill activated: {skill.name}"
        if skill.description:
            desc = skill.description[:100]
            if len(skill.description) > 100:
                desc += "..."
            msg += f"\n    {desc}"
        
        return CommandResult(success=True, message=msg)