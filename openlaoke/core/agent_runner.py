"""Agent runner for sub-agent tasks.

Failure semantics (harness fix):
- A sub-agent that fails or is cancelled is *not* a total loss.  Partial
  output (everything the sub-agent produced before the failure) is returned
  to the parent together with a resumable state file on disk, so a follow-up
  Agent call can continue instead of redoing the work.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from contextlib import suppress
from typing import TYPE_CHECKING, Any

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from openlaoke.core.state import AppState
    from openlaoke.types.core_types import TaskState

SUBAGENT_STATE_DIR = "~/.openlaoke/subagent_states"
MAX_RESULT_CHARS = 20000


def _state_path(task_state: TaskState) -> str:
    return os.path.expanduser(f"~/.openlaoke/subagent_{task_state.id}.json")


def _save_subagent_state(
    path: str,
    prompt: str,
    messages: list[dict],
    result_parts: list[str],
    iteration: int,
    status: str,
    error: str | None = None,
) -> None:
    """Save sub-agent state to disk for inspection and resumption."""
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        state = {
            "prompt": prompt,
            "messages": messages,
            "result_parts": result_parts,
            "iteration": iteration,
            "status": status,
            "error": error,
            "saved_at": time.time(),
        }
        # The state file is overwritten on every iteration and is the only thing
        # /agent-resume can read. Truncating it in place means a crash in the
        # middle of a dump leaves JSON that will not parse, and the sub-agent
        # becomes unresumable, so write beside it and rename.
        temporary = f"{path}.{os.getpid()}.tmp"
        try:
            with open(temporary, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
                f.flush()
                os.fsync(f.fileno())
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                with suppress(OSError):
                    os.remove(temporary)
    except Exception as e:
        logger.warning("Failed to save agent runner state: %s", e)


def _load_subagent_state(path: str) -> dict[str, Any] | None:
    """Load a previously saved sub-agent state (for /agent-resume)."""
    try:
        with open(path, encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except Exception:
        return None


def list_resumable_subagents() -> list[dict[str, Any]]:
    """Return recent interrupted sub-agent states, newest first."""
    base = os.path.expanduser("~/.openlaoke")
    out: list[dict[str, Any]] = []
    try:
        for name in sorted(os.listdir(base), reverse=True):
            if not name.startswith("subagent_") or not name.endswith(".json"):
                continue
            path = os.path.join(base, name)
            state = _load_subagent_state(path)
            if not state:
                continue
            if state.get("status") not in ("cancelled", "failed"):
                continue
            out.append(
                {
                    "id": name[len("subagent_") : -len(".json")],
                    "path": path,
                    "status": state.get("status"),
                    "iteration": state.get("iteration", 0),
                    "result_chars": sum(len(p) for p in state.get("result_parts", [])),
                    "error": state.get("error"),
                }
            )
            if len(out) >= 20:
                break
    except OSError:
        pass
    return out


async def run_subagent(
    prompt: str,
    description: str,
    app_state: AppState,
    task_state: TaskState,
    resume_from: str | None = None,
) -> str:
    """Run a sub-agent with the given prompt.

    The sub-agent uses the same API configuration and tools as the parent,
    but with its own isolated conversation context.

    If ``resume_from`` names a saved state file, the sub-agent continues from
    the recorded conversation instead of starting over.

    On failure/cancellation the partial state is saved and a summary of the
    partial output is returned so the parent can reuse it.

    The loop itself lives in :mod:`openlaoke.core.engine`; this function only
    supplies the sub-agent's system prompt, its resumable state file and the
    partial-result contract the parent expects.
    """
    from openlaoke.core.config_wizard import get_proxy_url
    from openlaoke.core.engine import STOP_ERROR, EnginePolicy, run_loop
    from openlaoke.core.multi_provider_api import MultiProviderClient
    from openlaoke.core.tool import ToolRegistry
    from openlaoke.tools import register_all_tools

    registry = ToolRegistry()
    register_all_tools(registry)

    config = app_state.multi_provider_config
    if not config or not config.is_configured():
        return "Sub-agent error: No provider configured"

    app_config = getattr(app_state, "app_config", None)
    proxy = get_proxy_url(app_config) if app_config else None

    api = MultiProviderClient(config, proxy=proxy)
    system_prompt = _build_system_prompt(app_state)

    state_path = _state_path(task_state)
    messages: list[dict[str, Any]] = []
    text_parts: list[str] = []
    offset = 0

    if resume_from:
        saved = _load_subagent_state(os.path.expanduser(resume_from))
        if saved:
            messages = list(saved.get("messages", []))
            text_parts = list(saved.get("result_parts", []))
            offset = int(saved.get("iteration", 0))
    if not messages:
        messages = [{"role": "user", "content": prompt}]

    def save(iteration: int, current: list[dict[str, Any]], parts: list[str], status: str) -> None:
        _save_subagent_state(state_path, prompt, current, parts, offset + iteration, status)

    save(0, messages, text_parts, "running")

    from openlaoke.core.harness_modes import engine_kwargs, get_mode

    mode = get_mode(getattr(app_state, "harness_mode", None))
    policy_kwargs = engine_kwargs(mode)
    policy_kwargs["max_iterations"] = max(1, mode.max_steps - offset)
    policy = EnginePolicy(
        **policy_kwargs,  # type: ignore[arg-type]
        tools=registry.get_all_for_prompt(),
        save_state=save,
    )

    try:
        result = await run_loop(
            app_state=app_state,
            api=api,
            registry=registry,
            system_prompt=system_prompt,
            messages=messages,
            policy=policy,
            model=app_state.session_config.model,
        )
    except asyncio.CancelledError:
        _save_subagent_state(state_path, prompt, messages, text_parts, offset, "cancelled")
        raise
    finally:
        await api.close()

    if result.stop_reason == STOP_ERROR:
        _save_subagent_state(
            state_path, prompt, result.messages, result.text_parts, offset, "failed", result.error
        )
        return _partial_summary(result.text_parts, result.error, state_path)

    _save_subagent_state(
        state_path, prompt, result.messages, result.text_parts, offset, "completed"
    )
    try:
        if os.path.exists(state_path):
            os.remove(state_path)
    except OSError:
        pass

    return "\n".join(part for part in result.text_parts if part) or "(no output)"


def _partial_summary(result_parts: list[str], error: str, state_path: str) -> str:
    """Build a parent-facing summary of a failed sub-agent's partial work."""
    partial_text = "\n".join(result_parts)[:MAX_RESULT_CHARS]
    lines = [
        f"Sub-agent failed: {error}",
        "",
        f"Partial work preserved ({len(result_parts)} intermediate outputs).",
        f"State saved at: {state_path}",
        "A follow-up Agent call with resume_from pointing at that file can continue "
        "instead of starting over.",
        "",
        "=== Partial output ===",
    ]
    if partial_text.strip():
        lines.append(partial_text)
    else:
        lines.append("(no assistant output before failure)")
    return "\n".join(lines)


def _build_system_prompt(app_state: AppState) -> str:
    return (
        "You are a helpful assistant working as a sub-agent. "
        "You have access to tools to help accomplish tasks. "
        "Be concise and focused on the task at hand.\n\n"
        f"Working directory: {app_state.get_cwd()}"
    )
