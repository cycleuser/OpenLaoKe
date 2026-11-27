"""Project trust: whether code and text from this directory may take effect.

The repository you open is attacker-controlled in the general case: a clone can
ship `.openlaoke/skills/*/SKILL.md` (text that goes straight into the system
prompt) and `.openlaoke/prompts/*.md` (same). Anything that runs or is injected
because a directory exists should therefore depend on a decision the user made
about that directory, not on the directory existing.

The decision lives in ``~/.openlaoke/trust.json`` keyed by the resolved project
path. Three states, and the third one matters:

* ``trusted``    - load project-local skills and prompt templates;
* ``untrusted``  - never load them, and do not ask again;
* ``undecided``  - no record yet. Treated exactly like ``untrusted`` (fail
  closed) but the caller may mention it once so the user knows why a skill they
  wrote is not appearing.

Until this module existed, ``/trust`` wrote that file and nothing read it.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

TRUSTED = "trusted"
UNTRUSTED = "untrusted"
UNDECIDED = "undecided"


def trust_path() -> Path:
    """Resolved per call: ``HOME`` can change (tests, and ``su``-style resets)."""
    return Path(os.path.expanduser("~")) / ".openlaoke" / "trust.json"


def project_key(cwd: str | Path | None = None) -> str:
    return str(Path(cwd or os.getcwd()).resolve())


def _load() -> dict[str, Any]:
    try:
        with open(trust_path(), encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}
    return payload


def trust_state(cwd: str | Path | None = None) -> str:
    """``trusted``, ``untrusted`` or ``undecided`` for this directory."""
    record = _load().get(project_key(cwd))
    if record is True:
        return TRUSTED
    if record is False:
        return UNTRUSTED
    return UNDECIDED


def is_trusted(cwd: str | Path | None = None) -> bool:
    """Only an explicit yes counts; an absent record is not permission."""
    return trust_state(cwd) == TRUSTED


def set_trusted(cwd: str | Path | None = None, trusted: bool | None = None) -> str:
    """Record a decision (``None`` clears it) and return the new state."""
    key = project_key(cwd)
    payload = _load()
    if trusted is None:
        payload.pop(key, None)
    else:
        payload[key] = bool(trusted)
    path = trust_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with open(temporary, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=1, sort_keys=True)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)
    return trust_state(cwd)


def project_skill_dirs(cwd: str | Path | None = None) -> list[Path]:
    """Project-local skill directories, only when this project is trusted."""
    if not is_trusted(cwd):
        return []
    base = Path(cwd or os.getcwd()) / ".openlaoke" / "skills"
    return [base] if base.exists() else []


def project_prompt_dirs(cwd: str | Path | None = None) -> list[Path]:
    """Project-local prompt template directories, only when trusted."""
    if not is_trusted(cwd):
        return []
    base = Path(cwd or os.getcwd()) / ".openlaoke" / "prompts"
    return [base] if base.exists() else []


def skipped_project_dirs(cwd: str | Path | None = None) -> list[str]:
    """Project-local directories that exist but are not being loaded.

    Used for the one-line hint: a skill the user wrote not appearing is
    otherwise indistinguishable from a bug.
    """
    base = Path(cwd or os.getcwd())
    skipped = []
    for name in ("skills", "prompts"):
        directory = base / ".openlaoke" / name
        if directory.exists() and trust_state(cwd) != TRUSTED:
            skipped.append(f".openlaoke/{name}")
    return skipped
