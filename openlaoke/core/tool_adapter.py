"""Tool calling adapter for models without native function calling support.

Inspired by POSIX-Compatibility-Layer's intent parsing approach.
Converts natural language tool calls into structured format.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ParsedToolCall:
    name: str
    arguments: dict[str, Any]
    confidence: float
    raw_text: str


class ToolCallAdapter:
    """Adapts models without tool support to use tools via text parsing."""

    TOOL_PATTERNS = {
        "bash": [
            r"(?:run|execute|bash|shell|command):\s*`([^`]+)`",
            r"(?:run|execute|bash|shell|command):\s*\*\*([^*]+)\*\*",
            r"```(?:bash|shell)\s*\n(.*?)\n```",
            r"(?:execute|run)\s+(?:the\s+)?(?:command|script):\s*(.+?)(?:\n|$)",
        ],
        "read": [
            r"(?:read|show|display|cat)\s+(?:the\s+)?(?:file\s+)?([^\s]+\.\w+)",
            r"```(?:read|file)\s*\n(.*?)\n```",
        ],
        "write": [
            r"(?:write|create|save)\s+(?:file\s+)?[`']?([^'`\s]+)[`']?\s*(?:with|containing|:)\s*(.+)",
            r"(?:create|make)\s+(?:a\s+)?(?:new\s+)?file\s+[`']?([^'`\s]+)[`']?",
            r"```write\s+[`']?([^'`\s]+)[`']?\s*\n(.*?)\n```",
        ],
        "edit": [
            r"(?:edit|modify|change|update)\s+[`']?([^'`\s]+)[`']?\s*(?::|to|with)\s*(.+)",
            r"(?:replace|substitute)\s+[`']?([^'`\s]+)[`']?",
        ],
        "glob": [
            r"(?:find|search|glob)\s+(?:files?\s+)?(?:matching\s+)?[`']?([^'`\s]+)[`']?",
            r"(?:list|show)\s+(?:all\s+)?(?:files?\s+)?(?:matching\s+)?[`']?([^'`\s]+)[`']?",
        ],
        "grep": [
            r"(?:grep|search)\s+(?:for\s+)?[`']?([^'`\s]+)[`']?\s+(?:in\s+)?[`']?([^'`\s]+)[`']?",
            r"(?:find|search)\s+(?:pattern\s+)?[`']?([^'`\s]+)[`']?",
        ],
    }

    CREATION_KEYWORDS = [
        "write",
        "create",
        "make",
        "generate",
        "build",
        "implement",
        "develop",
        "compose",
        "produce",
        "draft",
        "design",
        "写",
        "创建",
        "生成",
        "实现",
        "开发",
        "编写",
        "制作",
    ]

    NEW_FILE_INDICATORS = [
        "new file",
        "single file",
        "standalone",
        "independent",
        "新文件",
        "单文件",
        "独立",
        "单独",
        "from scratch",
        "from zero",
        "从头",
        "从零",
    ]

    def __init__(self, model: str):
        self.model = model
        self.no_tool_models = {
            "gemma3:1b",
            "gemma3:4b",
            "qwen3.5:0.8b",
            "qwen3.5:1.5b",
            "llama3.2:1b",
            "llama3.2:3b",
            "phi3:mini",
            "phi3:tiny",
        }

    def supports_tools(self) -> bool:
        """Check if model natively supports tool calling."""
        model_lower = self.model.lower()
        return not any(no_tool in model_lower for no_tool in self.no_tool_models)

    def is_creation_request(self, user_input: str) -> bool:
        """Detect if user wants to create something new (not modify existing)."""
        user_lower = user_input.lower()

        has_creation = any(kw in user_lower for kw in self.CREATION_KEYWORDS)
        has_new_indicator = any(ind in user_lower for ind in self.NEW_FILE_INDICATORS)

        return has_creation or has_new_indicator

    def should_skip_context_gathering(self, user_input: str) -> bool:
        """Determine if we should skip reading existing files."""
        if not self.is_creation_request(user_input):
            return False

        modification_keywords = [
            "modify",
            "update",
            "edit",
            "change",
            "fix",
            "refactor",
            "based on",
            "modify existing",
            "修改",
            "更新",
            "编辑",
            "基于",
        ]
        user_lower = user_input.lower()

        has_modification = any(kw in user_lower for kw in modification_keywords)

        return not has_modification

    def parse_tool_calls(self, text: str) -> list[ParsedToolCall]:
        """Parse tool calls from model's text output."""
        if self.supports_tools():
            return []

        calls = []

        for tool_name, patterns in self.TOOL_PATTERNS.items():
            for pattern in patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE | re.DOTALL)
                for match in matches:
                    groups = match.groups()

                    args = self._extract_arguments(tool_name, groups)

                    calls.append(
                        ParsedToolCall(
                            name=tool_name,
                            arguments=args,
                            confidence=0.8,
                            raw_text=match.group(0),
                        )
                    )

        return calls

    def _extract_arguments(self, tool_name: str, groups: tuple[str, ...]) -> dict[str, Any]:
        """Extract tool arguments from regex match groups."""
        args = {}

        if tool_name == "bash":
            if groups:
                args["command"] = groups[0].strip()

        elif tool_name == "read":
            if groups:
                args["file_path"] = groups[0].strip()

        elif tool_name == "write":
            if len(groups) >= 1:
                args["file_path"] = groups[0].strip()
            if len(groups) >= 2:
                args["content"] = groups[1].strip()

        elif tool_name == "edit":
            if len(groups) >= 1:
                args["file_path"] = groups[0].strip()
            if len(groups) >= 2:
                args["new_string"] = groups[1].strip()

        elif tool_name == "glob":
            if groups:
                args["pattern"] = groups[0].strip()

        elif tool_name == "grep":
            if len(groups) >= 1:
                args["pattern"] = groups[0].strip()
            if len(groups) >= 2:
                args["path"] = groups[1].strip()

        return args

    def format_tools_as_text(self, tools: list[dict[str, Any]]) -> str:
        """Format tools specification as natural language for non-tool models."""
        if self.supports_tools():
            return ""

        lines = [
            "\nYou have access to the following tools. Describe your tool usage in natural language:",
            "",
        ]

        for tool in tools:
            name = tool.get("name", "unknown")
            desc = tool.get("description", "")
            schema = tool.get("input_schema", {})
            properties = schema.get("properties", {})

            lines.append(f"**{name}**: {desc}")

            if properties:
                lines.append("  Parameters:")
                for param_name, param_spec in properties.items():
                    param_type = param_spec.get("type", "any")
                    param_desc = param_spec.get("description", "")
                    required = param_name in schema.get("required", [])
                    req_marker = " (required)" if required else ""
                    lines.append(f"    - {param_name} ({param_type}){req_marker}: {param_desc}")

            lines.append("")
            lines.append(f"  Example: Use {name} to [description of what to do]")
            lines.append("")

        lines.extend(
            [
                "When you need to use a tool, describe it naturally like:",
                '- "I will read the file config.py"',
                '- "Let me run the command: pip install requests"',
                '- "I will create a new file main.py with the following content..."',
                "",
            ]
        )

        return "\n".join(lines)


def create_adapter(model: str) -> ToolCallAdapter:
    """Create a tool adapter for the given model."""
    return ToolCallAdapter(model)
