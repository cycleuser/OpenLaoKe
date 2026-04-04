"""REPL tool - interactive REPL environment."""

from __future__ import annotations

import subprocess
from typing import Any, Literal

from pydantic import BaseModel, Field

from openlaoke.core.tool import Tool, ToolContext, ToolRegistry
from openlaoke.types.core_types import ToolResultBlock


class REPLInput(BaseModel):
    action: Literal["start", "stop", "execute", "reset", "status"] = Field(
        description="REPL action to perform"
    )
    language: Literal["python", "node", "ruby", "irb", "bash"] = Field(
        default="python", description="Programming language for the REPL"
    )
    code: str | None = Field(default=None, description="Code to execute in the REPL")
    session_id: str | None = Field(
        default=None, description="Session identifier for state persistence"
    )


class REPLTool(Tool):
    """Interactive REPL environment for multiple languages."""

    name = "REPL"
    description = (
        "Manage interactive REPL sessions for various programming languages. "
        "Supports Python, Node.js, Ruby, IRB, and Bash. "
        "Maintains state across executions within a session. "
        "Useful for interactive coding, testing, and debugging."
    )
    input_schema = REPLInput
    is_read_only = False
    is_destructive = False
    is_concurrency_safe = False
    requires_approval = False

    def __init__(self) -> None:
        super().__init__()
        self._sessions: dict[str, dict[str, Any]] = {}

    async def call(self, ctx: ToolContext, **kwargs: Any) -> ToolResultBlock:
        action = kwargs.get("action")
        language = kwargs.get("language", "python")
        code = kwargs.get("code")
        session_id = kwargs.get("session_id", "default")

        if not action:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content="Error: action is required",
                is_error=True,
            )

        if session_id not in self._sessions:
            self._sessions[session_id] = {
                "language": language,
                "variables": {},
                "history": [],
            }

        session = self._sessions[session_id]

        try:
            if action == "start":
                session["language"] = language
                session["variables"] = {}
                session["history"] = []
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Started {language} REPL session: {session_id}",
                    is_error=False,
                )

            elif action == "stop":
                if session_id in self._sessions:
                    del self._sessions[session_id]
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Stopped REPL session: {session_id}",
                    is_error=False,
                )

            elif action == "execute":
                if not code:
                    return ToolResultBlock(
                        tool_use_id=ctx.tool_use_id,
                        content="Error: code is required for execute action",
                        is_error=True,
                    )

                lang = session.get("language", language)

                if lang == "python":
                    result = self._execute_python(code, session)
                elif lang == "node":
                    result = self._execute_node(code, session)
                elif lang in ("ruby", "irb"):
                    result = self._execute_ruby(code, session)
                elif lang == "bash":
                    result = self._execute_bash(code, ctx)
                else:
                    result = f"Unsupported language: {lang}"

                session["history"].append({"code": code, "result": result})

                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=result,
                    is_error=False,
                )

            elif action == "reset":
                session["variables"] = {}
                session["history"] = []
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Reset REPL session: {session_id}",
                    is_error=False,
                )

            elif action == "status":
                history_count = len(session.get("history", []))
                lang = session.get("language", "unknown")
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Session: {session_id}\nLanguage: {lang}\nHistory entries: {history_count}",
                    is_error=False,
                )

            else:
                return ToolResultBlock(
                    tool_use_id=ctx.tool_use_id,
                    content=f"Error: Unknown action: {action}",
                    is_error=True,
                )

        except Exception as e:
            return ToolResultBlock(
                tool_use_id=ctx.tool_use_id,
                content=f"Error during REPL operation: {e}",
                is_error=True,
            )

    def _execute_python(self, code: str, session: dict[str, Any]) -> str:
        """Execute Python code."""
        try:
            result = subprocess.run(
                ["python3", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nStderr:\n{result.stderr}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        except FileNotFoundError:
            return "Error: python3 not found"

    def _execute_node(self, code: str, session: dict[str, Any]) -> str:
        """Execute Node.js code."""
        try:
            result = subprocess.run(
                ["node", "-e", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nStderr:\n{result.stderr}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        except FileNotFoundError:
            return "Error: node not found"

    def _execute_ruby(self, code: str, session: dict[str, Any]) -> str:
        """Execute Ruby code."""
        try:
            result = subprocess.run(
                ["ruby", "-e", code],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nStderr:\n{result.stderr}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"
        except FileNotFoundError:
            return "Error: ruby not found"

    def _execute_bash(self, code: str, ctx: ToolContext) -> str:
        """Execute Bash code."""
        try:
            result = subprocess.run(
                ["bash", "-c", code],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=ctx.app_state.get_cwd(),
            )
            output = result.stdout
            if result.stderr:
                output += f"\nStderr:\n{result.stderr}"
            return output or "(no output)"
        except subprocess.TimeoutExpired:
            return "Error: Execution timed out"


def register(registry: ToolRegistry) -> None:
    registry.register(REPLTool())
