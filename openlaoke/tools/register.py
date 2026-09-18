"""Tool registration — the pi tool set: read, write, edit, bash, grep, find, ls, powershell."""

from __future__ import annotations

from openlaoke.core.tool import ToolRegistry


def register_all_tools(registry: ToolRegistry) -> None:
    """Register the built-in tools."""
    from openlaoke.tools.bash_tool import BashTool
    from openlaoke.tools.edit_tool import EditTool
    from openlaoke.tools.glob_tool import GlobTool
    from openlaoke.tools.grep_tool import GrepTool
    from openlaoke.tools.invoke_skill_tool import InvokeSkillTool
    from openlaoke.tools.ls_tool import ListDirectoryTool
    from openlaoke.tools.powershell_tool import PowerShellTool
    from openlaoke.tools.read_tool import ReadTool
    from openlaoke.tools.write_tool import WriteTool

    for tool in (
        ReadTool(),
        WriteTool(),
        EditTool(),
        BashTool(),
        GrepTool(),
        GlobTool(),
        ListDirectoryTool(),
        PowerShellTool(),
        InvokeSkillTool(),
    ):
        registry.register(tool)


def register_essential_tools(registry: ToolRegistry) -> None:
    register_all_tools(registry)


def register_deferred_tools(registry: ToolRegistry) -> None:
    return None


def get_tool_loader(tool_name: str):
    return None
