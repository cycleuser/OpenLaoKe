"""Tab completion system for OpenLaoKe CLI."""

from __future__ import annotations

import readline
from typing import Callable

from openlaoke.core.skill_system import list_available_skills
from openlaoke.commands.registry import get_all_commands


class TabCompleter:
    """Tab completion for commands and skills."""
    
    def __init__(self):
        self._commands = []
        self._skills = []
        self._matches = []
        self._refresh()
    
    def _refresh(self):
        """Refresh the list of commands and skills."""
        # Get all slash commands
        self._commands = []
        for cmd in get_all_commands():
            if cmd.name and not cmd.hidden:
                self._commands.append(f"/{cmd.name}")
                for alias in cmd.aliases:
                    self._commands.append(f"/{alias}")
        
        # Get all skills
        self._skills = []
        for skill_name in list_available_skills():
            self._skills.append(f"/{skill_name}")
    
    def complete(self, text: str, state: int) -> str | None:
        """Complete the text."""
        if state == 0:
            # First call - build match list
            self._matches = []
            
            # Refresh lists
            self._refresh()
            
            # Get all completions
            all_items = self._commands + self._skills
            
            # Find matches
            for item in all_items:
                if item.startswith(text):
                    self._matches.append(item)
            
            # Also match partial commands (e.g., /p -> /plan, /python)
            if text.startswith("/"):
                partial = text[1:]  # Remove the /
                for skill in list_available_skills():
                    if skill.startswith(partial):
                        self._matches.append(f"/{skill}")
        
        # Return the next match
        if state < len(self._matches):
            return self._matches[state]
        
        return None
    
    def get_completions(self, text: str) -> list[str]:
        """Get all possible completions for text."""
        self._refresh()
        
        completions = []
        all_items = self._commands + self._skills
        
        for item in all_items:
            if item.startswith(text):
                completions.append(item)
        
        return sorted(set(completions))
    
    def get_skill_suggestions(self, prefix: str) -> list[str]:
        """Get skill suggestions for a prefix."""
        self._refresh()
        
        suggestions = []
        for skill in list_available_skills():
            if skill.startswith(prefix):
                suggestions.append(skill)
        
        return suggestions


def setup_tab_completion():
    """Setup tab completion for readline."""
    completer = TabCompleter()
    
    # Set the completer
    readline.set_completer(completer.complete)
    
    # Enable tab completion
    readline.parse_and_bind("tab: complete")
    
    # Set completion delimiter to space only (so /p can complete to /plan)
    readline.set_completer_delims(" \t\n")
    
    return completer


def show_completion_menu(text: str, completions: list[str]) -> str:
    """Show a completion menu and let user select."""
    if not completions:
        return text
    
    if len(completions) == 1:
        return completions[0]
    
    # Show all completions
    print("\n")
    for i, comp in enumerate(completions):
        print(f"  {i+1:2}. {comp}")
    
    print()
    return text


# Global completer instance
_completer: TabCompleter | None = None


def get_completer() -> TabCompleter:
    """Get the global completer instance."""
    global _completer
    if _completer is None:
        _completer = TabCompleter()
    return _completer