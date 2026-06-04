"""Enhanced skill system.

Three levels of progressive loading:

* **Level 1 (always in context):** skill name + description from
  frontmatter. Injected into the system prompt as a pinned index.
* **Level 2 (on trigger):** full ``SKILL.md`` body. Loaded when the
  user message matches a trigger keyword.
* **Level 3 (lazy):** bundled resources (``scripts/``, ``references/``,
  ``assets/``) loaded only when a sub-agent specifically asks for them.

Skills can be:

* ``inline`` (default): loaded as a tool result wrapped in
  ``<skill-pin name="...">`` so it survives context compaction.
* ``subagent``: spawns an isolated child agent whose system prompt is
  the skill body.

Auto-discovery scans ``.openlaoke/skills/``, ``.agents/skills/``,
``.agent/skills/``, ``.claude/skills/`` under both project and home.
"""

from __future__ import annotations
