"""Tests for defects fixed in the jcode-alignment refactor (phase P0)."""

from __future__ import annotations

from types import SimpleNamespace

from openlaoke.core.cache_guard import CacheGuard
from openlaoke.core.hook_system import HookSystem
from openlaoke.core.repl import REPL


def test_build_compact_prompt_accepts_user_input() -> None:
    state = SimpleNamespace(cwd="/tmp")
    prompt = CacheGuard.build_compact_prompt(state, "fix the parser")
    assert isinstance(prompt, str)
    assert "OpenLaoKe" in prompt


def test_build_compact_prompt_without_user_input() -> None:
    prompt = CacheGuard.build_compact_prompt(SimpleNamespace(cwd=""))
    assert "DONE" in prompt


def test_hook_system_has_no_missing_module_property() -> None:
    assert not hasattr(HookSystem(), "v2")


def test_resolve_max_iterations_reads_app_state() -> None:
    # An explicit max_steps always wins.
    fake = SimpleNamespace(app_state=SimpleNamespace(max_steps=7))
    assert REPL._resolve_max_iterations(fake) == 7

    # With no explicit override the harness mode decides the step budget,
    # so interactive behaviour stays consistent with --mode instead of a
    # fixed guess. pi is lean, opencode is generous.
    pi = SimpleNamespace(app_state=SimpleNamespace(max_steps=0, harness_mode="pi"))
    assert REPL._resolve_max_iterations(pi) == 25
    oc = SimpleNamespace(app_state=SimpleNamespace(max_steps=0, harness_mode="opencode"))
    assert REPL._resolve_max_iterations(oc) == 60

    # Unknown/missing mode falls back to the default (balanced) budget.
    fake_missing = SimpleNamespace(app_state=SimpleNamespace())
    assert REPL._resolve_max_iterations(fake_missing) == 50


def test_no_package_module_is_hidden_by_gitignore():
    """A source file that git ignores never reaches a clone.

    `.gitignore` once had a bare `session*`, which swallowed
    openlaoke/core/session_index.py and openlaoke/tools/session_search_tool.py:
    both were imported, neither was in the repository, and the failure only
    showed up on a fresh clone.
    """
    import subprocess
    from pathlib import Path

    root = Path(__file__).resolve().parent.parent
    if not (root / ".git").exists():
        import pytest

        pytest.skip("not a git checkout")

    files = sorted(str(path.relative_to(root)) for path in (root / "openlaoke").rglob("*.py"))
    result = subprocess.run(
        # --no-index so the check looks at the patterns, not at which
        # files happen to be tracked already.
        ["git", "check-ignore", "--no-index", "--stdin"],
        cwd=root,
        input="\n".join(files),
        capture_output=True,
        text=True,
        check=False,
    )
    ignored = [line for line in result.stdout.splitlines() if line.strip()]

    assert ignored == [], f"source files hidden by .gitignore: {ignored}"


def test_every_package_module_imports():
    """Catches a module that is committed but cannot be imported at all."""
    import importlib
    import pkgutil

    import openlaoke

    failures = []
    for info in pkgutil.walk_packages(openlaoke.__path__, "openlaoke."):
        try:
            importlib.import_module(info.name)
        except Exception as exc:  # noqa: BLE001 - the point is to report all of them
            failures.append(f"{info.name}: {type(exc).__name__}: {exc}")

    assert failures == []
