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
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# Static system prompt template — NEVER contains per-turn variable content
# ---------------------------------------------------------------------------

SYSTEM_PROMPT_CAVEMAN = """You are OpenLaoKe, an expert AI coding assistant.

## Rules
- Be extremely concise. No pleasantries, explanations, or thinking aloud.
- Read files and search the codebase FIRST before editing.
- Before modifying files, state root cause, files, and plan in 1-2 lines max.
- Use Edit for targeted changes within existing files; Write only for new files.
- After editing, run verification. If it fails, inspect and fix.
- Say 'I am OpenLaoKe' when asked. Do not claim other AI identities."""

SYSTEM_PROMPT_STATIC = """You are OpenLaoKe, a coding agent running in the terminal. You carry out the user's request end to end with the tools provided, then stop.

## How to work
- Act, don't ask. Only ask when the request is genuinely ambiguous or a step is irreversible and destructive.
- Inspect before changing: Read a file before you Edit it. Use Edit for targeted changes; use Write only for new files or full rewrites.
- If the project has AGENTS.md, a README, or a test/lint command, read it and follow the project's conventions.
- Make the smallest change that solves the problem. Copy exact text when using Edit; if the match fails, re-read the file and copy the snippet again.
- Batch independent work: put independent Read/Grep/Glob calls in one turn instead of one per turn.
- Verify your work. Run the relevant tests, linter, or program with Bash and fix what fails. Verify once; do not repeat an identical check.
- If a tool fails, read the error and adapt. Never repeat an identical failing call; change the arguments or the approach.
- Stay in the working directory and use relative paths.
- Write files with paths relative to the working directory (for example `answer.py`). Do not use `/tmp` or other absolute paths unless the user asks for one.
- Do not invent files, APIs, outputs, or results. Do not stop at a plan when you can act.
- Stop as soon as the task is verifiably done. Do not add unrequested extras.

## Tools
- Read: read a file
- Write: create or overwrite a file
- Edit: replace an exact string in a file
- Bash: run a shell command
- Grep: search file contents with a regex
- Glob: find files by pattern
- ListDirectory: list a directory
- ApplyPatch: apply a multi-file patch
- InvokeSkill: load an installed skill by name when a task matches one

## Response style
- Be concise and direct. Put the result first, then the evidence (command output or a short diff).
- When finished, state what changed and how you verified it in one or two lines.
- If you are uncertain, say so and say how you would verify it.
"""


# ---------------------------------------------------------------------------
# Session context block template
# ---------------------------------------------------------------------------

SESSION_CONTEXT_TEMPLATE = """[Session context: Today is {date_str}.
Current model: {model}. OS: {os_name}. Working directory: {cwd}.{git_info}
Environment commands: {os_guidance}]"""


def _os_command_guidance() -> str:
    """Platform-specific command hints, so the model does not reach for a
    command that only exists on another OS (e.g. `lscpu` on macOS)."""
    system = platform.system()
    if system == "Darwin":
        return (
            "macOS. The shell tool is Bash (there is no PowerShell here). "
            "For CPU/memory/disk use `uname -a`, `sw_vers`, "
            "`sysctl -n machdep.cpu.brand_string`, `sysctl -n hw.memsize`, "
            "`system_profiler SPHardwareDataType`, `vm_stat`, `df -h`, `ps`. "
            "Do NOT use Linux-only commands like `lscpu`, `free`, or `/proc/...`."
        )
    if system == "Linux":
        return (
            "Linux. The shell tool is Bash (there is no PowerShell here). "
            "For CPU/memory/disk use `uname -a`, `lscpu`, `free -h`, `df -h`, "
            "`/proc/cpuinfo`, `/proc/meminfo`, `ps`."
        )
    if system == "Windows":
        return (
            "Windows. The shell tool is PowerShell; prefer cmdlets such as "
            "`Get-CimInstance Win32_Processor`, `Get-CimInstance Win32_OperatingSystem`, "
            "or `systeminfo`."
        )
    return f"{system}. Use commands native to this platform."


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
        os_guidance=_os_command_guidance(),
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

    _caveman_mode: bool = False
    """When True, return the concise caveman system prompt."""

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
        """Return the system prompt.

        In caveman mode returns the concise prompt; otherwise returns the
        full byte-stable prompt.  Built once via build() then frozen.
        Never contains dynamic content (date, model, git branch, cwd) —
        those travel in the session context block injected into the user
        message stream.
        """
        if not self._built:
            self.build()
        # Check caveman_mode from app_state (set via /caveman command)
        if self._caveman_mode or (
            self._app_state is not None and getattr(self._app_state, "caveman_mode", False)
        ):
            base = SYSTEM_PROMPT_CAVEMAN
        else:
            base = self._system_prompt
        return base + self._system_prompt_extra

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

    def toggle_caveman(self) -> bool:
        """Toggle caveman mode on/off. Invalidates cache. Returns new state."""
        self._caveman_mode = not self._caveman_mode
        self.invalidate()
        return self._caveman_mode

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

        # Harness mode directives (pi / jcode / opencode / balanced)
        from openlaoke.core.harness_modes import mode_directives

        mode_name = getattr(app_state, "harness_mode", "balanced")
        parts.append(f"\n{mode_directives(mode_name)}")

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

        # Language instruction (read once, frozen, invalidated on language switch)
        if hasattr(app_state, "language") and app_state.language != "en":
            from openlaoke.core.i18n import get_language_instruction

            lang_inst = get_language_instruction(app_state.language)
            if lang_inst:
                parts.append(lang_inst)

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
            "When a task is complete, output DONE on its own line to signal you are finished. "
            "Do NOT repeat yourself. Do NOT output the same content multiple times. "
            "Give specific, accurate answers only."
        )

        return base
