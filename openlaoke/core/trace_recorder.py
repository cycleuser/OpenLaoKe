"""Execution trace recorder - records agent turns for replay and debugging.

Each turn records: tool calls, results, timing, model, tokens.
Traces persist to ~/.openlaoke/traces/ with structured JSON.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ToolCallTrace:
    tool_name: str
    args: dict[str, object]
    result_preview: str
    is_error: bool
    duration_ms: float
    timestamp: float = field(default_factory=time.time)


@dataclass
class TurnTrace:
    turn_id: str
    model: str
    user_message: str
    tool_calls: list[ToolCallTrace] = field(default_factory=list)
    thinking: str = ""
    response_preview: str = ""
    tokens_input: int = 0
    tokens_output: int = 0
    duration_ms: float = 0.0
    success: bool = True
    timestamp: float = field(default_factory=time.time)
    error: str = ""


class TraceRecorder:
    """Records agent execution traces to disk for replay/debug/test generation."""

    def __init__(self, trace_dir: str | None = None) -> None:
        self._dir = Path(trace_dir) if trace_dir else Path.home() / ".openlaoke" / "traces"
        self._dir.mkdir(parents=True, exist_ok=True)
        self._session_id: str = ""
        self._turns: list[TurnTrace] = []
        self._current_turn: TurnTrace | None = None
        self._current_call_start: float = 0.0

    def start_session(self, session_id: str, model: str) -> None:
        self._session_id = session_id
        self._turns = []

    def start_turn(self, turn_id: str, model: str, user_message: str) -> None:
        self._current_turn = TurnTrace(
            turn_id=turn_id,
            model=model,
            user_message=user_message[:1000],
        )

    def record_tool_call_start(self) -> None:
        self._current_call_start = time.time()

    def record_tool_call(
        self, tool_name: str, args: dict[str, object], result_preview: str, is_error: bool
    ) -> None:
        duration = (
            (time.time() - self._current_call_start) * 1000 if self._current_call_start else 0.0
        )
        trace = ToolCallTrace(
            tool_name=tool_name,
            args=args,
            result_preview=result_preview[:500],
            is_error=is_error,
            duration_ms=duration,
        )
        if self._current_turn:
            self._current_turn.tool_calls.append(trace)
        self._current_call_start = 0.0

    def record_thinking(self, thinking: str) -> None:
        if self._current_turn:
            self._current_turn.thinking = thinking[:2000]

    def record_response(self, response: str) -> None:
        if self._current_turn:
            self._current_turn.response_preview = response[:500]

    def record_tokens(self, input_tokens: int, output_tokens: int) -> None:
        if self._current_turn:
            self._current_turn.tokens_input += input_tokens
            self._current_turn.tokens_output += output_tokens

    def end_turn(self, success: bool = True, error: str = "") -> None:
        if self._current_turn:
            self._current_turn.success = success
            self._current_turn.error = error[:500]
            self._current_turn.duration_ms = (time.time() - self._current_turn.timestamp) * 1000
            self._turns.append(self._current_turn)
            self._save()
        self._current_turn = None

    def _save(self) -> None:
        if not self._session_id:
            return
        try:
            data = {
                "session_id": self._session_id,
                "turns": [self._turn_to_dict(t) for t in self._turns],
                "saved_at": time.time(),
            }
            path = self._dir / f"{self._session_id}.json"
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, default=str)
        except OSError:
            pass

    def _turn_to_dict(self, turn: TurnTrace) -> dict[str, object]:
        return {
            "turn_id": turn.turn_id,
            "model": turn.model,
            "user_message": turn.user_message,
            "tool_calls": [
                {
                    "tool_name": tc.tool_name,
                    "args": tc.args,
                    "result_preview": tc.result_preview,
                    "is_error": tc.is_error,
                    "duration_ms": tc.duration_ms,
                }
                for tc in turn.tool_calls
            ],
            "thinking": turn.thinking,
            "response_preview": turn.response_preview,
            "tokens_input": turn.tokens_input,
            "tokens_output": turn.tokens_output,
            "duration_ms": turn.duration_ms,
            "success": turn.success,
            "error": turn.error,
            "timestamp": turn.timestamp,
        }

    def list_sessions(self) -> list[str]:
        return sorted([p.stem for p in self._dir.glob("*.json")], reverse=True)

    def get_session(self, session_id: str) -> list[TurnTrace] | None:
        path = self._dir / f"{session_id}.json"
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            turns = []
            for t in data.get("turns", []):
                turns.append(
                    TurnTrace(
                        turn_id=t["turn_id"],
                        model=t["model"],
                        user_message=t["user_message"],
                        tool_calls=[
                            ToolCallTrace(
                                tool_name=tc["tool_name"],
                                args=tc.get("args", {}),
                                result_preview=tc.get("result_preview", ""),
                                is_error=tc.get("is_error", False),
                                duration_ms=tc.get("duration_ms", 0.0),
                            )
                            for tc in t.get("tool_calls", [])
                        ],
                        thinking=t.get("thinking", ""),
                        response_preview=t.get("response_preview", ""),
                        tokens_input=t.get("tokens_input", 0),
                        tokens_output=t.get("tokens_output", 0),
                        duration_ms=t.get("duration_ms", 0.0),
                        success=t.get("success", True),
                        error=t.get("error", ""),
                    )
                )
            return turns
        except (OSError, json.JSONDecodeError):
            return None

    def generate_regression_test(self, session_id: str, turn_index: int = -1) -> str | None:
        """Generate a pytest test from a recorded turn."""
        turns = self.get_session(session_id)
        if not turns or abs(turn_index) >= len(turns):
            return None

        turn = turns[turn_index]
        lines = [
            '"""Generated regression test from trace."""',
            f"# Session: {session_id}, Turn: {turn.turn_id}",
            f"# Model: {turn.model}, Duration: {turn.duration_ms:.0f}ms",
            "",
            "@pytest.mark.asyncio",
            "async def test_regression_from_trace():",
            f'    """Replay: {turn.user_message[:80]}"""',
        ]
        for tc in turn.tool_calls:
            lines.append(f"    # Tool: {tc.tool_name} ({tc.duration_ms:.0f}ms)")
            if not tc.is_error:
                lines.append(f"    # {tc.result_preview[:120].replace(chr(10), ' ')}")
            else:
                lines.append(f"    # ERROR: {tc.result_preview[:120].replace(chr(10), ' ')}")

        return "\n".join(lines)
