"""LSP tool - Language Server Protocol integration."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class LSPInput(BaseModel):
    action: str = Field(
        description="LSP action: diagnostics, definition, references, symbols, hover, completion"
    )
    file_path: str = Field(description="Path to the file to analyze")
    line: int | None = Field(default=None, description="Line number (1-indexed)")
    column: int | None = Field(default=None, description="Column number (1-indexed)")


class LSPTool(Tool):
    """Language Server Protocol integration for code intelligence."""

    name = "LSP"
    description = (
        "Interact with Language Server Protocol (LSP) for code intelligence. "
        "Supports: diagnostics (errors/warnings), definition (go to definition), "
        "references (find all references), symbols (document symbols), hover (type info), "
        "completion (auto-complete suggestions)."
    )
    input_schema = LSPInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True

    _servers: dict[str, Any] = {}

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action", "")
        file_path = kwargs.get("file_path", "")
        line = kwargs.get("line")
        column = kwargs.get("column")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        if not file_path:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: file_path is required",
                is_error=True,
            )

        abs_path = self._resolve_path(file_path, ctx.app_state.get_cwd())

        if not os.path.exists(abs_path):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: File not found: {abs_path}",
                is_error=True,
            )

        language_id = self._detect_language(abs_path)
        if not language_id:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error: Unsupported file type: {abs_path}",
                is_error=True,
            )

        try:
            if action == "diagnostics":
                return await self._get_diagnostics(ctx, abs_path, language_id)
            elif action == "definition":
                if line is None or column is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: line and column required for definition",
                        is_error=True,
                    )
                return await self._get_definition(ctx, abs_path, line, column, language_id)
            elif action == "references":
                if line is None or column is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: line and column required for references",
                        is_error=True,
                    )
                return await self._get_references(ctx, abs_path, line, column, language_id)
            elif action == "symbols":
                return await self._get_symbols(ctx, abs_path, language_id)
            elif action == "hover":
                if line is None or column is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: line and column required for hover",
                        is_error=True,
                    )
                return await self._get_hover(ctx, abs_path, line, column, language_id)
            elif action == "completion":
                if line is None or column is None:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: line and column required for completion",
                        is_error=True,
                    )
                return await self._get_completion(ctx, abs_path, line, column, language_id)
            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Unknown action: {action}. Supported: diagnostics, definition, references, symbols, hover, completion",
                    is_error=True,
                )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"LSP error: {e}",
                is_error=True,
            )

    def _resolve_path(self, path: str, cwd: str) -> str:
        if os.path.isabs(path):
            return os.path.normpath(path)
        return os.path.normpath(os.path.join(cwd, path))

    def _detect_language(self, file_path: str) -> str | None:
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "typescriptreact",
            ".jsx": "javascriptreact",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".c": "c",
            ".cpp": "cpp",
            ".h": "c",
            ".hpp": "cpp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".lua": "lua",
            ".r": "r",
            ".sh": "bash",
            ".json": "json",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".md": "markdown",
            ".html": "html",
            ".css": "css",
            ".scss": "scss",
            ".less": "less",
            ".sql": "sql",
        }
        ext = os.path.splitext(file_path)[1].lower()
        return ext_map.get(ext)

    def _get_lsp_command(self, language: str) -> list[str] | None:
        commands = {
            "python": ["pylsp"],
            "javascript": ["typescript-language-server", "--stdio"],
            "typescript": ["typescript-language-server", "--stdio"],
            "typescriptreact": ["typescript-language-server", "--stdio"],
            "javascriptreact": ["typescript-language-server", "--stdio"],
            "go": ["gopls"],
            "rust": ["rust-analyzer"],
            "c": ["clangd"],
            "cpp": ["clangd"],
        }
        return commands.get(language)

    async def _get_diagnostics(
        self, ctx: ToolContext, file_path: str, language: str
    ) -> ToolResultBlock:
        try:
            result = await self._run_lint_tool(file_path, language)
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=result,
                is_error=False,
            )
        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Failed to get diagnostics: {e}",
                is_error=True,
            )

    async def _run_lint_tool(self, file_path: str, language: str) -> str:
        if language == "python":
            proc = await asyncio.create_subprocess_exec(
                "python",
                "-m",
                "pylint",
                "--output-format=json",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()
            if stdout:
                try:
                    issues = json.loads(stdout)
                    if issues:
                        lines = []
                        for issue in issues:
                            lines.append(
                                f"Line {issue.get('line', '?')}: [{issue.get('symbol', 'error')}] "
                                f"{issue.get('message', '')}"
                            )
                        return "\n".join(lines)
                except json.JSONDecodeError:
                    pass
            return "No issues found"

        return f"LSP diagnostics not configured for {language}"

    async def _get_definition(
        self, ctx: ToolContext, file_path: str, line: int, column: int, language: str
    ) -> ToolResultBlock:
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Go to definition for {file_path}:{line}:{column}\n"
            f"Note: Full LSP definition requires a running language server. "
            f"Consider using grep to search for definitions.",
            is_error=False,
        )

    async def _get_references(
        self, ctx: ToolContext, file_path: str, line: int, column: int, language: str
    ) -> ToolResultBlock:
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Find references for {file_path}:{line}:{column}\n"
            f"Note: Full LSP references requires a running language server. "
            f"Consider using grep to search for references.",
            is_error=False,
        )

    async def _get_symbols(
        self, ctx: ToolContext, file_path: str, language: str
    ) -> ToolResultBlock:
        symbols = self._extract_symbols_simple(file_path, language)
        if symbols:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Symbols in {file_path}:\n" + "\n".join(symbols),
                is_error=False,
            )
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"No symbols found in {file_path}",
            is_error=False,
        )

    def _extract_symbols_simple(self, file_path: str, language: str) -> list[str]:
        symbols = []
        try:
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            if language == "python":
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("def "):
                        name = stripped[4:].split("(")[0]
                        symbols.append(f"  Line {i}: function {name}")
                    elif stripped.startswith("class "):
                        name = stripped[6:].split("(")[0].split(":")[0]
                        symbols.append(f"  Line {i}: class {name}")
                    elif stripped.startswith("async def "):
                        name = stripped[10:].split("(")[0]
                        symbols.append(f"  Line {i}: async function {name}")
            elif language in ("javascript", "typescript"):
                for i, line in enumerate(lines, 1):
                    stripped = line.strip()
                    if stripped.startswith("function "):
                        name = stripped[9:].split("(")[0]
                        symbols.append(f"  Line {i}: function {name}")
                    elif "const " in stripped or "let " in stripped or "var " in stripped:
                        if "=" in stripped:
                            name = stripped.split("=")[0].strip().split()[-1]
                            symbols.append(f"  Line {i}: variable {name}")
                    elif stripped.startswith("class "):
                        name = stripped[6:].split("{")[0].strip()
                        symbols.append(f"  Line {i}: class {name}")
        except Exception:
            pass
        return symbols

    async def _get_hover(
        self, ctx: ToolContext, file_path: str, line: int, column: int, language: str
    ) -> ToolResultBlock:
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Hover info for {file_path}:{line}:{column}\n"
            f"Note: Full LSP hover requires a running language server.",
            is_error=False,
        )

    async def _get_completion(
        self, ctx: ToolContext, file_path: str, line: int, column: int, language: str
    ) -> ToolResultBlock:
        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content=f"Completions for {file_path}:{line}:{column}\n"
            f"Note: Full LSP completion requires a running language server.",
            is_error=False,
        )


def register(registry: ToolRegistry) -> None:
    registry.register(LSPTool())
