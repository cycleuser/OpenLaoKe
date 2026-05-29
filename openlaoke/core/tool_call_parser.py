"""Forgiving multi-format tool call parser.

Handles tool calls from JSON, XML, Hermes, Liquid AI markers, and plain text.
Auto-repairs common small-model mistakes (wrong param names, type mismatches).
"""

from __future__ import annotations

import contextlib
import json
import re
from typing import Any


def extract_tool_calls(
    content: str,
    known_tools: set[str] | None = None,
    reasoning_content: str | None = None,
) -> list[dict[str, Any]]:
    """Extract tool calls from model output in multiple formats.

    Attempts extraction in priority order:
    1. Hermes format: <tool_call>{...}</tool_call>
    2. Liquid AI markers: <|tool_call_start|>[func(kw=val)]<|tool_call_end|>
    3. JSON code fence: ```json ... ```
    4. Tool call code fence: ```tool_call ... ```
    5. Bare JSON object/array
    6. Reasoning content fallback
    """
    if not content and reasoning_content:
        content = reasoning_content or ""

    if not content:
        return []

    tool_calls: list[dict[str, Any]] = []

    tool_calls = _extract_hermes(content)
    if tool_calls:
        return _repair_tool_calls(tool_calls, known_tools)

    tool_calls = _extract_liquid_markers(content)
    if tool_calls:
        return _repair_tool_calls(tool_calls, known_tools)

    tool_calls = _extract_fenced_json(content, "json")
    if tool_calls:
        return _repair_tool_calls(tool_calls, known_tools)

    tool_calls = _extract_fenced_json(content, "tool_call")
    if tool_calls:
        return _repair_tool_calls(tool_calls, known_tools)

    tool_calls = _extract_bare_json(content)
    if tool_calls:
        return _repair_tool_calls(tool_calls, known_tools)

    return []


def _extract_hermes(content: str) -> list[dict[str, Any]]:
    matches = re.findall(r"<tool_call>\s*(.*?)\s*</tool_call>", content, re.DOTALL)
    results = []
    for match in matches:
        parsed = _safe_json_parse(match)
        if parsed:
            results.append(parsed)
    return results


def _extract_liquid_markers(content: str) -> list[dict[str, Any]]:
    pattern = r"<\|tool_call_start\|>\s*(.*?)\s*<\|tool_call_end\|>"
    matches = re.findall(pattern, content, re.DOTALL)
    results = []
    for match in matches:
        parsed = _parse_liquid_function_call(match)
        if parsed:
            results.append(parsed)
    return results


def _parse_liquid_function_call(text: str) -> dict[str, Any] | None:
    match = re.match(r"([\w.]+)\s*\((.*)\)\s*$", text.strip(), re.DOTALL)
    if not match:
        return None
    func_name = match.group(1).strip()
    args_text = match.group(2).strip()
    args = _parse_kwargs(args_text)
    if not func_name:
        return None
    return {"name": func_name, "arguments": args}


def _parse_kwargs(args_text: str) -> dict[str, Any]:
    """Parse Python keyword-argument style string."""
    result: dict[str, Any] = {}
    i = 0
    length = len(args_text)
    while i < length:
        while i < length and args_text[i] in ", ":
            i += 1
        if i >= length:
            break
        eq = args_text.find("=", i)
        if eq < 0:
            break
        key = args_text[i:eq].strip()
        if not key:
            break
        i = eq + 1
        while i < length and args_text[i] == " ":
            i += 1
        if i >= length:
            break
        if args_text[i] in ("'", '"'):
            val, i = _parse_string(args_text, i)
        elif args_text[i] in "{[(":
            val, i = _parse_bracket(args_text, i)
        else:
            end = i
            while end < length and args_text[end] not in ",)]}":
                end += 1
            val = args_text[i:end].strip()
            i = end
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.lower() == "none":
                val = None
            else:
                with contextlib.suppress(ValueError, TypeError):
                    val = float(val) if "." in val else int(val)
        result[key] = val
        while i < length and args_text[i] == " ":
            i += 1
        if i < length and args_text[i] == ",":
            i += 1
    return result


def _parse_string(text: str, start: int) -> tuple[Any, int]:
    quote = text[start]
    i = start + 1
    result = []
    while i < len(text):
        ch = text[i]
        if ch == "\\" and i + 1 < len(text):
            next_ch = text[i + 1]
            if next_ch == "n":
                result.append("\n")
            elif next_ch == "t":
                result.append("\t")
            elif next_ch == "r":
                result.append("\r")
            elif next_ch == "\\":
                result.append("\\")
            elif next_ch in ("'", '"'):
                result.append(next_ch)
            else:
                result.append("\\" + next_ch)
            i += 2
        elif ch == quote:
            i += 1
            return "".join(result), i
        else:
            result.append(ch)
            i += 1
    return "".join(result), i


def _parse_bracket(text: str, start: int) -> tuple[Any, int]:
    bracket_map = {"{": "}", "[": "]", "(": ")"}
    open_b = text[start]
    close_b = bracket_map.get(open_b, open_b)
    depth = 1
    i = start + 1
    while i < len(text) and depth > 0:
        if text[i] == open_b:
            depth += 1
        elif text[i] == close_b:
            depth -= 1
        i += 1
    inner = text[start + 1 : i - 1]
    return inner.strip(), i


def _extract_fenced_json(content: str, fence_type: str) -> list[dict[str, Any]]:
    pattern = rf"```{fence_type}\s*\n?(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)
    results = []
    for match in matches:
        parsed = _safe_json_parse(match.strip())
        if isinstance(parsed, list):
            results.extend(parsed)
        elif isinstance(parsed, dict):
            results.append(parsed)
    return results


def _extract_bare_json(content: str) -> list[dict[str, Any]]:
    idx = 0
    content_len = len(content)
    while idx < content_len:
        ch = content[idx]
        if ch in "{[":
            parsed, end = _try_parse_json_at(content, idx)
            if parsed is not None:
                if isinstance(parsed, list):
                    for item in parsed:
                        if isinstance(item, dict) and "name" in item:
                            return [item]
                elif isinstance(parsed, dict) and "name" in parsed:
                    return [parsed]
                elif isinstance(parsed, dict):
                    idx = end
                    continue
            idx += 1
        else:
            idx += 1
    return []


def _try_parse_json_at(content: str, start: int) -> tuple[Any, int] | tuple[None, int]:
    depth = 0
    in_string = False
    escape = False
    close_char = "]" if content[start] == "[" else "}"
    open_char = content[start]
    i = start
    while i < len(content):
        ch = content[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            i += 1
            continue
        if ch == '"':
            in_string = True
            i += 1
            continue
        if ch == open_char:
            depth += 1
        elif ch == close_char:
            depth -= 1
            if depth == 0:
                try:
                    candidate = content[start : i + 1]
                    candidate = candidate.rstrip().rstrip(",")
                    return json.loads(candidate), i + 1
                except json.JSONDecodeError:
                    return None, i + 1
        i += 1
    return None, i


def _safe_json_parse(text: str) -> Any:
    text = text.strip()
    text = re.sub(r",\s*([}\]])", r"\1", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _repair_tool_calls(
    tool_calls: list[dict[str, Any]],
    known_tools: set[str] | None = None,
) -> list[dict[str, Any]]:
    repaired = []
    for call in tool_calls:
        call = _normalize_call_shape(call)
        if known_tools:
            call = _fuzzy_match_tool_name(call, known_tools)
            call = _convert_args_types(call)
        if call.get("name"):
            repaired.append(call)
    return repaired


def _normalize_call_shape(call: dict[str, Any]) -> dict[str, Any]:
    if "function" in call and isinstance(call["function"], dict):
        func = call["function"]
        return {
            "name": func.get("name", call.get("name", "")),
            "arguments": func.get("arguments", call.get("arguments", {})),
        }
    if "tool" in call:
        call["name"] = call.get("tool", call.get("name", ""))
    if "args" in call and "arguments" not in call:
        call["arguments"] = call["args"]
    if isinstance(call.get("arguments"), str):
        parsed = _safe_json_parse(call["arguments"])
        if isinstance(parsed, dict):
            call["arguments"] = parsed
        else:
            call["arguments"] = {}
    if not isinstance(call.get("arguments"), dict):
        call["arguments"] = {}
    return call


def _fuzzy_match_tool_name(call: dict[str, Any], known_tools: set[str]) -> dict[str, Any]:
    name = str(call.get("name", ""))
    if name in known_tools:
        return call
    for known in known_tools:
        if known.lower() == name.lower():
            call["name"] = known
            return call
    best_distance = 999
    best_match = name
    for known in known_tools:
        dist = _levenshtein(name.lower(), known.lower())
        if dist < best_distance:
            best_distance = dist
            best_match = known
    if best_distance <= 3 and best_distance < len(name) / 2:
        call["name"] = best_match
    return call


def _levenshtein(a: str, b: str) -> int:
    m, n = len(a), len(b)
    if m == 0:
        return n
    if n == 0:
        return m
    prev = list(range(n + 1))
    curr = [0] * (n + 1)
    for i in range(1, m + 1):
        curr[0] = i
        for j in range(1, n + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            curr[j] = min(prev[j] + 1, curr[j - 1] + 1, prev[j - 1] + cost)
        prev, curr = curr, prev
    return prev[n]


def _convert_args_types(call: dict[str, Any]) -> dict[str, Any]:
    """Auto-convert arguments: "42" -> 42, "true" -> True, etc."""
    args = call.get("arguments", {})
    if not isinstance(args, dict):
        return call
    converted = {}
    for k, v in args.items():
        if isinstance(v, str):
            if v.lower() == "true":
                converted[k] = True
            elif v.lower() == "false":
                converted[k] = False
            elif v.lower() == "null" or v.lower() == "none":
                converted[k] = None
            elif re.match(r"^-?\d+$", v):
                converted[k] = int(v)
            elif re.match(r"^-?\d+\.\d+$", v):
                converted[k] = float(v)
            else:
                converted[k] = v
        else:
            converted[k] = v
    call["arguments"] = converted
    return call
