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
    from openlaoke.tools.apply_patch_tool import ApplyPatchTool
    from openlaoke.tools.bg_tool import BgTool
    from openlaoke.tools.codemode_tool import CodeModeTool
    from openlaoke.tools.compile_tool import CompileTool
    from openlaoke.tools.docs_tool import OpenLaoKeDocsTool
    from openlaoke.tools.edit_tool import EditTool
    from openlaoke.tools.glob_tool import GlobTool
    from openlaoke.tools.grep_tool import GrepTool
    from openlaoke.tools.invoke_skill_tool import InvokeSkillTool
    from openlaoke.tools.ls_tool import ListDirectoryTool
    from openlaoke.tools.memory_tool import MemoryTool
    from openlaoke.tools.read_tool import ReadTool
    from openlaoke.tools.session_search_tool import (
        ConversationSearchTool,
        SessionSearchTool,
    )
    from openlaoke.tools.todo_tool import TodoTool
    from openlaoke.tools.viewer_tools import OpenTool, PanelTool
    from openlaoke.tools.webfetch_tool import WebFetchTool
    from openlaoke.tools.websearch_tool import WebSearchTool
    from openlaoke.tools.write_tool import WriteTool

    tools = [
        ReadTool(),
        WriteTool(),
        EditTool(),
        GrepTool(),
        GlobTool(),
        ListDirectoryTool(),
        TodoTool(),
        WebFetchTool(),
        WebSearchTool(),
        PanelTool(),
        OpenTool(),
        BgTool(),
        CodeModeTool(),
        CompileTool(),
        OpenLaoKeDocsTool(),
        ApplyPatchTool(),
        MemoryTool(),
        SessionSearchTool(),
        ConversationSearchTool(),
    ]
    from openlaoke.utils.config import load_config

    try:
        batch_enabled = bool(load_config().enable_batch)
    except Exception:
        batch_enabled = False
    if batch_enabled:
        from openlaoke.tools.batch_tool import BatchTool

        tools.append(BatchTool())

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
