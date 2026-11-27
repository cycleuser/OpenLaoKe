"""Tests for ListDirectory, InvokeSkill and the file-writing tools.

These are the tools a model reaches for on almost every task, so the checks are
about the messages a small model actually reads: does a bad path explain itself,
does a missing skill list the alternatives, does a write report what changed.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import ToolContext
from openlaoke.tools.invoke_skill_tool import InvokeSkillTool
from openlaoke.tools.ls_tool import ListDirectoryTool


def make_ctx(tmp_path, tool_use_id: str = "call_1") -> ToolContext:
    return ToolContext(app_state=create_app_state(cwd=str(tmp_path)), tool_use_id=tool_use_id)


# --------------------------------------------------------------------------- #
# ListDirectory
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_defaults_to_the_working_directory(tmp_path) -> None:
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.txt").write_text("x", encoding="utf-8")

    result = await ListDirectoryTool().call(make_ctx(tmp_path))

    assert result.is_error is False
    assert f"Contents of {tmp_path}:" in result.content
    assert "a.py" in result.content
    assert "sub/" in result.content
    assert "2 items total" in result.content


@pytest.mark.asyncio
async def test_list_shows_directories_before_files(tmp_path) -> None:
    (tmp_path / "zzz.txt").write_text("x", encoding="utf-8")
    (tmp_path / "aaa_dir").mkdir()

    content = (await ListDirectoryTool().call(make_ctx(tmp_path))).content
    body = [line for line in content.splitlines() if line.startswith(("DIR", "FILE"))]

    assert body[0].startswith("DIR")
    assert body[1].startswith("FILE")
    assert "aaa_dir/" in body[0]


@pytest.mark.asyncio
async def test_list_reports_a_missing_path(tmp_path) -> None:
    missing = tmp_path / "nope"
    result = await ListDirectoryTool().call(make_ctx(tmp_path), path=str(missing))

    assert result.is_error is True
    assert result.content == f"Error: Path does not exist: {missing}"


@pytest.mark.asyncio
async def test_list_rejects_a_file_path(tmp_path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")

    result = await ListDirectoryTool().call(make_ctx(tmp_path), path=str(target))

    assert result.is_error is True
    assert result.content == f"Error: Not a directory: {target}"


@pytest.mark.asyncio
async def test_list_expands_a_home_relative_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    result = await ListDirectoryTool().call(make_ctx(tmp_path), path="~")

    assert result.is_error is False
    assert f"Contents of {tmp_path}:" in result.content


@pytest.mark.asyncio
async def test_list_of_an_empty_directory_says_zero_items(tmp_path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()

    content = (await ListDirectoryTool().call(make_ctx(tmp_path), path=str(empty))).content

    assert "0 items total" in content


@pytest.mark.asyncio
async def test_list_reports_a_permission_error(tmp_path, monkeypatch) -> None:
    def boom(_path):
        raise PermissionError("denied")

    monkeypatch.setattr(ListDirectoryTool, "_list_directory", staticmethod(boom))
    result = await ListDirectoryTool().call(make_ctx(tmp_path))

    assert result.is_error is True
    assert result.content.startswith("Error: Permission denied:")


@pytest.mark.asyncio
async def test_list_wraps_any_other_listing_failure(tmp_path, monkeypatch) -> None:
    def boom(_path):
        raise RuntimeError("scandir exploded")

    monkeypatch.setattr(ListDirectoryTool, "_list_directory", staticmethod(boom))
    result = await ListDirectoryTool().call(make_ctx(tmp_path))

    assert result.is_error is True
    assert result.content == "Error listing directory: scandir exploded"


@pytest.mark.asyncio
async def test_an_entry_that_cannot_be_stat_ed_still_appears(tmp_path) -> None:
    (tmp_path / "ghost.txt").write_text("x", encoding="utf-8")

    class FakeEntry:
        name = "ghost.txt"

        def is_dir(self) -> bool:
            return False

        def stat(self):
            raise OSError("vanished")

    class FakeScanner:
        def __enter__(self):
            return iter([FakeEntry()])

        def __exit__(self, *exc):
            return False

    import openlaoke.tools.ls_tool as ls_module

    original = ls_module.os.scandir
    ls_module.os.scandir = lambda _p: FakeScanner()
    try:
        entries = ListDirectoryTool()._list_directory(str(tmp_path))
    finally:
        ls_module.os.scandir = original

    assert entries == [{"name": "ghost.txt", "is_dir": False, "size": 0, "modified": ""}]


@pytest.mark.parametrize(
    "size,expected",
    [
        (0, "0.0B"),
        (1023, "1023.0B"),
        (1024, "1.0KB"),
        (1536, "1.5KB"),
        (1024**2, "1.0MB"),
        (1024**3, "1.0GB"),
        (1024**4, "1.0TB"),
        (1024**5, "1.0PB"),
    ],
)
def test_size_formatting(size: int, expected: str) -> None:
    assert ListDirectoryTool()._format_size(size) == expected


# --------------------------------------------------------------------------- #
# InvokeSkill
# --------------------------------------------------------------------------- #


@pytest.fixture()
def skill_home(tmp_path, monkeypatch):
    """An isolated ~/.openlaoke/skills plus a cleared registry."""
    import openlaoke.core.skill_system as skill_system

    home = tmp_path / "home"
    (home / ".openlaoke" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(skill_system, "_global_registry", None)
    yield home
    skill_system._global_registry = None


def install_skill(home: Path, name: str, body: str = "Do the thing.") -> Path:
    folder = home / ".openlaoke" / "skills" / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(
        f"---\nname: {name}\ndescription: test skill {name}\n---\n\n{body}\n", encoding="utf-8"
    )
    return path


@pytest.mark.asyncio
async def test_invoke_skill_requires_a_name_and_lists_what_exists(tmp_path, skill_home) -> None:
    install_skill(skill_home, "reviewer")

    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="  ")

    assert result.is_error is True
    assert "skill_name is required" in result.content
    assert "reviewer" in result.content


@pytest.mark.asyncio
async def test_invoke_skill_without_any_installed_skill_says_where_to_put_one(
    tmp_path, skill_home
) -> None:
    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="")

    assert result.is_error is True
    assert "~/.openlaoke/skills/<name>/SKILL.md" in result.content


@pytest.mark.asyncio
async def test_invoke_skill_reports_an_unknown_name_with_alternatives(tmp_path, skill_home) -> None:
    install_skill(skill_home, "reviewer")

    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="ghost-skill")

    assert result.is_error is True
    assert "Skill 'ghost-skill' not found" in result.content
    assert "reviewer" in result.content


@pytest.mark.asyncio
async def test_invoke_skill_runs_the_skill_through_the_task_manager(
    tmp_path, skill_home, monkeypatch
) -> None:
    skill_path = install_skill(skill_home, "writer", body="Write a haiku.")
    seen: dict[str, str] = {}

    async def fake_run_agent(self, *, prompt, description, tool_use_id, subagent_type):
        seen["prompt"] = prompt
        seen["description"] = description
        seen["subagent_type"] = subagent_type
        return "a haiku"

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)

    result = await InvokeSkillTool().call(
        make_ctx(tmp_path),
        skill_name=" writer ",
        arguments="about rain",
        description="haiku",
    )

    assert result.is_error is False
    assert result.content == "Skill 'writer' result:\n\na haiku"
    assert "[Skill: writer]" in seen["prompt"]
    assert "Write a haiku." in seen["prompt"]
    assert "[Task]\nabout rain" in seen["prompt"]
    assert seen["subagent_type"] == "skill:writer"
    assert seen["description"] == "haiku"
    assert skill_path.exists()


@pytest.mark.asyncio
async def test_invoke_skill_falls_back_to_the_description_as_the_task(
    tmp_path, skill_home, monkeypatch
) -> None:
    install_skill(skill_home, "writer")
    seen: dict[str, str] = {}

    async def fake_run_agent(self, *, prompt, description, tool_use_id, subagent_type):
        seen["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)
    await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="writer", description="polish text")

    assert "[Task]\npolish text" in seen["prompt"]


@pytest.mark.asyncio
async def test_invoke_skill_defaults_the_task_when_nothing_is_given(
    tmp_path, skill_home, monkeypatch
) -> None:
    install_skill(skill_home, "writer")
    seen: dict[str, str] = {}

    async def fake_run_agent(self, *, prompt, description, tool_use_id, subagent_type):
        seen["prompt"] = prompt
        return "ok"

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)
    await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="writer")

    assert "Execute the skill as instructed." in seen["prompt"]


@pytest.mark.asyncio
async def test_invoke_skill_truncates_a_huge_result(tmp_path, skill_home, monkeypatch) -> None:
    install_skill(skill_home, "verbose")

    async def fake_run_agent(self, *, prompt, description, tool_use_id, subagent_type):
        return "x" * 25_000

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)
    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="verbose")

    assert result.is_error is False
    assert "output truncated, 5000 chars omitted" in result.content
    assert len(result.content) < 25_000


@pytest.mark.asyncio
async def test_invoke_skill_reports_an_execution_failure(tmp_path, skill_home, monkeypatch) -> None:
    install_skill(skill_home, "broken")

    async def fake_run_agent(self, **kwargs):
        raise RuntimeError("subagent died")

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)
    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="broken")

    assert result.is_error is True
    assert "Skill 'broken' execution failed: subagent died" in result.content


@pytest.mark.asyncio
async def test_invoke_skill_reports_an_unreadable_skill_file(tmp_path, skill_home) -> None:
    path = install_skill(skill_home, "locked")
    path.write_text("x", encoding="utf-8")

    def boom(*args, **kwargs):
        raise OSError("permission denied")

    original = Path.read_text
    Path.read_text = boom
    try:
        result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="locked")
    finally:
        Path.read_text = original

    assert result.is_error is True
    assert "Failed to read skill 'locked'" in result.content


def test_skill_search_falls_back_to_the_known_directories(tmp_path, monkeypatch) -> None:
    # With no registry hit, a flat <name>.md file is still found.
    skills = tmp_path / ".openlaoke" / "skills"
    skills.mkdir(parents=True)
    (skills / "flat.md").write_text("# flat", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    # Project-local skills only load in a trusted project (core/trust.py).
    from openlaoke.core import trust

    trust.set_trusted(tmp_path, True)
    monkeypatch.setattr(InvokeSkillTool, "_registry_skill", staticmethod(lambda _n: None))

    assert InvokeSkillTool._find_skill_file("flat") == skills / "flat.md"
    assert InvokeSkillTool._find_skill_file("absent") is None


def test_list_available_skills_merges_registry_and_disk(tmp_path, monkeypatch) -> None:
    import openlaoke.core.skill_system as skill_system

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    skills = tmp_path / ".openlaoke" / "skills"
    (skills / "from-disk").mkdir(parents=True)
    (skills / "from-disk" / "SKILL.md").write_text("# x", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    from openlaoke.core import trust

    trust.set_trusted(tmp_path, True)
    monkeypatch.setattr(skill_system, "list_available_skills", lambda: ["from-registry"])

    assert InvokeSkillTool._list_available_skills() == ["from-disk", "from-registry"]


def test_list_available_skills_survives_a_broken_registry(tmp_path, monkeypatch) -> None:
    import openlaoke.core.skill_system as skill_system

    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)

    def boom():
        raise RuntimeError("registry unavailable")

    monkeypatch.setattr(skill_system, "list_available_skills", boom)
    assert InvokeSkillTool._list_available_skills() == []


@pytest.mark.asyncio
async def test_invoke_skill_finds_a_skill_the_registry_knows_from_another_directory(
    tmp_path, monkeypatch
) -> None:
    """A skill in ~/.claude/skills is listed by /skill and must be invocable.

    Regression: the tool searched a private list of three directories that did
    not include ~/.claude/skills or ~/.opencode/skills, so a skill the session
    context advertised came back as "not found".
    """
    import openlaoke.core.skill_system as skill_system

    home = tmp_path / "home"
    claude_skill = home / ".claude" / "skills" / "claude-style"
    claude_skill.mkdir(parents=True)
    (claude_skill / "SKILL.md").write_text(
        "---\nname: claude-style\ndescription: lives elsewhere\n---\n\nBody.\n", encoding="utf-8"
    )
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(skill_system, "_global_registry", None)

    seen: dict[str, str] = {}

    async def fake_run_agent(self, *, prompt, description, tool_use_id, subagent_type):
        seen["prompt"] = prompt
        return "done"

    monkeypatch.setattr("openlaoke.core.task.TaskManager.run_agent", fake_run_agent)

    result = await InvokeSkillTool().call(make_ctx(tmp_path), skill_name="claude-style")

    assert result.is_error is False, result.content
    assert "Body." in seen["prompt"]
    skill_system._global_registry = None
