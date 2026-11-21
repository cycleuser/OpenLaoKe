"""Recover tool calls that a model emitted as text instead of native calls.

Several OpenAI-compatible runtimes return Qwen-style XML inside the assistant
text when their tool-call parser does not recognize the model's format::

    <tool_call>
    <function=Read>
    <parameter=file_path>
    sales.csv
    </parameter>
    </function>
    </tool_call>

The model did the right thing; only the transport failed. Parsing the text here
keeps small local models usable without weakening the native tool-call path.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from openlaoke.types.core_types import ToolUseBlock

_TOOL_BLOCK = re.compile(r"<tool_call>(.*?)</tool_call>", re.DOTALL)
_FUNCTION = re.compile(r"<function=([^>\n]+)>\s*(.*?)\s*</function>", re.DOTALL)
_PARAMETER = re.compile(r"<parameter=([^>\n]+)>\s*(.*?)\s*</parameter>", re.DOTALL)
# Some runtimes strip the wrapper and leave a bare <function=...> block.
_BARE_FUNCTION = re.compile(r"<function=([^>\n]+)>\s*(.*?)\s*</function>", re.DOTALL)


def _coerce(value: str) -> Any:
    text = value.strip()
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if text.lower() in ("null", "none"):
        return None
    if text.startswith(("{", "[")):
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        return text


def _parse_json_block(body: str) -> ToolUseBlock | None:
    try:
        payload = json.loads(body.strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None
    function = payload.get("function") if isinstance(payload.get("function"), dict) else {}
    name = payload.get("name") or function.get("name") or ""
    arguments = payload.get("arguments") or payload.get("parameters") or function.get("arguments")
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            arguments = {}
    if not name:
        return None
    return ToolUseBlock(
        id=str(payload.get("id") or f"call_{uuid.uuid4().hex[:12]}"),
        name=str(name),
        input=arguments if isinstance(arguments, dict) else {},
    )


def _parse_xml_block(body: str) -> list[ToolUseBlock]:
    matches = _FUNCTION.findall(body)
    if not matches and "<function=" in body:
        matches = _BARE_FUNCTION.findall(body)
    calls: list[ToolUseBlock] = []
    for name, inner in matches:
        arguments: dict[str, Any] = {}
        for key, value in _PARAMETER.findall(inner):
            arguments[key.strip()] = _coerce(value)
        calls.append(
            ToolUseBlock(
                id=f"call_{uuid.uuid4().hex[:12]}",
                name=name.strip(),
                input=arguments,
            )
        )
    return calls


def parse_text_tool_calls(text: str) -> tuple[str, list[ToolUseBlock]]:
    """Return visible text plus any tool calls embedded in it.

    Native ``tool_calls`` are untouched; this only recovers text that contains
    a recognizable ``<tool_call>`` or bare ``<function=...>`` block.
    """
    if not text or ("<tool_call>" not in text and "<function=" not in text):
        return text, []

    calls: list[ToolUseBlock] = []
    spans: list[tuple[int, int]] = []

    for match in _TOOL_BLOCK.finditer(text):
        body = match.group(1)
        json_call = _parse_json_block(body)
        parsed = [json_call] if json_call else _parse_xml_block(body)
        if parsed:
            calls.extend(parsed)
            spans.append(match.span())

    if not calls:
        for match in _BARE_FUNCTION.finditer(text):
            parsed = _parse_xml_block(match.group(0))
            if parsed:
                calls.extend(parsed)
                spans.append(match.span())

    if not calls:
        return text, []

    cleaned = text
    for start, end in reversed(spans):
        cleaned = cleaned[:start] + cleaned[end:]
    return cleaned.strip(), calls
