"""Tool registration — the pi tool set, adapted to the host OS.

Read/Write/Edit/Grep/Glob/ListDirectory/InvokeSkill are always available. The
shell tools are added only when they are actually usable on this machine: Bash
when a POSIX shell exists, PowerShell when it is installed (or on Windows).

This keeps the tool list honest about the environment. On macOS the model is
never handed a PowerShell tool it cannot call, so it will not mistake the host
for Windows.
"""

from __future__ import annotations

import platform
import shutil

from openlaoke.core.tool import ToolRegistry


def _has_bash() -> bool:
    if platform.system() != "Windows":
        return True
    return bool(shutil.which("bash") or shutil.which("sh"))


def _has_powershell() -> bool:
    if platform.system() == "Windows":
        return True
    return bool(shutil.which("pwsh") or shutil.which("powershell"))


def register_all_tools(registry: ToolRegistry) -> None:
    """Register the built-in tools for this host."""
    from openlaoke.tools.edit_tool import EditTool
    from openlaoke.tools.glob_tool import GlobTool
    from openlaoke.tools.grep_tool import GrepTool
    from openlaoke.tools.invoke_skill_tool import InvokeSkillTool
    from openlaoke.tools.ls_tool import ListDirectoryTool
    from openlaoke.tools.read_tool import ReadTool
    from openlaoke.tools.write_tool import WriteTool

    tools = [
        ReadTool(),
        WriteTool(),
        EditTool(),
        GrepTool(),
        GlobTool(),
        ListDirectoryTool(),
    ]
    if _has_bash():
        from openlaoke.tools.bash_tool import BashTool

        tools.append(BashTool())
    if _has_powershell():
        from openlaoke.tools.powershell_tool import PowerShellTool

        tools.append(PowerShellTool())
    tools.append(InvokeSkillTool())

    for tool in tools:
        registry.register(tool)


def register_essential_tools(registry: ToolRegistry) -> None:
    register_all_tools(registry)


def register_deferred_tools(registry: ToolRegistry) -> None:
    return None


def get_tool_loader(tool_name: str):
    return None
