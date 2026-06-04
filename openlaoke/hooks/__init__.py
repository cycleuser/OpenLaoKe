"""Hook system with 11 lifecycle events.

Lifecycle hooks are the place where plugins and extensions plug into
the agent loop. Each hook can mutate its output. A short-circuit
``Handled`` flag allows a hook to fully take over a behavior.

Events (inspired by the well-known agent lifecycle):

* ``PreToolUse`` — fires before a tool call executes
* ``PostToolUse`` — fires after a tool call returns
* ``UserPromptSubmit`` — fires when the user submits a turn
* ``Stop`` — fires when the turn is about to end
* ``PostLLMCall`` — fires after the LLM produces a response
* ``SessionStart`` — fires when a session begins
* ``SessionEnd`` — fires when a session ends
* ``SubagentStop`` — fires when a subagent finishes
* ``Notification`` — fires for any non-tool notice
* ``PreCompact`` — fires before context compaction
* ``PostCompact`` — fires after context compaction
"""

from __future__ import annotations
