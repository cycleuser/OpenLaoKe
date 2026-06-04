"""Memory system: hierarchical doc-based memory with Dream consolidation.

Two layers:

* **Doc memory** — ``REASONIX.md`` / ``REASONIX.local.md`` /
  ``AGENTS.md`` / ``CLAUDE.md`` bootstrap files loaded at boot and
  cached into the system-prompt prefix.

* **Auto-memory** — per-project one-fact-per-file Markdown with
  frontmatter. ``MEMORY.md`` is the index that loads into the prefix.

Cache-stable: in-session changes write to disk and queue a turn-tail
note (``pending_memory``) that rides the next outgoing turn without
mutating the cache-stable prefix.
"""

from __future__ import annotations
