"""Passive memory extraction hooks for automatic memory accumulation.

Hooks that run on tool execution events and extract key information
into the SQLite memory store without user intervention.
"""

from __future__ import annotations

import hashlib
import logging
import re
import time

from openlaoke.core.hook_system import HookInput, HookOutput
from openlaoke.core.memory.sqlite_store import MemoryRecord, SQLiteMemoryStore, TimelineEvent

logger = logging.getLogger(__name__)

FILE_PATTERNS = {
    "config": [r"\.(json|yaml|yml|toml|ini|cfg|conf)$", r"(config|settings|env)\.py$"],
    "test": [r"test_.*\.py$", r".*_test\.py$", r"tests?/"],
    "doc": [r"\.(md|rst|txt|doc)$", r"README", r"CHANGELOG", r"docs?/"],
    "src": [r"\.(py|js|ts|rs|go|java|cpp|c|h|hpp)$"],
}

TOOL_MEMORY_RULES = {
    "bash": {
        "install": r"(?:pip|npm|cargo|apt|brew|uv)\s+(?:install|add|get)",
        "test": r"(?:pytest|cargo\s+test|npm\s+test|go\s+test|make\s+test)",
        "git": r"git\s+(?:commit|push|pull|merge|rebase|branch)",
        "build": r"(?:make|cargo\s+build|npm\s+run\s+build|python\s+setup\.py)",
    },
    "edit": {
        "fix": r"(?:fix|bug|issue|error|crash|leak|race)",
        "refactor": r"(?:refactor|rename|move|extract|restructure)",
        "feature": r"(?:add|implement|create|new|feature)",
    },
    "write": {
        "create": r".*",
    },
    "read": {
        "explore": r".*",
    },
}


def _extract_key_info(text: str, max_len: int = 300) -> str:
    lines = text.strip().split("\n")
    key_lines = []
    for line in lines:
        line = line.strip()
        if not line or len(line) < 5:
            continue
        if (
            any(
                kw in line.lower()
                for kw in ["error", "failed", "warning", "traceback", "exception"]
            )
            or any(kw in line.lower() for kw in ["success", "passed", "ok", "done", "complete"])
            or line.startswith(("import ", "from ", "def ", "class ", "async def "))
        ):
            key_lines.append(line)
    if not key_lines:
        key_lines = lines[:5]
    result = "\n".join(key_lines)[:max_len]
    return result


def _detect_memory_type(content: str, tool_name: str, result: str) -> str:
    content_lower = content.lower()
    result_lower = result.lower()
    if any(kw in content_lower for kw in ["fix", "bug", "error", "crash", "leak", "fail"]):
        return "lesson"
    if any(kw in content_lower for kw in ["prefer", "always", "never", "don't", "use "]):
        return "preference"
    if tool_name == "edit":
        if any(kw in result_lower for kw in ["error", "fail", "syntax"]):
            return "lesson"
        return "fact"
    if tool_name == "bash":
        if any(kw in result_lower for kw in ["error", "fail", "not found", "permission"]):
            return "lesson"
        if any(kw in content_lower for kw in ["install", "upgrade", "update"]):
            return "config"
    return "fact"


def _extract_concepts(text: str) -> list[str]:
    patterns = [
        r"(?:module|class|function|method|file|package|library|framework)\s+['\"]?(\w+)",
        r"(?:using|import|from|require)\s+(?:the\s+)?['\"]?(\w[\w.-]+)",
        r"(?:error|bug|issue)\s+(?:in|with|on)\s+['\"]?(\w[\w.-]+)",
        r"(\w+)\s+(?:module|class|function|method|file)",
    ]
    concepts = []
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            concept = match.group(1)
            if len(concept) > 2 and concept not in concepts:
                concepts.append(concept)
    return concepts[:5]


def tool_execute_after_memory_hook(input_data: HookInput, output: HookOutput) -> None:
    tool_name = input_data.tool_name
    tool_args = input_data.tool_args
    tool_result = input_data.tool_result
    tool_error = input_data.tool_error
    session_id = input_data.session_id

    if not tool_name or tool_name in ("glob", "ls", "todo"):
        return

    summary_parts = [f"{tool_name}"]
    if tool_name == "bash" and "command" in tool_args:
        cmd = tool_args["command"][:100]
        summary_parts.append(f"executed: {cmd}")
    elif tool_name in ("edit", "write", "read") and "file_path" in tool_args:
        summary_parts.append(f"on {tool_args['file_path']}")

    summary = " ".join(summary_parts)

    event = TimelineEvent(
        id=f"evt_{hashlib.md5(f'{session_id}{tool_name}{time.time()}'.encode()).hexdigest()[:12]}",
        event_type=f"tool_{tool_name}",
        session_id=session_id,
        tool_name=tool_name,
        summary=summary,
        details={
            "args_preview": {k: str(v)[:100] for k, v in list(tool_args.items())[:3]},
            "has_error": bool(tool_error),
        },
        created_at=time.time(),
    )

    try:
        store = SQLiteMemoryStore()
        store.add_timeline_event(event)

        if tool_error or (tool_result and len(tool_result) > 50):
            content = _extract_key_info(tool_error or tool_result or "")
            if content and len(content) > 10:
                memory_type = _detect_memory_type(
                    str(tool_args), tool_name, tool_error or tool_result or ""
                )
                concepts = _extract_concepts(
                    str(tool_args) + " " + (tool_result or "") + " " + (tool_error or "")
                )
                record = MemoryRecord(
                    id=f"mem_{hashlib.md5(f'{tool_name}{content[:50]}{session_id}'.encode()).hexdigest()[:12]}",
                    content=content,
                    memory_type=memory_type,
                    key=f"{tool_name}_{memory_type}",
                    tags=concepts + [tool_name, memory_type],
                    source_session=session_id,
                    source_tool=tool_name,
                    confidence=0.7 if tool_error else 0.5,
                    importance=0.8 if tool_error else 0.4,
                    metadata={
                        "tool_args_preview": {
                            k: str(v)[:200] for k, v in list(tool_args.items())[:3]
                        },
                    },
                )
                store.store(record)
    except Exception as e:
        logger.debug(f"Memory extraction hook error: {e}")


def session_start_memory_hook(input_data: HookInput, output: HookOutput) -> None:
    session_id = input_data.session_id
    if not session_id:
        return

    try:
        store = SQLiteMemoryStore()
        recent_events = store.query_timeline(session_id=session_id, limit=5)
        if recent_events:
            event = TimelineEvent(
                id=f"evt_{hashlib.md5(f'{session_id}_session_resume_{time.time()}'.encode()).hexdigest()[:12]}",
                event_type="session_resume",
                session_id=session_id,
                tool_name="",
                summary=f"Session resumed, {len(recent_events)} recent events",
                details={"recent_events": [e.to_dict() for e in recent_events]},
                created_at=time.time(),
            )
            store.add_timeline_event(event)
    except Exception as e:
        logger.debug(f"Session start memory hook error: {e}")


def user_prompt_memory_hook(input_data: HookInput, output: HookOutput) -> None:
    messages = input_data.metadata.get("messages", [])
    session_id = input_data.session_id
    if not messages:
        return

    last_user_msg = ""
    for msg in reversed(messages):
        if msg.get("role") == "user":
            content = msg.get("content", "")
            if isinstance(content, str):
                last_user_msg = content
                break

    if not last_user_msg or len(last_user_msg) < 10:
        return

    correction_patterns = [
        r"(?:no[,!]?\s+)?(?:you\s+should|please\s+)?use\s+(.+)",
        r"don'?t\s+use\s+(.+?)[,.]\s+use\s+(.+)",
        r"(?:actually|instead)[,.]?\s+use\s+(.+)",
        r"next\s+time[,.]?\s+use\s+(.+)",
        r"(?:I\s+)?prefer\s+(.+)",
        r"always\s+use\s+(.+)",
        r"记住[：:]\s*(.+)",
        r"以后[都]?用\s+(.+)",
        r"不要[再用]?(\w+)",
    ]

    for pattern in correction_patterns:
        m = re.search(pattern, last_user_msg, re.IGNORECASE)
        if m:
            content = m.group(m.lastindex or 1).strip() if m.lastindex else last_user_msg
            if len(content) > 3:
                try:
                    store = SQLiteMemoryStore()
                    record = MemoryRecord(
                        id=f"mem_{hashlib.md5(f'correction_{content[:50]}{time.time()}'.encode()).hexdigest()[:12]}",
                        content=f"User preference: {content}",
                        memory_type="preference",
                        key=f"user_pref_{content[:30]}",
                        tags=["user_preference", "correction"],
                        source_session=session_id,
                        confidence=0.9,
                        importance=0.9,
                    )
                    store.store(record)
                except Exception as e:
                    logger.debug(f"User prompt memory hook error: {e}")
            break
