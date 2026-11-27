"""Tests for project trust: decisions are recorded and actually enforced."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from openlaoke.core import trust
from openlaoke.core.state import AppState


class _FakeTheme:
    """REPL colours come from the theme; these tests only need a name."""

    def color(self, _name: str) -> str:
        return "white"


@pytest.fixture(autouse=True)
def _isolated_trust_file(tmp_path, monkeypatch):
    """Never touch the developer's real trust.json."""
    monkeypatch.setenv("HOME", str(tmp_path / "home"))


def test_an_absent_record_is_undecided_not_permission(tmp_path):
    assert trust.trust_state(tmp_path) == trust.UNDECIDED
    assert trust.is_trusted(tmp_path) is False


def test_a_decision_is_recorded_and_read_back(tmp_path):
    assert trust.set_trusted(tmp_path, True) == trust.TRUSTED
    assert trust.is_trusted(tmp_path) is True
    assert trust.set_trusted(tmp_path, False) == trust.UNTRUSTED
    assert trust.is_trusted(tmp_path) is False
    assert trust.set_trusted(tmp_path, None) == trust.UNDECIDED


def test_the_decision_is_keyed_by_resolved_path(tmp_path):
    trust.set_trusted(tmp_path / ".", True)

    assert trust.trust_state(str(tmp_path)) == trust.TRUSTED
    assert trust.trust_state(tmp_path / "sub") == trust.UNDECIDED


def test_a_corrupt_trust_file_reads_as_undecided(tmp_path):
    trust.trust_path().parent.mkdir(parents=True, exist_ok=True)
    trust.trust_path().write_text("{ not json")

    assert trust.trust_state(tmp_path) == trust.UNDECIDED


def test_a_non_object_trust_file_reads_as_undecided(tmp_path):
    trust.trust_path().parent.mkdir(parents=True, exist_ok=True)
    trust.trust_path().write_text("[1, 2]")

    assert trust.trust_state(tmp_path) == trust.UNDECIDED


def test_the_trust_file_is_written_atomically(tmp_path):
    trust.set_trusted(tmp_path, True)

    payload = json.loads(trust.trust_path().read_text())
    assert payload[str(tmp_path.resolve())] is True
    assert [
        item.name for item in trust.trust_path().parent.iterdir() if item.name.endswith(".tmp")
    ] == []


def test_project_skill_dirs_are_empty_until_trusted(tmp_path, monkeypatch):
    (tmp_path / ".openlaoke" / "skills" / "mine").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)

    assert trust.project_skill_dirs() == []

    trust.set_trusted(tmp_path, True)
    assert trust.project_skill_dirs() == [tmp_path / ".openlaoke" / "skills"]


def test_project_prompt_dirs_follow_the_same_rule(tmp_path, monkeypatch):
    (tmp_path / ".openlaoke" / "prompts").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert trust.project_prompt_dirs() == []

    trust.set_trusted(tmp_path, True)
    assert trust.project_prompt_dirs() == [tmp_path / ".openlaoke" / "prompts"]


def test_skipped_project_dirs_names_only_what_exists(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert trust.skipped_project_dirs() == []

    (tmp_path / ".openlaoke" / "skills").mkdir(parents=True)
    assert trust.skipped_project_dirs() == [".openlaoke/skills"]

    trust.set_trusted(tmp_path, True)
    assert trust.skipped_project_dirs() == []


def test_the_skill_tool_cannot_see_project_skills_until_trusted(tmp_path, monkeypatch):
    from openlaoke.tools.invoke_skill_tool import InvokeSkillTool

    skill = tmp_path / ".openlaoke" / "skills" / "deploy" / "SKILL.md"
    skill.parent.mkdir(parents=True)
    skill.write_text("# deploy\n\nRun the release script.")
    monkeypatch.chdir(tmp_path)

    assert InvokeSkillTool._find_skill_file("deploy") is None
    assert "deploy" not in InvokeSkillTool._list_available_skills()

    trust.set_trusted(tmp_path, True)
    assert InvokeSkillTool._find_skill_file("deploy") == skill
    assert "deploy" in InvokeSkillTool._list_available_skills()


def test_project_prompt_templates_are_not_loaded_until_trusted(tmp_path, monkeypatch):
    from openlaoke.core.prompt_templates import get_default_prompt_dirs

    (tmp_path / ".openlaoke" / "prompts").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    assert tmp_path / ".openlaoke" / "prompts" not in get_default_prompt_dirs()

    trust.set_trusted(tmp_path, True)
    assert tmp_path / ".openlaoke" / "prompts" in get_default_prompt_dirs()


def test_the_skill_registry_includes_project_skills_only_when_trusted(tmp_path, monkeypatch):
    import openlaoke.core.skill_system as skill_system

    (tmp_path / ".openlaoke" / "skills" / "local").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(skill_system, "_global_registry", None)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "home"))

    assert tmp_path / ".openlaoke" / "skills" not in skill_system.get_default_skill_dirs()

    trust.set_trusted(tmp_path, True)
    assert tmp_path / ".openlaoke" / "skills" in skill_system.get_default_skill_dirs()


def test_the_trust_command_reports_all_three_states(tmp_path):
    from openlaoke.commands.pi_commands import TrustCommand

    class Ctx:
        app_state = AppState(session_id="s", cwd=str(tmp_path))
        args = ""

    assert "undecided" in asyncio.run(TrustCommand().execute(Ctx())).message

    Ctx.args = "on"
    assert "trusted" in asyncio.run(TrustCommand().execute(Ctx())).message
    assert trust.trust_state(tmp_path) == trust.TRUSTED

    Ctx.args = "off"
    assert "untrusted" in asyncio.run(TrustCommand().execute(Ctx())).message
    assert trust.trust_state(tmp_path) == trust.UNTRUSTED

    Ctx.args = "reset"
    assert "undecided" in asyncio.run(TrustCommand().execute(Ctx())).message

    Ctx.args = "sideways"
    rejected = asyncio.run(TrustCommand().execute(Ctx()))
    assert rejected.success is False
    assert "Usage" in rejected.message


def test_the_trust_command_explains_why_nothing_loaded(tmp_path):
    from openlaoke.commands.pi_commands import TrustCommand

    (tmp_path / ".openlaoke" / "skills").mkdir(parents=True)

    class Ctx:
        app_state = AppState(session_id="s", cwd=str(tmp_path))
        args = "status"

    message = asyncio.run(TrustCommand().execute(Ctx())).message

    assert "not loaded until it is trusted" in message


def test_the_repl_mentions_the_skipped_directory(tmp_path, monkeypatch):
    from io import StringIO

    from rich.console import Console

    from openlaoke.core.repl import REPL

    (tmp_path / ".openlaoke" / "skills").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    repl = REPL.__new__(REPL)
    repl.app_state = AppState(session_id="s", cwd=str(tmp_path))
    repl.console = Console(file=StringIO(), force_terminal=False, width=120, color_system=None)
    repl._theme = _FakeTheme()

    REPL._warn_untrusted_project_local(repl)

    out = repl.console.file.getvalue()
    assert ".openlaoke/skills" in out
    assert "/trust on" in out


def test_the_repl_says_nothing_in_a_trusted_project(tmp_path, monkeypatch):
    from io import StringIO

    from rich.console import Console

    from openlaoke.core.repl import REPL

    (tmp_path / ".openlaoke" / "skills").mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    trust.set_trusted(tmp_path, True)
    repl = REPL.__new__(REPL)
    repl.app_state = AppState(session_id="s", cwd=str(tmp_path))
    repl.console = Console(file=StringIO(), force_terminal=False, width=120, color_system=None)
    repl._theme = _FakeTheme()

    REPL._warn_untrusted_project_local(repl)

    assert repl.console.file.getvalue().strip() == ""
