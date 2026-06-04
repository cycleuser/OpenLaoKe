"""2-Stage Tool Routing System — Category scoring and dynamic schema injection.

Reduces token overhead by only sending relevant tool schemas based on
message classification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TOOL_CATEGORIES = {
    "read": {
        "description": "Read files, list directories, explore codebase",
        "tools": ["Read", "ListDirectory", "Glob", "Grep"],
        "patterns": [
            (r"\b(read|show|view|display|list|explore|check|inspect)\b", 2),
            (r"\b(file|directory|folder|path|code)\b", 1),
            (r"\b(what (is|are|does)|how|where|who)\b", 1),
            (r"\b(explain|understand|learn|find)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(write|create|make|add|change|modify|update|delete|remove)\b", -2),
            (r"\b(run|execute|test|build|install)\b", -1),
        ],
    },
    "write": {
        "description": "Write, create, edit, or modify files",
        "tools": ["Write", "Edit", "ApplyPatch"],
        "patterns": [
            (r"\b(write|create|make|add|change|modify|update|delete|remove)\b", 2),
            (r"\b(file|code|function|class|test|config)\b", 1),
            (r"\b(new|implement|build|develop|design)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(read|show|view|list|explain|understand)\b", -2),
            (r"\b(run|execute|test)\b", -1),
        ],
    },
    "search": {
        "description": "Search for content in files or codebase",
        "tools": ["Grep", "Glob", "ToolSearch"],
        "patterns": [
            (r"\b(search|find|look for|locate|scan)\b", 2),
            (r"\b(pattern|regex|regexp|grep|glob)\b", 2),
            (r"\b(all uses? of|where (is|are)|who (calls|uses|inherits))\b", 2),
            (r"\b(reference|usage|caller|occurrence)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(write|create|make|change)\b", -2),
            (r"\b(run|execute|test)\b", -1),
        ],
    },
    "run": {
        "description": "Run shell commands, execute code, build, test",
        "tools": ["Bash", "CodeRunner", "TaskKill"],
        "patterns": [
            (r"\b(run|execute|test|build|install|compile|start|stop|restart)\b", 2),
            (r"\b(command|script|process|server|app)\b", 1),
            (r"\b(pip|npm|pytest|cargo|go|make|docker)\b", 2),
        ],
        "anti_patterns": [
            (r"\b(read|show|view|explain)\b", -2),
            (r"\b(write|create|modify)\b", -1),
        ],
    },
    "plan": {
        "description": "Create plans, strategies, or task lists",
        "tools": ["Plan", "TodoWrite"],
        "patterns": [
            (r"\b(plan|strategy|approach|design|architect)\b", 2),
            (r"\b(step|phase|task|todo|checklist)\b", 1),
            (r"\b(how (to|should)|what (is|are) the steps)\b", 1),
            (r"\b(refactor|migrate|rewrite|reorganize|restructure)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(just|simple|quick|small|tiny)\b", -1),
        ],
    },
    "code_intel": {
        "description": "Semantic code questions (how does X work, call graphs, inheritance)",
        "tools": ["LSP", "Grep", "Read", "Glob"],
        "patterns": [
            (r"\b(how does \w+ work)\b", 3),
            (r"\b(what calls? \w+)\b", 3),
            (r"\b(who (inherits|extends|implements) \w+)\b", 3),
            (r"\b(call(ers?| graph)|inherit(ance|ors?)|dependenc)\b", 2),
            (r"\b(symbol|function|method|class|interface)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(write|create|modify|change)\b", -2),
            (r"\b(run|execute|test)\b", -1),
        ],
    },
    "web": {
        "description": "Web browsing, fetching URLs, searching the internet",
        "tools": ["WebSearch", "WebFetch", "WebBrowser"],
        "patterns": [
            (r"\b(search (the )?web|google|look up)\b", 2),
            (r"\b(fetch|download|get) (the )?(url|page|site|web)\b", 2),
            (r"\b(http|https|www\.|\.com|\.org)\b", 2),
            (r"\b(documentation|docs|api reference)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(local|file|directory|code)\b", -1),
        ],
    },
    "respond": {
        "description": "Just answer the question, no tools needed",
        "tools": [],
        "patterns": [
            (r"\b(thank|thanks|ok|okay|yes|no|sure|got it)\b", 2),
            (r"\b(what do you think|how are you|hello|hi)\b", 2),
            (r"\b(explain|describe|tell me|what is)\b", 1),
        ],
        "anti_patterns": [
            (r"\b(file|code|run|write|search|read)\b", -2),
        ],
    },
}

CATEGORY_PRIORITY = ["write", "run", "code_intel", "search", "plan", "read", "web", "respond"]


@dataclass
class RoutingResult:
    """Result of tool routing."""

    category: str
    tools: list[str]
    score: float
    is_two_stage: bool = False


@dataclass
class ToolRouter:
    """2-Stage tool router based on weighted regex scoring."""

    context_length: int = 32000
    two_stage_threshold: int = 16000
    previous_category: str | None = None

    def route(self, message: str) -> RoutingResult:
        """Route message to tool category using weighted regex scoring."""
        message_lower = message.lower()

        if self._is_affirmation(message_lower):
            return self._reuse_previous_category()

        scores = {}
        for category, config in TOOL_CATEGORIES.items():
            score = 0.0
            for pattern, weight in config["patterns"]:
                if re.search(pattern, message_lower):
                    score += weight
            for pattern, weight in config["anti_patterns"]:
                if re.search(pattern, message_lower):
                    score += weight
            scores[category] = score

        best_category = max(scores, key=scores.get)

        if scores[best_category] <= 0:
            best_category = "respond"

        self.previous_category = best_category

        tools = TOOL_CATEGORIES[best_category]["tools"]
        is_two_stage = self.context_length <= self.two_stage_threshold

        return RoutingResult(
            category=best_category,
            tools=tools,
            score=scores[best_category],
            is_two_stage=is_two_stage,
        )

    def _is_affirmation(self, message: str) -> bool:
        """Check if message is a simple affirmation (yes/ok/etc)."""
        affirmation_patterns = [
            r"^\s*(yes|ok|okay|sure|yeah|yep|yup|right|correct|go ahead|continue)\s*$",
            r"^\s*[✓✔✅]\s*$",
        ]
        return any(re.match(p, message) for p in affirmation_patterns)

    def _reuse_previous_category(self) -> RoutingResult:
        """Reuse previous category for affirmations."""
        if self.previous_category and self.previous_category != "respond":
            tools = TOOL_CATEGORIES[self.previous_category]["tools"]
            return RoutingResult(
                category=self.previous_category,
                tools=tools,
                score=0.0,
            )
        return RoutingResult(
            category="respond",
            tools=[],
            score=0.0,
        )

    def get_category_descriptions(self) -> dict[str, str]:
        """Get category descriptions for two-stage routing."""
        return {cat: config["description"] for cat, config in TOOL_CATEGORIES.items()}

    def get_tools_for_category(self, category: str) -> list[str]:
        """Get tools for a specific category."""
        return TOOL_CATEGORIES.get(category, {}).get("tools", [])

    def get_all_tools_by_category(self) -> dict[str, list[str]]:
        """Get all tools organized by category."""
        return {cat: config["tools"] for cat, config in TOOL_CATEGORIES.items()}
