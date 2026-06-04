"""Enhanced skill metadata and progressive loading helpers.

This module extends the core :class:`Skill` system with:

* **Run mode** — ``inline`` (default) or ``subagent``. Inline skills are
  injected as a pinned tool result; subagent skills spawn an isolated
  child loop.

* **Requirements check** — ``requires.bins`` and ``requires.env`` are
  resolved at load time. A skill that requires a missing binary is
  not pinned in the index.

* **Pinned index** — names + descriptions + a ``[subagent]`` tag for
  subagent skills. Capped at ``INDEX_MAX_CHARS`` (default 4000) so
  the system prompt prefix stays compact.
"""

from __future__ import annotations

import os
import shutil

from openlaoke.core.skill_system import Skill

INDEX_MAX_CHARS = 4000


def parse_run_mode(skill: Skill) -> str:
    """Return ``"inline"`` (default) or ``"subagent"``.

    Subagent skills are advertised in the pinned index with a tag so
    the model can decide whether to invoke a dedicated top-level
    wrapper (``explore``, ``research``, ``review``,
    ``security_review``).
    """
    mode = (skill.metadata or {}).get("runAs") or (skill.metadata or {}).get("run_as")
    if isinstance(mode, str) and mode.strip().lower() in ("subagent", "agent", "child"):
        return "subagent"
    return "inline"


def parse_requires(skill: Skill) -> dict[str, list[str]]:
    """Extract ``requires.bins`` and ``requires.env`` from frontmatter."""
    metadata = skill.metadata or {}
    raw = metadata.get("requires", {}) or {}
    if not isinstance(raw, dict):
        return {"bins": [], "env": []}
    bins = raw.get("bins") or []
    env = raw.get("env") or []
    if isinstance(bins, str):
        bins = [b.strip() for b in bins.split(",") if b.strip()]
    if isinstance(env, str):
        env = [e.strip() for e in env.split(",") if e.strip()]
    return {"bins": list(bins), "env": list(env)}


def meets_requirements(skill: Skill) -> tuple[bool, list[str]]:
    """Return ``(ok, missing)`` for a skill's required binaries and env vars."""
    missing: list[str] = []
    for binary in parse_requires(skill)["bins"]:
        if shutil.which(binary) is None:
            missing.append(f"bin:{binary}")
    for env_name in parse_requires(skill)["env"]:
        if not os.environ.get(env_name):
            missing.append(f"env:{env_name}")
    return (not missing, missing)


def load_skill_references(skill: Skill) -> str:
    """Concatenate sibling ``references/*.md`` files (Anthropic layout)."""
    if not skill.path:
        return ""
    references = skill.path.parent / "references"
    if not references.is_dir():
        return ""
    chunks: list[str] = []
    for ref in sorted(references.glob("*.md")):
        try:
            chunks.append(f"\n### {ref.stem}\n\n" + ref.read_text(encoding="utf-8"))
        except OSError:
            continue
    return "".join(chunks)


def skill_full_body(skill: Skill) -> str:
    """Skill body with ``references/*.md`` siblings appended."""
    body = skill.content or ""
    refs = load_skill_references(skill)
    if refs:
        return body + refs
    return body


def pinned_index(skills: list[Skill]) -> str:
    """Compact, length-bounded index of skills for the system prompt.

    Each entry is one line::

        - name: description [subagent]

    Truncated to ``INDEX_MAX_CHARS`` with a marker.
    """
    lines: list[str] = []
    for skill in skills:
        ok, missing = meets_requirements(skill)
        if not ok:
            continue
        desc = (skill.description or "").strip().replace("\n", " ")
        if len(desc) > 120:
            desc = desc[:117] + "..."
        tag = " [subagent]" if parse_run_mode(skill) == "subagent" else ""
        lines.append(f"- {skill.name}: {desc}{tag}")
    text = "\n".join(lines)
    if len(text) > INDEX_MAX_CHARS:
        text = text[: INDEX_MAX_CHARS - 20] + "\n... (more skills)"
    return text


def pin_inline(skill: Skill, body: str | None = None) -> str:
    """Wrap a skill body in a sentinel that survives context compaction.

    The summarizer treats the inner content as opaque and will not
    summarize it away.
    """
    payload = body if body is not None else skill_full_body(skill)
    return f'<skill-pin name="{skill.name}">\n{payload}\n</skill-pin>'
