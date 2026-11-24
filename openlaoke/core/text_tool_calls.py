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

Three dialects are recognised inside a ``<tool_call>`` wrapper:

1. JSON payload (Hermes / Qwen-Agent): ``{"name": ..., "arguments": {...}}``.
2. ``<function=Name>`` … ``<parameter=key>value</parameter>`` (Qwen).
3. ``Name<arg_key>key</arg_key><arg_value>value</arg_value>…`` (GLM, Spark,
   LFM2 tool-tuned checkpoints). The tool name sits right after the tag and each
   argument is an ``arg_key``/``arg_value`` pair; no closing ``</function>``.
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

# GLM / Spark / LFM2 dialect: Name<arg_key>k</arg_key><arg_value>v</arg_value>
_NAME = r"[A-Za-z_][A-Za-z0-9_.-]*"
_ARG_KEY = re.compile(r"<arg_key>(.*?)</arg_key>", re.DOTALL)
_ARG_VALUE = re.compile(r"<arg_value>(.*?)</arg_value>", re.DOTALL)
_ARGTAG_WHOLE = re.compile(rf"^\s*({_NAME})\s*(.*?)\s*(?:</tool_call>)?\s*$", re.DOTALL)
# A model that never emits a closing tag still gets one shot at recovery.
_TRAILING_BLOCK = re.compile(r"<tool_call>((?:(?!<tool_call>).)*)$", re.DOTALL)


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
    raw_function = payload.get("function")
    function = raw_function if isinstance(raw_function, dict) else {}
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


def _parse_argtag_block(body: str) -> list[ToolUseBlock]:
    """Parse ``Name<arg_key>k</arg_key><arg_value>v</arg_value>`` calls."""
    if "<arg_key>" not in body or "<arg_value>" not in body:
        return []
    head = _ARG_KEY.search(body)
    if head is None:
        return []
    match = _ARGTAG_WHOLE.match(body)
    if match is None:
        return []
    name, rest = match.group(1), match.group(2)
    if "<arg_key>" not in rest:
        return []
    keys = _ARG_KEY.findall(rest)
    values = _ARG_VALUE.findall(rest)
    if not keys or len(keys) != len(values):
        return []
    arguments = {key.strip(): _coerce(value) for key, value in zip(keys, values, strict=False)}
    arguments = {k: v for k, v in arguments.items() if k}
    if not arguments:
        return []
    return [ToolUseBlock(id=f"call_{uuid.uuid4().hex[:12]}", name=name.strip(), input=arguments)]


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
        parsed = [json_call] if json_call else (_parse_xml_block(body) or _parse_argtag_block(body))
        if parsed:
            calls.extend(parsed)
            spans.append(match.span())

    if not calls:
        for match in _BARE_FUNCTION.finditer(text):
            parsed = _parse_xml_block(match.group(0))
            if parsed:
                calls.extend(parsed)
                spans.append(match.span())

    # Last resort: an unterminated <tool_call> block. Small models drop the
    # closing tag often enough that throwing the call away wastes a whole turn.
    if not calls:
        for match in _TRAILING_BLOCK.finditer(text):
            parsed = _parse_argtag_block(match.group(1))
            if parsed:
                calls.extend(parsed)
                spans.append(match.span())

    if not calls:
        return text, []

    cleaned = text
    for start, end in reversed(spans):
        cleaned = cleaned[:start] + cleaned[end:]
    return cleaned.strip(), calls
