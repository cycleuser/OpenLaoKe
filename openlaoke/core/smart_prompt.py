"""Smart system prompt generator optimized for small models.

Avoids unnecessary context gathering for creation tasks.
"""

from __future__ import annotations

from openlaoke.core.tool_adapter import ToolCallAdapter


class SmartPromptGenerator:
    """Generates optimized system prompts based on task type."""

    def __init__(self, model: str):
        self.adapter = ToolCallAdapter(model)

    def generate_system_prompt(
        self,
        user_request: str,
        base_prompt: str,
        tools: list[dict] | None = None,
    ) -> str:
        """Generate an optimized system prompt."""
        lines = [base_prompt]

        if self.adapter.should_skip_context_gathering(user_request):
            lines.extend(
                [
                    "",
                    "⚡ OPTIMIZATION: Direct Creation Mode",
                    "The user wants to create something new. Do NOT:",
                    "  - Read existing files in the current directory",
                    "  - Explore the project structure",
                    "  - Check for similar files",
                    "",
                    "Instead, IMMEDIATELY:",
                    "  - Create the requested file/content directly",
                    "  - Use your knowledge to generate high-quality code",
                    "  - Focus on the specific requirements",
                    "",
                ]
            )

        if tools and not self.adapter.supports_tools():
            tool_instructions = self.adapter.format_tools_as_text(tools)
            lines.extend(
                [
                    "",
                    "🔧 TOOL USAGE (Text Mode)",
                    tool_instructions,
                ]
            )

        return "\n".join(lines)

    def get_execution_hints(self, user_request: str) -> dict[str, bool]:
        """Get hints for execution optimization."""
        return {
            "skip_context_gathering": self.adapter.should_skip_context_gathering(user_request),
            "is_creation": self.adapter.is_creation_request(user_request),
            "needs_tools": not self.adapter.supports_tools(),
        }


def optimize_for_small_model(
    model: str, user_request: str, base_prompt: str, tools: list[dict] | None = None
) -> tuple[str, dict[str, bool]]:
    """Optimize execution for small models."""
    generator = SmartPromptGenerator(model)
    optimized_prompt = generator.generate_system_prompt(user_request, base_prompt, tools)
    hints = generator.get_execution_hints(user_request)
    return optimized_prompt, hints
