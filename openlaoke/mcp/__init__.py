"""MCP (Model Context Protocol) integration.

Two transport modes:

* **stdio** — spawn a child process and speak JSON-RPC on its stdin/stdout.
* **streamable-http** — connect to an HTTP endpoint that speaks the
  Streamable-HTTP transport.

MCP tools are exposed to the agent with the namespaced name
``mcp__<server>__<tool>``. Resources and prompts are exposed as tools
too, with their own namespacing.
"""

from __future__ import annotations
