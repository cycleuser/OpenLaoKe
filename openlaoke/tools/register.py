"""Tool registration with lazy loading support."""

from __future__ import annotations

from collections.abc import Callable

from openlaoke.core.tool import Tool, ToolRegistry


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
    deferred_map: dict[str, tuple[Callable[[], Tool], str, str]] = {
        "Agent": (
            lambda: __import__("openlaoke.tools.agent_tool", fromlist=["AgentTool"]).AgentTool(),
            "Run a subagent for complex tasks",
            "subagent task delegation",
        ),
        "ApplyPatch": (
            lambda: __import__(
                "openlaoke.tools.apply_patch_tool", fromlist=["ApplyPatchTool"]
            ).ApplyPatchTool(),
            "Apply a patch to files",
            "patch apply diff",
        ),
        "Batch": (
            lambda: __import__("openlaoke.tools.batch_tool", fromlist=["BatchTool"]).BatchTool(),
            "Execute multiple tool calls in parallel",
            "parallel batch concurrent",
        ),
        "Git": (
            lambda: __import__("openlaoke.tools.git_tool", fromlist=["GitTool"]).GitTool(),
            "Git operations",
            "git repository version control",
        ),
        "ListDirectory": (
            lambda: __import__(
                "openlaoke.tools.ls_tool", fromlist=["ListDirectoryTool"]
            ).ListDirectoryTool(),
            "List directory contents",
            "ls list directory",
        ),
        "LSP": (
            lambda: __import__("openlaoke.tools.lsp_tool", fromlist=["LSPTool"]).LSPTool(),
            "Language server protocol operations",
            "lsp language server ide",
        ),
        "NotebookWrite": (
            lambda: __import__(
                "openlaoke.tools.notebook_write_tool", fromlist=["NotebookWriteTool"]
            ).NotebookWriteTool(),
            "Edit Jupyter notebooks",
            "jupyter notebook cell",
        ),
        "Plan": (
            lambda: __import__("openlaoke.tools.plan_tool", fromlist=["PlanTool"]).PlanTool(),
            "Create execution plans",
            "plan strategy steps",
        ),
        "Question": (
            lambda: __import__(
                "openlaoke.tools.question_tool", fromlist=["QuestionTool"]
            ).QuestionTool(),
            "Ask user questions",
            "ask question user input",
        ),
        "TaskKill": (
            lambda: __import__(
                "openlaoke.tools.taskkill_tool", fromlist=["TaskKillTool"]
            ).TaskKillTool(),
            "Kill running tasks",
            "kill stop terminate task",
        ),
        "TodoWrite": (
            lambda: __import__(
                "openlaoke.tools.todo_tool", fromlist=["TodoWriteTool"]
            ).TodoWriteTool(),
            "Manage todo list",
            "todo task checklist",
        ),
        "WebFetch": (
            lambda: __import__(
                "openlaoke.tools.webfetch_tool", fromlist=["WebFetchTool"]
            ).WebFetchTool(),
            "Fetch web page content",
            "web fetch url http",
        ),
        "WebSearch": (
            lambda: __import__(
                "openlaoke.tools.websearch_tool", fromlist=["WebSearchTool"]
            ).WebSearchTool(),
            "Search the web",
            "web search duckduckgo",
        ),
        "Sleep": (
            lambda: __import__("openlaoke.tools.sleep_tool", fromlist=["SleepTool"]).SleepTool(),
            "Pause execution for specified duration",
            "sleep wait delay pause",
        ),
        "Brief": (
            lambda: __import__("openlaoke.tools.brief_tool", fromlist=["BriefTool"]).BriefTool(),
            "Enable brief response mode",
            "brief concise short response",
        ),
        "WebBrowser": (
            lambda: __import__(
                "openlaoke.tools.web_browser_tool", fromlist=["WebBrowserTool"]
            ).WebBrowserTool(),
            "Browser automation using Playwright",
            "browser playwright automation navigate click screenshot",
        ),
        "Tmux": (
            lambda: __import__("openlaoke.tools.tmux_tool", fromlist=["TmuxTool"]).TmuxTool(),
            "Manage tmux sessions",
            "tmux session terminal split pane",
        ),
        "PowerShell": (
            lambda: __import__(
                "openlaoke.tools.powershell_tool", fromlist=["PowerShellTool"]
            ).PowerShellTool(),
            "Execute PowerShell commands",
            "powershell windows scripting pwsh",
        ),
        "Cron": (
            lambda: __import__("openlaoke.tools.cron_tool", fromlist=["CronTool"]).CronTool(),
            "Manage cron jobs",
            "cron schedule job timer",
        ),
        "REPL": (
            lambda: __import__("openlaoke.tools.repl_tool", fromlist=["REPLTool"]).REPLTool(),
            "Interactive REPL environment",
            "repl interactive python node ruby",
        ),
        "ToolSearch": (
            lambda: __import__(
                "openlaoke.tools.tool_search_tool", fromlist=["ToolSearchTool"]
            ).ToolSearchTool(),
            "Search and discover available tools",
            "tool search suggest discover",
        ),
        "DownloadReference": (
            lambda: __import__(
                "openlaoke.tools.reference_downloader", fromlist=["ReferenceDownloader"]
            ).ReferenceDownloader(),
            "Download academic papers as PDFs",
            "reference paper pdf download arxiv doi",
        ),
        "BatchDownloadReferences": (
            lambda: __import__(
                "openlaoke.tools.reference_downloader", fromlist=["BatchDownloadReferences"]
            ).BatchDownloadReferences(),
            "Download multiple academic papers",
            "batch download papers references",
        ),
        "SearchAndDownloadPapers": (
            lambda: __import__(
                "openlaoke.tools.reference_downloader", fromlist=["SearchAndDownloadPapers"]
            ).SearchAndDownloadPapers(),
            "Search and download academic papers",
            "search download academic papers semantic scholar",
        ),
    }

    for name, (loader, description, search_hint) in deferred_map.items():
        registry.register_deferred_with_info(
            name=name,
            loader=loader,
            description=description,
            search_hint=search_hint,
        )


def get_tool_loader(tool_name: str) -> Callable[[], Tool] | None:
    """Get a loader function for a deferred tool."""
    loaders: dict[str, Callable[[], Tool]] = {
        "Agent": lambda: __import__(
            "openlaoke.tools.agent_tool", fromlist=["AgentTool"]
        ).AgentTool(),
        "ApplyPatch": lambda: __import__(
            "openlaoke.tools.apply_patch_tool", fromlist=["ApplyPatchTool"]
        ).ApplyPatchTool(),
        "Batch": lambda: __import__(
            "openlaoke.tools.batch_tool", fromlist=["BatchTool"]
        ).BatchTool(),
        "Git": lambda: __import__("openlaoke.tools.git_tool", fromlist=["GitTool"]).GitTool(),
        "ListDirectory": lambda: __import__(
            "openlaoke.tools.ls_tool", fromlist=["ListDirectoryTool"]
        ).ListDirectoryTool(),
        "LSP": lambda: __import__("openlaoke.tools.lsp_tool", fromlist=["LSPTool"]).LSPTool(),
        "NotebookWrite": lambda: __import__(
            "openlaoke.tools.notebook_write_tool", fromlist=["NotebookWriteTool"]
        ).NotebookWriteTool(),
        "Plan": lambda: __import__("openlaoke.tools.plan_tool", fromlist=["PlanTool"]).PlanTool(),
        "Question": lambda: __import__(
            "openlaoke.tools.question_tool", fromlist=["QuestionTool"]
        ).QuestionTool(),
        "TaskKill": lambda: __import__(
            "openlaoke.tools.taskkill_tool", fromlist=["TaskKillTool"]
        ).TaskKillTool(),
        "TodoWrite": lambda: __import__(
            "openlaoke.tools.todo_tool", fromlist=["TodoWriteTool"]
        ).TodoWriteTool(),
        "WebFetch": lambda: __import__(
            "openlaoke.tools.webfetch_tool", fromlist=["WebFetchTool"]
        ).WebFetchTool(),
        "WebSearch": lambda: __import__(
            "openlaoke.tools.websearch_tool", fromlist=["WebSearchTool"]
        ).WebSearchTool(),
        "Sleep": lambda: __import__(
            "openlaoke.tools.sleep_tool", fromlist=["SleepTool"]
        ).SleepTool(),
        "Brief": lambda: __import__(
            "openlaoke.tools.brief_tool", fromlist=["BriefTool"]
        ).BriefTool(),
        "WebBrowser": lambda: __import__(
            "openlaoke.tools.web_browser_tool", fromlist=["WebBrowserTool"]
        ).WebBrowserTool(),
        "Tmux": lambda: __import__("openlaoke.tools.tmux_tool", fromlist=["TmuxTool"]).TmuxTool(),
        "PowerShell": lambda: __import__(
            "openlaoke.tools.powershell_tool", fromlist=["PowerShellTool"]
        ).PowerShellTool(),
        "Cron": lambda: __import__("openlaoke.tools.cron_tool", fromlist=["CronTool"]).CronTool(),
        "REPL": lambda: __import__("openlaoke.tools.repl_tool", fromlist=["REPLTool"]).REPLTool(),
        "ToolSearch": lambda: __import__(
            "openlaoke.tools.tool_search_tool", fromlist=["ToolSearchTool"]
        ).ToolSearchTool(),
        "DownloadReference": lambda: __import__(
            "openlaoke.tools.reference_downloader", fromlist=["ReferenceDownloader"]
        ).ReferenceDownloader(),
        "BatchDownloadReferences": lambda: __import__(
            "openlaoke.tools.reference_downloader", fromlist=["BatchDownloadReferences"]
        ).BatchDownloadReferences(),
        "SearchAndDownloadPapers": lambda: __import__(
            "openlaoke.tools.reference_downloader", fromlist=["SearchAndDownloadPapers"]
        ).SearchAndDownloadPapers(),
    }
    return loaders.get(tool_name)
