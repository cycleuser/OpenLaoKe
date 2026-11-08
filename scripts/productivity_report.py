"""Productivity report from the saved sessions.

Reads `~/.openlaoke/sessions/*.json` and writes Markdown: per-day activity, what
was worked on (by directory), which tools carried the work, and how large the
transcripts grew. Nothing leaves the machine, and no model is called - it is
arithmetic over files you already have.

    python scripts/productivity_report.py
    python scripts/productivity_report.py --days 14 --out report.md
"""

from __future__ import annotations

import argparse
import json
import os
import time
from collections import Counter, defaultdict
from typing import Any

DEFAULT_DIR = os.path.join(os.path.expanduser("~"), ".openlaoke", "sessions")


def _load(directory: str) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    if not os.path.isdir(directory):
        return payloads
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, filename), encoding="utf-8") as handle:
                payloads.append(json.load(handle))
        except (OSError, json.JSONDecodeError):
            continue
    return payloads


def collect(directory: str, days: float = 0.0) -> dict[str, Any]:
    cutoff = time.time() - days * 86400 if days > 0 else 0.0
    per_day: dict[str, dict[str, int]] = defaultdict(
        lambda: {"sessions": 0, "user": 0, "assistant": 0, "messages": 0, "tokens": 0}
    )
    per_project: Counter[str] = Counter()
    tools: Counter[str] = Counter()
    total_tokens = 0
    total_sessions = 0

    for payload in _load(directory):
        created = float(payload.get("created_at") or 0.0)
        if cutoff and created and created < cutoff:
            continue
        stamp = time.strftime("%Y-%m-%d", time.localtime(created or time.time()))
        bucket = per_day[stamp]
        bucket["sessions"] += 1
        total_sessions += 1

        messages = payload.get("messages") or []
        bucket["messages"] += len(messages)
        for message in messages:
            role = str((message or {}).get("role", ""))
            if role.endswith("user"):
                bucket["user"] += 1
            elif role.endswith("assistant"):
                bucket["assistant"] += 1

        usage = payload.get("token_usage") or {}
        tokens = int(usage.get("input_tokens", 0) or 0) + int(usage.get("output_tokens", 0) or 0)
        bucket["tokens"] += tokens
        total_tokens += tokens

        per_project[payload.get("cwd") or "(unknown)"] += 1

        for name, count in (payload.get("tool_call_counts") or {}).items():
            tools[str(name)] += int(count or 0)

    return {
        "per_day": dict(sorted(per_day.items())),
        "per_project": per_project,
        "tools": tools,
        "total_tokens": total_tokens,
        "total_sessions": total_sessions,
    }


def render(data: dict[str, Any], days: float = 0.0) -> str:
    window = f"the last {days:g} days" if days > 0 else "all saved sessions"
    lines = [
        "# OpenLaoKe productivity report",
        "",
        f"Window: {window}. Sources: local session files only.",
        f"Sessions: {data['total_sessions']}; tokens (in + out): {data['total_tokens']:,}.",
        "",
        "## Activity by day",
        "",
        "| Day | Sessions | User msgs | Assistant msgs | Messages | Tokens |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for day, bucket in data["per_day"].items():
        lines.append(
            f"| {day} | {bucket['sessions']} | {bucket['user']} | {bucket['assistant']} "
            f"| {bucket['messages']} | {bucket['tokens']:,} |"
        )
    if not data["per_day"]:
        lines.append("| (no sessions found) | - | - | - | - | - |")

    lines += ["", "## Where the work happened", "", "| Directory | Sessions |", "| --- | --- |"]
    for path, count in data["per_project"].most_common(15):
        lines.append(f"| `{path}` | {count} |")
    if not data["per_project"]:
        lines.append("| (none) | - |")

    lines += ["", "## Tool usage", "", "| Tool | Calls |", "| --- | --- |"]
    for name, count in data["tools"].most_common(20):
        lines.append(f"| {name} | {count:,} |")
    if not data["tools"]:
        lines.append("| (no recorded calls) | - |")

    lines += [
        "",
        "## How to read this",
        "",
        "- Token counts come from the usage blocks a provider reported; sessions from",
        "  providers that do not report usage show zero rather than an estimate.",
        "- Tool counts only exist for sessions saved after call counting landed, so an",
        "  older session can show messages but no tool rows.",
        "- A directory appearing often is activity, not necessarily progress.",
        "",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", default=DEFAULT_DIR, help="session directory")
    parser.add_argument("--days", type=float, default=0, help="only the last N days; 0 means all")
    parser.add_argument("--out", default="", help="write here instead of stdout")
    args = parser.parse_args(argv)

    data = collect(args.dir, args.days)
    text = render(data, args.days)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as handle:
            handle.write(text)
        print(f"wrote {args.out} ({len(text)} chars, {data['total_sessions']} sessions)")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
