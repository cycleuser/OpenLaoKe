"""Skill command for loading and using skills."""

from __future__ import annotations

from openlaoke.commands.base import SlashCommand, CommandContext, CommandResult
from openlaoke.core.skill_system import list_available_skills, load_skill


class SkillCommand(SlashCommand):
    """Command to load and manage skills."""
    
    name = "skill"
    description = "Load and manage skills"
    
    async def execute(self, ctx: CommandContext) -> CommandResult:
        args = ctx.args.strip().lower()
        
        if not args or args in ("list", "ls"):
            return self._list_skills(ctx)
        elif args in ("help", "?"):
            return self._show_help(ctx)
        else:
            return self._show_skill(ctx, args)
    
    def _list_skills(self, ctx: CommandContext) -> CommandResult:
        """List all available skills."""
        skills = list_available_skills()
        
        if not skills:
            msg = "\n  No skills available."
            msg += "\n  Skills are loaded from:"
            msg += "\n    - ~/.claude/skills/"
            msg += "\n    - ~/.opencode/skills/"
            msg += "\n    - ~/.openlaoke/skills/"
            return CommandResult(success=True, message=msg)
        
        msg = f"\n  Available skills ({len(skills)}):"
        msg += "\n  Press Tab to autocomplete skill names.\n"
        
        for name in sorted(skills):
            skill = load_skill(name)
            if skill:
                desc = skill.description[:40] if skill.description else ""
                if desc:
                    msg += f"\n    /{name:20} - {desc}..."
                else:
                    msg += f"\n    /{name}"
        
        return CommandResult(success=True, message=msg)
    
    def _show_skill(self, ctx: CommandContext, name: str) -> CommandResult:
        """Show details of a specific skill."""
        skill = load_skill(name)
        
        if not skill:
            msg = f"\n  Skill not found: {name}"
            msg += "\n  Use /skill list to see available skills."
            return CommandResult(success=False, message=msg)
        
        msg = f"\n  Skill: {skill.name}"
        msg += f"\n  Version: {skill.version}"
        if skill.description:
            msg += f"\n\n  {skill.description}"
        if skill.allowed_tools:
            msg += f"\n\n  Allowed tools: {', '.join(skill.allowed_tools)}"
        msg += f"\n\n  Path: {skill.path}"
        
        return CommandResult(success=True, message=msg)
    
    def _show_help(self, ctx: CommandContext) -> CommandResult:
        """Show skill command help."""
        msg = """
  Skill commands:
    /skill          List all available skills
    /skill list     List all available skills  
    /skill <name>   Show details of a specific skill
    /skill help     Show this help message

  Quick activation:
    /<skill_name>   Activate a skill directly (use Tab to autocomplete)
    
  Examples:
    /browse         Activate browse skill (browser testing)
    /qa             Activate qa skill (QA testing)
    /debug          Activate debug skill (debugging)
    /review         Activate review skill (code review)

  Skills are loaded from:
    ~/.claude/skills/     (Claude Code skills)
    ~/.opencode/skills/   (OpenCode skills)
    ~/.openlaoke/skills/  (OpenLaoKe skills)
"""
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