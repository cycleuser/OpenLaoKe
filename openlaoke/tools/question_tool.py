"""Question tool - ask user questions interactively."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class QuestionOption(BaseModel):
    value: str = Field(description="The option value")
    label: str | None = Field(default=None, description="Optional display label for the option")


class QuestionItem(BaseModel):
    question: str = Field(description="The question to ask")
    header: str = Field(default="", description="Optional header/title for the question group")
    options: list[QuestionOption] | None = Field(
        default=None, description="Optional list of choices"
    )
    multiple: bool = Field(default=False, description="Allow multiple selections")


class QuestionInput(BaseModel):
    questions: list[QuestionItem] = Field(description="List of questions to ask the user")


class QuestionTool(Tool):
    """Ask the user questions interactively."""

    name = "Question"
    description = (
        "Asks the user questions and returns their answers. "
        "Can ask single or multiple choice questions. "
        "Use this when you need user input or clarification."
    )
    input_schema = QuestionInput
    is_read_only = True
    is_destructive = False
    is_concurrency_safe = True
    requires_approval = False

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        questions_data = kwargs.get("questions", [])

        if not isinstance(questions_data, list):
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: questions must be a list",
                is_error=True,
            )

        output_lines: list[str] = []
        output_lines.append("=== Questions for User ===\n")

        for i, q in enumerate(questions_data, 1):
            if isinstance(q, dict):
                question_text = q.get("question", "")
                header = q.get("header", "")
                options = q.get("options", [])
                multiple = q.get("multiple", False)
            else:
                question_text = getattr(q, "question", "")
                header = getattr(q, "header", "")
                options = getattr(q, "options", None) or []
                multiple = getattr(q, "multiple", False)

            if header:
                output_lines.append(f"[{header}]")

            if multiple:
                output_lines.append(f"{i}. {question_text} (select all that apply)")
            else:
                output_lines.append(f"{i}. {question_text}")

            if options:
                for j, opt in enumerate(options, 1):
                    if isinstance(opt, dict):
                        value = opt.get("value", "")
                        label = opt.get("label") or value
                    else:
                        value = getattr(opt, "value", "")
                        label = getattr(opt, "label", None) or value
                    output_lines.append(f"   [{j}] {label}")
            else:
                output_lines.append("   (Enter your response)")

            output_lines.append("")

        output_lines.append("Please respond with your answers.")
        output_lines.append(
            "For multiple choice questions, provide the number(s) of your selection(s)."
        )
        output_lines.append("For open questions, provide your text response.")

        return ToolResultBlock(
            tool_use_id=ctx.tool_use_id,
            content="\n".join(output_lines),
            is_error=False,
        )


def register(registry: ToolRegistry) -> None:
    registry.register(QuestionTool())
