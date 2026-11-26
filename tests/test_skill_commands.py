"""Tests for /skill: listing, activating, deactivating and inspecting skills.

The command reads the shared skill registry, so the tests install real SKILL.md
files in an isolated home directory and let the registry load them.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openlaoke.commands.base import CommandContext
from openlaoke.commands.skill_commands import SkillCommand, UseSkillCommand
from openlaoke.core.state import create_app_state


@pytest.fixture(autouse=True)
def skill_home(tmp_path, monkeypatch):
    import openlaoke.core.skill_system as skill_system

    home = tmp_path / "home"
    (home / ".openlaoke" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(skill_system, "_global_registry", None)
    yield home
    skill_system._global_registry = None


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path))


def ctx(state, args: str = "") -> CommandContext:
    return CommandContext(app_state=state, args=args)


def install(home: Path, name: str, description: str = "helper skill", body: str = "Do it.") -> Path:
    folder = home / ".openlaoke" / "skills" / name
    folder.mkdir(parents=True)
    path = folder / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n{body}\n", encoding="utf-8"
    )
    return path


def rescan() -> None:
    from openlaoke.core.skill_system import rescan_skills

    rescan_skills()


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_listing_without_any_skill_says_where_to_add_one(state) -> None:
    result = await SkillCommand().execute(ctx(state))

    assert result.success is True
    assert "No skills installed" in result.message
    assert "~/.openlaoke/skills/<name>/SKILL.md" in result.message


@pytest.mark.asyncio
async def test_listing_shows_names_and_descriptions(state, skill_home) -> None:
    install(skill_home, "reviewer", "review a diff")
    install(skill_home, "writer", "polish prose")

    message = (await SkillCommand().execute(ctx(state))).message

    assert "Available skills:" in message
    assert "reviewer" in message
    assert "review a diff" in message
    assert "Use /skill <name> to activate." in message


@pytest.mark.asyncio
async def test_listing_marks_the_active_skills(state, skill_home) -> None:
    install(skill_home, "reviewer")
    install(skill_home, "writer")
    state.active_skills = ["writer"]

    message = (await SkillCommand().execute(ctx(state))).message
    writer_line = next(line for line in message.splitlines() if "writer" in line)
    reviewer_line = next(line for line in message.splitlines() if "reviewer" in line)

    assert writer_line.strip().startswith("*")
    assert not reviewer_line.strip().startswith("*")


@pytest.mark.asyncio
async def test_listing_truncates_a_long_description(state, skill_home) -> None:
    install(skill_home, "verbose", "x" * 200)

    message = (await SkillCommand().execute(ctx(state))).message

    assert "x" * 60 + "..." in message


# --------------------------------------------------------------------------- #
# Activation
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_activating_a_skill_adds_it_to_the_session(state, skill_home) -> None:
    install(skill_home, "reviewer", "review a diff")

    result = await SkillCommand().execute(ctx(state, "reviewer"))

    assert result.success is True
    assert state.active_skills == ["reviewer"]
    assert "Activated skill: reviewer" in result.message
    assert "review a diff" in result.message


@pytest.mark.asyncio
async def test_activating_twice_keeps_one_entry(state, skill_home) -> None:
    install(skill_home, "reviewer")
    command = SkillCommand()

    await command.execute(ctx(state, "reviewer"))
    await command.execute(ctx(state, "reviewer"))

    assert state.active_skills == ["reviewer"]


@pytest.mark.asyncio
async def test_activating_an_unknown_skill_fails(state, skill_home) -> None:
    install(skill_home, "reviewer")
    result = await SkillCommand().execute(ctx(state, "ghost"))

    assert result.success is False
    assert result.message == "Unknown skill: ghost"
    assert state.active_skills == []


# --------------------------------------------------------------------------- #
# Deactivation
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_off_and_clear_deactivate(state, skill_home) -> None:
    install(skill_home, "reviewer")
    install(skill_home, "writer")
    state.active_skills = ["reviewer", "writer"]
    command = SkillCommand()

    off = await command.execute(ctx(state, "off reviewer"))
    assert off.message == "Deactivated skill: reviewer"
    assert state.active_skills == ["writer"]

    cleared = await command.execute(ctx(state, "clear"))
    assert cleared.message == "All skills deactivated."
    assert state.active_skills == []


@pytest.mark.asyncio
async def test_off_without_a_name_clears_everything(state, skill_home) -> None:
    install(skill_home, "reviewer")
    state.active_skills = ["reviewer"]

    result = await SkillCommand().execute(ctx(state, "off "))

    assert result.message == "All skills deactivated."
    assert state.active_skills == []


@pytest.mark.asyncio
async def test_off_for_a_skill_that_is_not_active(state, skill_home) -> None:
    install(skill_home, "reviewer")
    result = await SkillCommand().execute(ctx(state, "off reviewer"))

    assert result.success is True
    assert result.message == "Skill not active: reviewer"


@pytest.mark.asyncio
async def test_reload_reports_the_count(state, skill_home) -> None:
    install(skill_home, "reviewer")

    result = await SkillCommand().execute(ctx(state, "reload"))

    assert result.success is True
    assert result.message == "Reloaded 1 skill(s)."


# --------------------------------------------------------------------------- #
# Inspection
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_info_requires_a_name(state, skill_home) -> None:
    result = await SkillCommand().execute(ctx(state, "info"))
    assert result.success is False
    assert result.message == "Use '/skill info <name>'."


@pytest.mark.asyncio
async def test_info_shows_the_skill_body(state, skill_home) -> None:
    install(skill_home, "writer", "polish prose", body="Rewrite it clearly.")

    result = await SkillCommand().execute(ctx(state, "info writer"))

    assert result.success is True
    assert result.message.startswith("writer: polish prose")
    assert "Rewrite it clearly." in result.message


@pytest.mark.asyncio
async def test_info_of_an_unknown_skill(state, skill_home) -> None:
    install(skill_home, "writer")
    result = await SkillCommand().execute(ctx(state, "show ghost"))

    assert result.success is False
    assert result.message == "Unknown skill: ghost"


@pytest.mark.asyncio
async def test_info_is_capped_at_four_thousand_characters(state, skill_home) -> None:
    install(skill_home, "huge", body="y" * 10_000)

    result = await SkillCommand().execute(ctx(state, "info huge"))

    assert len(result.message) == 4000


@pytest.mark.asyncio
async def test_use_skill_delegates_to_skill(state, skill_home) -> None:
    install(skill_home, "reviewer", "review a diff")

    result = await UseSkillCommand().execute(ctx(state, "reviewer"))

    assert result.success is True
    assert state.active_skills == ["reviewer"]
    assert UseSkillCommand().hidden is True
