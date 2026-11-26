"""Conversation-shape fixes applied before a request goes to a provider.

OpenAI-compatible servers reject or misbehave on two things every agent loop
produces eventually: a conversation that starts with an assistant turn (after a
trimmed history) and two adjacent turns with the same role (after a retry or a
merged tool batch).
"""

from __future__ import annotations

from typing import Any


def enforce_role_alternation(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge consecutive same-role messages and make the conversation user-first.

    Tool-role messages are never merged: OpenAI-compatible providers require one
    tool message per ``tool_call_id``, so collapsing two of them loses a result.

    Returns copies, leaving *messages* untouched.
    """
    if not messages:
        return messages

    fixed: list[dict[str, Any]] = []
    for msg in messages:
        if msg.get("role") == "tool":
            fixed.append(dict(msg))
            continue
        if fixed and fixed[-1].get("role") == msg.get("role"):
            prev = fixed[-1]
            content = prev.get("content", "")
            new_content = msg.get("content", "")
            if isinstance(content, str) and isinstance(new_content, str):
                prev["content"] = content + "\n" + new_content
            else:
                prev["content"] = (
                    content if isinstance(content, list) else [{"type": "text", "text": str(content)}]
                )
                prev["content"] += (
                    new_content
                    if isinstance(new_content, list)
                    else [{"type": "text", "text": str(new_content)}]
                )
        else:
            fixed.append(dict(msg))

    # A trimmed history can start with the assistant turn whose user prompt was
    # dropped; every provider here needs a user turn first.
    while fixed and fixed[0].get("role") not in ("user", "system"):
        fixed.pop(0)

    return fixed
