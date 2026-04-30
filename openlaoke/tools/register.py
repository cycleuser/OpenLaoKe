"""Tool registration with lazy loading support."""

from __future__ import annotations

import importlib
from collections.abc import Callable

from openlaoke.core.tool import Tool, ToolRegistry

_DEFERRED_TOOLS: dict[str, tuple[str, str, str, str]] = {
    "Agent": (
        "openlaoke.tools.agent_tool",
        "AgentTool",
        "Run a subagent for complex tasks",
        "subagent task delegation",
    ),
    "ApplyPatch": (
        "openlaoke.tools.apply_patch_tool",
        "ApplyPatchTool",
        "Apply a patch to files",
        "patch apply diff",
    ),
    "Batch": (
        "openlaoke.tools.batch_tool",
        "BatchTool",
        "Execute multiple tool calls in parallel",
        "parallel batch concurrent",
    ),
    "Git": (
        "openlaoke.tools.git_tool",
        "GitTool",
        "Git operations",
        "git repository version control",
    ),
    "ListDirectory": (
        "openlaoke.tools.ls_tool",
        "ListDirectoryTool",
        "List directory contents",
        "ls list directory",
    ),
    "LSP": (
        "openlaoke.tools.lsp_tool",
        "LSPTool",
        "Language server protocol operations",
        "lsp language server ide",
    ),
    "NotebookWrite": (
        "openlaoke.tools.notebook_write_tool",
        "NotebookWriteTool",
        "Edit Jupyter notebooks",
        "jupyter notebook cell",
    ),
    "Plan": (
        "openlaoke.tools.plan_tool",
        "PlanTool",
        "Create execution plans",
        "plan strategy steps",
    ),
    "Question": (
        "openlaoke.tools.question_tool",
        "QuestionTool",
        "Ask user questions",
        "ask question user input",
    ),
    "TaskKill": (
        "openlaoke.tools.taskkill_tool",
        "TaskKillTool",
        "Kill running tasks",
        "kill stop terminate task",
    ),
    "TodoWrite": (
        "openlaoke.tools.todo_tool",
        "TodoWriteTool",
        "Manage todo list",
        "todo task checklist",
    ),
    "WebFetch": (
        "openlaoke.tools.webfetch_tool",
        "WebFetchTool",
        "Fetch web page content",
        "web fetch url http",
    ),
    "WebSearch": (
        "openlaoke.tools.websearch_tool",
        "WebSearchTool",
        "Search the web",
        "web search duckduckgo",
    ),
    "Sleep": (
        "openlaoke.tools.sleep_tool",
        "SleepTool",
        "Pause execution for specified duration",
        "sleep wait delay pause",
    ),
    "Brief": (
        "openlaoke.tools.brief_tool",
        "BriefTool",
        "Enable brief response mode",
        "brief concise short response",
    ),
    "WebBrowser": (
        "openlaoke.tools.web_browser_tool",
        "WebBrowserTool",
        "Browser automation using Playwright",
        "browser playwright automation navigate click screenshot",
    ),
    "Tmux": (
        "openlaoke.tools.tmux_tool",
        "TmuxTool",
        "Manage tmux sessions",
        "tmux session terminal split pane",
    ),
    "PowerShell": (
        "openlaoke.tools.powershell_tool",
        "PowerShellTool",
        "Execute PowerShell commands",
        "powershell windows scripting pwsh",
    ),
    "Cron": (
        "openlaoke.tools.cron_tool",
        "CronTool",
        "Manage cron jobs",
        "cron schedule job timer",
    ),
    "REPL": (
        "openlaoke.tools.repl_tool",
        "REPLTool",
        "Interactive REPL environment",
        "repl interactive python node ruby",
    ),
    "ToolSearch": (
        "openlaoke.tools.tool_search_tool",
        "ToolSearchTool",
        "Search and discover available tools",
        "tool search suggest discover",
    ),
    "DownloadReference": (
        "openlaoke.tools.reference_downloader",
        "ReferenceDownloader",
        "Download academic papers as PDFs",
        "reference paper pdf download arxiv doi",
    ),
    "BatchDownloadReferences": (
        "openlaoke.tools.reference_downloader",
        "BatchDownloadReferences",
        "Download multiple academic papers",
        "batch download papers references",
    ),
    "SearchAndDownloadPapers": (
        "openlaoke.tools.reference_downloader",
        "SearchAndDownloadPapers",
        "Search and download academic papers",
        "search download academic papers semantic scholar",
    ),
}


def _make_loader(module_name: str, class_name: str) -> Callable[[], Tool]:
    def loader() -> Tool:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)()

    return loader


def register_all_tools(registry: ToolRegistry) -> None:
    """Register all built-in tools with essential tools loaded immediately."""
    register_essential_tools(registry)
    register_deferred_tools(registry)


def register_essential_tools(registry: ToolRegistry) -> None:
    """Register essential tools that are always loaded."""
    from openlaoke.tools.bash_tool import BashTool
    from openlaoke.tools.edit_tool import EditTool
    from openlaoke.tools.glob_tool import GlobTool
    from openlaoke.tools.grep_tool import GrepTool
    from openlaoke.tools.read_tool import ReadTool
    from openlaoke.tools.write_tool import WriteTool

    registry.register(BashTool())
    registry.register(ReadTool())
    registry.register(WriteTool())
    registry.register(EditTool())
    registry.register(GlobTool())
    registry.register(GrepTool())


def register_deferred_tools(registry: ToolRegistry) -> None:
    """Register deferred tools with lazy loading."""
    for name, (module_name, class_name, description, search_hint) in _DEFERRED_TOOLS.items():
        registry.register_deferred_with_info(
            name=name,
            loader=_make_loader(module_name, class_name),
            description=description,
            search_hint=search_hint,
        )


def get_tool_loader(tool_name: str) -> Callable[[], Tool] | None:
    """Get a loader function for a deferred tool."""
    if tool_name in _DEFERRED_TOOLS:
        module_name, class_name, _, _ = _DEFERRED_TOOLS[tool_name]
        return _make_loader(module_name, class_name)
    return None
