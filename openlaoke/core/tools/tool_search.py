"""Tool search tool for discovering and loading deferred tools."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from openlaoke.core.tool import Tool, ToolContext
from openlaoke.types.core_types import ToolResultBlock

if TYPE_CHECKING:
    from openlaoke.core.tools.lazy_loader import LazyToolLoader


@dataclass
class ToolMatch:
    """A matched tool from search."""

    name: str
    description: str
    search_hint: str = ""
    score: float = 0.0
    is_loaded: bool = False


@dataclass
class ToolSuggestion:
    """A suggested tool based on context."""

    name: str
    reason: str
    confidence: float = 0.0


class ToolSearchInput(BaseModel):
    """Input schema for ToolSearch tool."""

    query: str
    max_results: int = 5


class ToolSearchTool(Tool):
    """Tool search tool - search and load available tools."""

    name = "ToolSearch"
    description = "Search for deferred tools and load them on demand"
    input_schema = ToolSearchInput
    defer_loading = True

    def __init__(self, lazy_loader: LazyToolLoader | None = None) -> None:
        super().__init__()
        self._lazy_loader = lazy_loader

    def set_lazy_loader(self, loader: LazyToolLoader) -> None:
        """Set the lazy loader instance."""
        self._lazy_loader = loader

    def _parse_tool_name(self, name: str) -> dict[str, Any]:
        """Parse tool name into searchable parts."""
        if name.startswith("mcp__"):
            without_prefix = name.replace("mcp__", "").lower()
            parts: list[str] = []
            for segment in without_prefix.split("__"):
                parts.extend(segment.split("_"))
            return {
                "parts": [p for p in parts if p],
                "full": without_prefix.replace("__", " ").replace("_", " "),
                "is_mcp": True,
            }

        camel_split = re.sub(r"([a-z])([A-Z])", r"\1 \2", name)
        space_split = camel_split.replace("_", " ").lower()
        parts = space_split.split()
        return {
            "parts": [p for p in parts if p],
            "full": " ".join(parts),
            "is_mcp": False,
        }

    async def search(self, query: str, max_results: int = 5) -> list[ToolMatch]:
        """Search matching tools."""
        if not self._lazy_loader:
            return []

        query_lower = query.lower().strip()
        deferred = self._lazy_loader.get_all_deferred_info()

        exact_match = None
        for t in deferred:
            if t.name.lower() == query_lower:
                exact_match = ToolMatch(
                    name=t.name,
                    description=t.description,
                    search_hint=t.search_hint,
                    score=100.0,
                    is_loaded=t.is_loaded,
                )
                return [exact_match]

        results: list[ToolMatch] = []
        query_terms = query_lower.split()

        for tool in deferred:
            score = 0.0
            name_lower = tool.name.lower()
            desc_lower = tool.description.lower()
            hint_lower = tool.search_hint.lower()

            for term in query_terms:
                if term in name_lower:
                    score += 10.0
                if term in hint_lower:
                    score += 8.0
                if term in desc_lower:
                    score += 5.0
                for alias in tool.aliases:
                    if term in alias.lower():
                        score += 7.0

            if score > 0:
                results.append(
                    ToolMatch(
                        name=tool.name,
                        description=tool.description,
                        search_hint=tool.search_hint,
                        score=score,
                        is_loaded=tool.is_loaded,
                    )
                )

        return sorted(results, key=lambda m: m.score, reverse=True)[:max_results]

    async def suggest(self, context: str) -> list[ToolSuggestion]:
        """Suggest tools based on context."""
        if not self._lazy_loader:
            return []

        suggestions: list[ToolSuggestion] = []
        context_lower = context.lower()

        keywords_map: dict[str, list[str]] = {
            "file": ["Read", "Write", "Edit", "Glob", "Grep"],
            "read": ["Read"],
            "write": ["Write"],
            "edit": ["Edit"],
            "search": ["Grep", "Glob", "ToolSearch"],
            "web": ["WebSearch", "WebFetch"],
            "fetch": ["WebFetch"],
            "git": ["Git", "Bash"],
            "bash": ["Bash"],
            "command": ["Bash"],
            "plan": ["Plan"],
            "notebook": ["NotebookEdit"],
            "jupyter": ["NotebookEdit"],
            "agent": ["Agent"],
            "task": ["TaskKill", "Agent"],
            "todo": ["Todo"],
            "ask": ["Question"],
            "ls": ["LS", "Glob"],
            "patch": ["ApplyPatch"],
            "batch": ["Batch"],
        }

        for keyword, tool_names in keywords_map.items():
            if keyword in context_lower:
                for name in tool_names:
                    deferred = self._lazy_loader.deferred_tools.get(name)
                    if deferred:
                        suggestions.append(
                            ToolSuggestion(
                                name=name,
                                reason=f"Keyword '{keyword}' detected",
                                confidence=0.7,
                            )
                        )

        return sorted(suggestions, key=lambda s: s.confidence, reverse=True)[:5]

    async def load_tool(self, name: str) -> bool:
        """Load a specific tool."""
        if not self._lazy_loader:
            return False

        tool = await self._lazy_loader.get(name)
        return tool is not None

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        """Execute tool search."""
        query = kwargs.get("query", "")
        max_results = kwargs.get("max_results", 5)

        matches = await self.search(query, max_results)

        if not matches:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="No matching deferred tools found",
                is_error=False,
            )

        result_lines: list[str] = []
        for match in matches:
            status = "loaded" if match.is_loaded else "deferred"
            result_lines.append(f"- {match.name} ({status}): {match.description[:50]}...")

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(result_lines),
            is_error=False,
        )

    def get_description(self) -> str:
        return self.description

    def get_input_schema(self) -> dict[str, Any]:
        return self.input_schema.model_json_schema()
