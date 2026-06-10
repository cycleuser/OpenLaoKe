"""Cache-aware guard for prompt cache hit rate optimization.

Core responsibilities:
1. Build a byte-stable system prompt ONCE per session (never rebuilt mid-session)
2. Inject dynamic content (time, model, OS, git branch) as [session context] blocks
   appended to user messages, NOT the system prompt
3. Place double cache_control breakpoints on the last 2 real messages
   (rolling dual-marker pattern — survives single-step tool-call rollback)
4. Skip system_injected messages when placing cache markers

Design principles:
  - Frozen system prompt — built once at session init, never rebuilt
  - Dual cache markers — two markers covering the tail boundary
  - Session context blocks — dynamic info in user message stream
"""

from __future__ import annotations

import os
import platform
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlaoke.core.state import AppState


# ---------------------------------------------------------------------------
# Static system prompt template — NEVER contains per-turn variable content
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_STATIC = """You are OpenLaoKe, an expert AI coding assistant designed to help with \
software engineering tasks. You can read and write files, run shell commands, \
search codebases, and spawn sub-agents for parallel work.

## Core Principles
- Be concise and direct in your responses
- Always verify your work after making changes
- Read files before editing them to understand context
- Use the Edit tool for targeted changes, Write for new files
- Run tests to verify your changes work
- Never commit secrets or API keys
- Follow the existing code style and conventions

## Tool Usage Guidelines
- Read files before editing to understand the current state
- Use Glob to find files when you don't know the exact path
- Use Grep to search for patterns across multiple files
- Use Bash for running commands, tests, and git operations
- Use Edit for small targeted changes, Write for new files
- Use Agent to delegate independent parallel tasks

IMPORTANT: When using tools, ALWAYS provide ALL required parameters:
- Write tool: requires both 'file_path' AND 'content'
- Edit tool: requires 'file_path', 'old_string', AND 'new_string'
- Bash tool: requires 'command'
- Read tool: requires 'file_path'
Never omit required parameters. If you're unsure about a parameter, ask the user.

## Web Research
- You have internet access: use WebSearch to find current information and WebFetch to read pages
- Use WebSearch for: weather, news, documentation, version info, API references, or any factual lookup
- ALWAYS search the web rather than guessing or inventing facts you're not sure about
- Do NOT invent freshness-sensitive facts (weather, prices, dates, versions) when you can search
- When searching, summarize findings and cite source URLs

## Response Format
- Keep explanations concise and focused
- Show relevant code snippets when explaining
- Always explain what you're doing and why
- If uncertain, say so and suggest how to verify

## Anti-AI Quality Standards (MANDATORY)

CRITICAL: Your output will be checked for AI-typical patterns. You MUST avoid:

1. **Empty numbered lists** - Never write lists without substantive content
   ❌ BAD: "Benefits include: 1. Speed 2. Quality 3. Cost"
   ✅ GOOD: "The system achieves 2.3s average response time (34% faster than baseline), \
94% code accuracy on HumanEval benchmark, and $0.003 per query operational cost."

2. **Vague claims without evidence** - Every claim needs SPECIFIC numbers or citations
   ❌ BAD: "significant improvement", "novel approach", "state-of-the-art"
   ✅ GOOD: "45% reduction in latency (p<0.01, n=1000 trials)", \
"as demonstrated in Smith et al. [3]"

3. **AI-typical phrases** - Avoid these patterns:
   - "Systems could enable:"
   - "Improvements include:"
   - "The main contributions are:"
   - Generic bullet points as paragraphs

4. **Missing technical depth** - Explain HOW and WHY, not just WHAT
   ❌ BAD: "The system uses caching for performance."
   ✅ GOOD: "The system implements LRU caching with 256MB capacity in Redis, \
achieving 89% cache hit rate and reducing database queries by 67% (measured over 10k requests)."

5. **No real citations** - Use WebSearch to find REAL papers
   - Always cite actual papers with [number] format
   - Reference specific code with file:line format
   - Include actual measurements and numbers
VERIFICATION: Before finishing ANY task:
- Does every paragraph have specific details (numbers, citations, code refs)?
- Are there more than 3 bullet points without explanation?
- Can you replace generic phrases with specific evidence?"""


# ---------------------------------------------------------------------------
# Session context block template
# ---------------------------------------------------------------------------

SESSION_CONTEXT_TEMPLATE = """[Session context: Today is {date_str}.
Current model: {model}. OS: {os_name}. Working directory: {cwd}.{git_info}]"""


def _build_session_context(
    app_state: object,
    model: str = "",
    date_str: str = "",
) -> str:
    """Build the [session context] block that travels in the user message stream.

    This is the ONLY place where per-session variable information lives.
    It is injected as a user message with system_injected=True flag,
    so it never touches the system prompt and is skipped for cache markers.
    """
    cwd = getattr(app_state, "cwd", "") or os.getcwd()
    if not date_str:
        date_str = time.strftime("%Y-%m-%d, %A")
    os_name = f"{platform.system()} {platform.release()}"

    git_info = ""
    try:
        import subprocess

        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            branch = result.stdout.strip()
            if branch and branch != "HEAD":
                git_info = f" Git branch: {branch}."
    except Exception:
        pass

    return SESSION_CONTEXT_TEMPLATE.format(
        date_str=date_str,
        model=model,
        os_name=os_name,
        cwd=cwd,
        git_info=git_info,
    )


# ---------------------------------------------------------------------------
# CacheGuard — the single orchestrator for cache-friendly prompting
# ---------------------------------------------------------------------------


@dataclass
class CacheGuard:
    """Manages system prompt lifecycle and cache breakpoints for a session.

    Usage in the REPL loop::

        guard = CacheGuard(app_state)

        # Once per turn, BEFORE building messages:
        session_ctx = guard.ensure_session_context(model="claude-sonnet-4-6")

        # Build the system prompt (stable, cached):
        system_prompt = guard.system_prompt  # property — built once

        # After constructing messages, apply cache markers:
        messages = guard.apply_cache_markers(messages)

        # The session context block is inserted into the message stream:
        if session_ctx:
            messages.append({"role": "user", "content": session_ctx,
                             "system_injected": True})
    """

    # ---- configuration ----------------------------------------------------

    _app_state: object
    """Weak reference to AppState for accessing skills, knowledge, etc."""

    _system_prompt: str = ""
    """The byte-stable system prompt, built once and frozen."""

    _system_prompt_extra: str = ""
    """Extra suffix appended after static prompt (skills, knowledge, suffix).
    Built once at session start. Frozen thereafter."""

    _last_session_context_date: str = ""
    """Date of the last session context injection. Used to detect day changes."""

    _last_session_context_model: str = ""
    """Model at last injection. Used to detect model switches."""

    _built: bool = False
    """Whether build() has been called (one-shot)."""

    # ---- public API -------------------------------------------------------

    def __init__(self, app_state: object | None = None) -> None:
        self._app_state = app_state

    @property
    def app_state(self) -> object | None:
        return self._app_state

    @app_state.setter
    def app_state(self, value: object) -> None:
        self._app_state = value

    # -- system prompt ------------------------------------------------------

    @property
    def system_prompt(self) -> str:
        """Return the byte-stable system prompt.

        Built once via build() then frozen.  Never contains dynamic content
        (date, model, git branch, cwd) — those travel in the session context
        block injected into the user message stream.
        """
        if not self._built:
            self.build()
        return self._system_prompt + self._system_prompt_extra

    def build(self) -> str:
        """One-shot: build the system prompt and freeze it.

        Safe to call multiple times — only the first call does work.
        """
        if self._built:
            return self.system_prompt

        self._system_prompt = SYSTEM_PROMPT_STATIC
        self._system_prompt_extra = self._build_extra()
        self._built = True
        return self.system_prompt

    def invalidate(self) -> None:
        """Force rebuild on next access.

        Use ONLY when switching to a new session or after a structural
        change (e.g., skills reload that MUST be visible).  Normal session
        context changes (date, model, git branch) do NOT invalidate.
        """
        self._built = False
        self._system_prompt = ""
        self._system_prompt_extra = ""

    def _build_extra(self) -> str:
        """Build the once-per-session extra suffix.

        This includes active skills, knowledge loader output, and
        user-configured system_prompt_suffix — all read ONCE at session
        start.  Mid-session changes are communicated via [session context].
        """
        app_state = self._app_state
        if app_state is None:
            return ""

        parts: list[str] = []

        # Active skills (read once, frozen)
        if hasattr(app_state, "active_skills") and app_state.active_skills:
            from openlaoke.core.skill_system import get_skill_system_prompt

            skill_prompt = get_skill_system_prompt(app_state.active_skills)
            if skill_prompt:
                parts.append(f"\n## Active Skills\n{skill_prompt}")

        # User-configured suffix
        if hasattr(app_state, "session_config"):
            suffix = app_state.session_config.system_prompt_suffix
            if suffix:
                parts.append(f"\n## Additional Instructions\n{suffix}")

        # Knowledge loader (read once, frozen)
        if hasattr(app_state, "knowledge_loader") and app_state.knowledge_loader is not None:
            try:
                knowledge = app_state.knowledge_loader.format_for_prompt("")
                if knowledge:
                    parts.append(f"\n{knowledge}")
            except Exception:
                pass

        return "\n".join(parts) if parts else ""

    # -- session context ----------------------------------------------------

    def ensure_session_context(
        self,
        model: str = "",
        force: bool = False,
    ) -> str | None:
        """Return a [session context] block if one is needed this turn.

        A new block is emitted when:
        - This is the first call (no previous injection) — happens at session start
        - The date changed (crossed midnight) — prevents stale time context
        - The model changed (user switched models mid-session) — model self-awareness
        - force=True (caller explicitly requests re-injection)

        Returns None if no injection is needed this turn.
        The caller should insert the returned string as a user message with
        system_injected=True metadata.
        """
        if not self._built:
            self.build()

        today = time.strftime("%Y-%m-%d")

        needs_injection = (
            not self._last_session_context_date  # first call ever
            or today != self._last_session_context_date  # day change
            or (model and model != self._last_session_context_model)  # model switch
            or force
        )

        if not needs_injection:
            return None

        self._last_session_context_date = today
        if model:
            self._last_session_context_model = model

        return _build_session_context(
            self._app_state,
            model=model,
            date_str=time.strftime("%Y-%m-%d, %A"),
        )

    # -- cache markers ------------------------------------------------------

    @staticmethod
    def apply_cache_markers(
        messages: list[dict[str, Any]],
        provider_type: str = "",
    ) -> list[dict[str, Any]]:
        """Apply double cache_control breakpoints to messages.

        Marks the LAST TWO non-system_injected messages with
        cache_control={"type": "ephemeral"}.  This implements the
        rolling dual-marker pattern:

        - Two markers cover the tail boundary — if the model retries
          a tool call (single-step rollback), the older marker still
          hits because it falls on a message that still exists.

        - system_injected messages are SKIPPED — they are ephemeral
          [session context] blocks that change between turns, so
          marking them would waste a cache write.

        Only adds markers for Anthropic providers; OpenAI/DeepSeek use
        automatic prefix caching which works differently.
        """
        if not messages:
            return messages

        # Find the last two non-system_injected messages
        marker_indices: list[int] = []
        for i in range(len(messages) - 1, -1, -1):
            msg = messages[i]
            if not msg.get("system_injected"):
                marker_indices.append(i)
                if len(marker_indices) >= 2:
                    break

        if not marker_indices:
            return messages

        # Apply markers
        for idx in marker_indices:
            msg = messages[idx]
            content = msg.get("content", "")
            role = msg.get("role", "user")

            # For Anthropic, content blocks need cache_control
            # We wrap string content in a content-block structure
            if isinstance(content, str) and content:
                if "cache_control" not in msg:
                    # Use Anthropic content-block format
                    blocks: list[dict[str, Any]] = [
                        {
                            "type": "text",
                            "text": content,
                            "cache_control": {"type": "ephemeral"},
                        }
                    ]
                    # Preserve existing tool-related fields
                    new_msg: dict[str, Any] = {"role": role, "content": blocks}
                    for key in ("tool_calls", "tool_call_id", "name"):
                        if key in msg:
                            new_msg[key] = msg[key]
                    messages[idx] = new_msg
            elif isinstance(content, list):
                # Already content blocks — add cache_control to the last text block
                found_text = False
                for block in reversed(content):
                    if isinstance(block, dict) and block.get("type") == "text":
                        if "cache_control" not in block:
                            block["cache_control"] = {"type": "ephemeral"}
                        found_text = True
                        break
                if not found_text and content:
                    last = content[-1]
                    if isinstance(last, dict) and "cache_control" not in last:
                        last["cache_control"] = {"type": "ephemeral"}

        return messages

    # -- small-model helpers ------------------------------------------------

    @staticmethod
    def build_compact_prompt(app_state: object, user_input: str = "") -> str:
        """Build minimal prompt for local/small models."""
        os_name = f"{platform.system()} {platform.release()}"
        cwd = getattr(app_state, "cwd", "") or os.getcwd()

        base = (
            f"You are OpenLaoKe, an open-source AI coding assistant running on {os_name}. "
            "You help users with programming tasks: writing code, debugging, explaining concepts. "
            "Be concise and direct. Always answer in the user's language. "
            f"Working directory: {cwd}. "
        )
        base += (
            "If asked who you are, say you are OpenLaoKe, an AI coding assistant. "
            f"If asked about the OS, say {os_name}. "
            "CRITICAL: Only use tools for file operations or running commands. "
            "For greetings (hi, hello), questions about yourself (who are you, what can you do), "
            "or simple conversation, respond DIRECTLY in text WITHOUT using any tools. "
            "Do NOT use Glob/Read/Bash for conversational questions. "
            "IMPORTANT: You have WebSearch for web queries (weather, news, docs, facts). "
            "ALWAYS search the web instead of guessing or saying you don't know. "
            "When a task is complete, output DONE on its own line to signal you are finished. "
            "Do NOT repeat yourself. Do NOT output the same content multiple times. "
            "Give specific, accurate answers only."
        )

        if user_input:
            try:
                from openlaoke.agent.context import ContextBuilder

                ctx = ContextBuilder()
                runtime = ctx.build_runtime_block(
                    user_input=user_input,
                    cwd=cwd,
                )
                if runtime:
                    return f"{base}\n\n{runtime}"
            except Exception:
                pass

            from openlaoke.core.distilled_templates import DistilledTemplateManager

            manager = DistilledTemplateManager()
            context = manager.build_context(user_input, max_tokens=200)
            if context:
                return f"{base}\n\n{context}"

        return base
