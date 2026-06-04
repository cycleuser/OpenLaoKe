"""Parsers for ``.mcp.json`` (compatibility with the standard MCP config
format) and the OpenLaoKe-native ``[[plugins]]`` config block.

The two formats are merged; project config takes precedence over
``.mcp.json``. Both shapes produce a uniform :class:`PluginEntry`.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from openlaoke.mcp.client import (
    PluginEntry,
    Tier,
    TransportType,
    expand_env,
)

logger = logging.getLogger(__name__)


@dataclass
class _ParseResult:
    entries: list[PluginEntry] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _coerce_transport(value: str) -> TransportType:
    value = (value or "").strip().lower()
    if value in ("http", "streamable-http", "streamable_http"):
        return TransportType.STREAMABLE_HTTP
    if value == "sse":
        return TransportType.SSE
    return TransportType.STDIO


def _coerce_tier(value: str) -> Tier:
    value = (value or "").strip().lower()
    if value == "eager":
        return Tier.EAGER
    if value == "background":
        return Tier.BACKGROUND
    return Tier.LAZY


def from_mcp_json(data: dict[str, Any]) -> _ParseResult:
    """Parse the standard ``.mcp.json`` ``mcpServers`` map."""
    result = _ParseResult()
    servers = data.get("mcpServers") or {}
    if not isinstance(servers, dict):
        result.errors.append("mcpServers must be a dict")
        return result
    for name, cfg in servers.items():
        if not isinstance(cfg, dict):
            result.errors.append(f"server {name!r} is not a dict")
            continue
        transport = _coerce_transport(cfg.get("type", "stdio"))
        entry = PluginEntry(
            name=name,
            transport=transport,
            tier=_coerce_tier(cfg.get("tier", "lazy")),
        )
        if transport == TransportType.STDIO:
            entry.command = cfg.get("command", "")
            entry.args = list(cfg.get("args", []) or [])
            entry.env = {str(k): str(v) for k, v in (cfg.get("env") or {}).items()}
        else:
            entry.url = cfg.get("url", "")
            entry.headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
        result.entries.append(entry)
    return result


def from_plugins_block(plugins: list[dict[str, Any]]) -> _ParseResult:
    """Parse the OpenLaoKe-native ``[[plugins]]`` config list."""
    result = _ParseResult()
    for cfg in plugins:
        if not isinstance(cfg, dict):
            continue
        name = cfg.get("name", "").strip()
        if not name:
            result.errors.append("plugin entry missing 'name'")
            continue
        transport = _coerce_transport(cfg.get("type", "stdio"))
        entry = PluginEntry(
            name=name,
            transport=transport,
            tier=_coerce_tier(cfg.get("tier", "lazy")),
            description=cfg.get("description", ""),
            enabled=bool(cfg.get("enabled", True)),
        )
        if transport == TransportType.STDIO:
            entry.command = cfg.get("command", "")
            entry.args = list(cfg.get("args", []) or [])
            entry.env = {str(k): str(v) for k, v in (cfg.get("env") or {}).items()}
        else:
            entry.url = cfg.get("url", "")
            entry.headers = {str(k): str(v) for k, v in (cfg.get("headers") or {}).items()}
        result.entries.append(entry)
    return result


def load_mcp_json(path: str) -> list[PluginEntry]:
    """Load a ``.mcp.json`` file from disk. Returns ``[]`` on failure."""
    if not path or not os.path.exists(path):
        return []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Failed to load %s: %s", path, exc)
        return []
    if not isinstance(data, dict):
        return []
    return from_mcp_json(data).entries


def merge(
    project_entries: list[PluginEntry],
    mcp_json_entries: list[PluginEntry],
) -> list[PluginEntry]:
    """Merge two plugin lists. Project config wins on name collisions."""
    by_name: dict[str, PluginEntry] = {}
    for entry in mcp_json_entries:
        by_name[entry.name] = entry
    for entry in project_entries:
        by_name[entry.name] = entry
    return list(by_name.values())


def with_expanded_env(entries: list[PluginEntry]) -> list[PluginEntry]:
    """Apply ``${VAR}`` expansion to all string fields."""
    return [expand_env_value(e) for e in entries]


def expand_env_value(entry: PluginEntry) -> PluginEntry:
    """Return a copy of ``entry`` with all string fields expanded."""
    return PluginEntry(
        name=entry.name,
        transport=entry.transport,
        command=expand_env(entry.command) if entry.command else None,
        args=[expand_env(a) for a in entry.args],
        env={k: expand_env(v) for k, v in entry.env.items()},
        url=expand_env(entry.url) if entry.url else None,
        headers={k: expand_env(v) for k, v in entry.headers.items()},
        tier=entry.tier,
        enabled=entry.enabled,
        description=entry.description,
        metadata=dict(entry.metadata),
    )
