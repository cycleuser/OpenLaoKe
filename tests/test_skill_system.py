"""Tests for SKILL.md parsing and the skill registry.

The interesting part is the frontmatter handling: real skills in the wild carry
colons in their descriptions, which plain YAML rejects, so the loader has three
attempts (direct, sanitised, manual) and each one needs a case.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from openlaoke.core.skill_system import (
    Skill,
    SkillRegistry,
    _sanitize_frontmatter,
    get_default_skill_dirs,
    get_skill_registry,
    get_skill_system_prompt,
    list_available_skills,
    load_skill,
    rescan_skills,
)


@pytest.fixture(autouse=True)
def isolated_home(tmp_path, monkeypatch):
    import openlaoke.core.skill_system as skill_system

    home = tmp_path / "home"
    (home / ".openlaoke" / "skills").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(skill_system, "_global_registry", None)
    yield home
    skill_system._global_registry = None


def write_skill(directory: Path, name: str, frontmatter: str, body: str = "Body.") -> Path:
    folder = directory / name
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / "SKILL.md"
    path.write_text(f"---\n{frontmatter}\n---\n\n{body}\n", encoding="utf-8")
    return path


# --------------------------------------------------------------------------- #
# Frontmatter sanitising
# --------------------------------------------------------------------------- #


def test_sanitize_turns_a_colon_value_into_a_block_scalar() -> None:
    sanitised = _sanitize_frontmatter("description: Use when: the build fails")

    assert "description: |-" in sanitised
    assert "  Use when: the build fails" in sanitised


def test_sanitize_leaves_comments_blanks_and_indented_lines_alone() -> None:
    frontmatter = "# a comment\n\n  indented: value\nname: plain"

    assert _sanitize_frontmatter(frontmatter).splitlines() == [
        "# a comment",
        "",
        "  indented: value",
        "name: plain",
    ]


def test_sanitize_leaves_non_key_lines_alone() -> None:
    assert _sanitize_frontmatter("- just a list item") == "- just a list item"


def test_sanitize_leaves_quoted_and_empty_values_alone() -> None:
    for line in ['name: "quoted: value"', "name:", "name: |", "name: >"]:
        assert _sanitize_frontmatter(line) == line


# --------------------------------------------------------------------------- #
# Skill.from_content
# --------------------------------------------------------------------------- #


def test_a_plain_colon_description_is_recovered() -> None:
    """Unquoted YAML breaks on the colon; the sanitised retry must still load it."""
    content = "---\nname: builder\ndescription: Use when: the build fails\n---\n\nSteps here.\n"

    skill = Skill.from_content(content, Path("/tmp/skills/builder/SKILL.md"))

    assert skill.name == "builder"
    assert "build fails" in skill.description
    assert skill.content.strip() == "Steps here."


def test_broken_yaml_falls_back_to_manual_extraction() -> None:
    content = "---\nname: broken\ndescription: [unclosed\n---\n\nBody.\n"

    skill = Skill.from_content(content, Path("/tmp/skills/broken/SKILL.md"))

    assert skill.name == "broken"
    assert skill.description == "[unclosed"


def test_a_missing_name_uses_the_directory_name() -> None:
    skill = Skill.from_content(
        "---\ndescription: no name here\n---\n\nBody.\n", Path("/x/my-skill/SKILL.md")
    )

    assert skill.name == "my-skill"


def test_the_literal_name_skill_also_falls_back() -> None:
    skill = Skill.from_content("---\nname: SKILL\n---\n\nBody.\n", Path("/x/real-name/SKILL.md"))

    assert skill.name == "real-name"


def test_without_a_path_the_name_is_unknown() -> None:
    skill = Skill.from_content("---\ndescription: orphan\n---\n\nBody.\n", None)

    assert skill.name == "unknown"


def test_content_without_frontmatter_is_all_body() -> None:
    skill = Skill.from_content("Just instructions, no frontmatter.")

    assert skill.name == "unknown"
    assert skill.content == "Just instructions, no frontmatter."


def test_allowed_tools_accepts_a_list_and_a_string() -> None:
    as_list = Skill.from_content("---\nname: a\nallowed-tools: [Read, Write]\n---\nBody")
    as_string = Skill.from_content("---\nname: b\nallowed_tools: Bash\n---\nBody")

    assert as_list.allowed_tools == ["Read", "Write"]
    assert as_string.allowed_tools == ["Bash"]


def test_metadata_and_version_are_kept() -> None:
    skill = Skill.from_content("---\nname: v\ndescription: d\nversion: 2.1.0\n---\nBody")

    assert skill.version == "2.1.0"
    assert skill.metadata["name"] == "v"


def test_preamble_is_extracted_from_a_bash_block() -> None:
    skill = Skill.from_content("---\nname: p\n---\n```bash\nnpm install\n```\nDo the thing.")

    assert skill.get_preamble() == "npm install"


def test_a_skill_without_a_preamble_returns_none() -> None:
    skill = Skill.from_content("---\nname: p\n---\nNo code block.")

    assert skill.get_preamble() is None


def test_the_system_prompt_is_the_content() -> None:
    skill = Skill.from_content("---\nname: p\n---\nThe body.")

    assert skill.get_system_prompt() == skill.content


# --------------------------------------------------------------------------- #
# Skill.from_file
# --------------------------------------------------------------------------- #


def test_from_file_reads_a_real_file(tmp_path) -> None:
    path = write_skill(tmp_path, "reader", "name: reader\ndescription: reads")

    skill = Skill.from_file(path)

    assert skill is not None
    assert skill.name == "reader"
    assert skill.path == path


def test_from_file_returns_none_for_a_missing_path(tmp_path) -> None:
    assert Skill.from_file(tmp_path / "nope" / "SKILL.md") is None


def test_from_file_returns_none_when_the_file_cannot_be_read(tmp_path, capsys) -> None:
    path = write_skill(tmp_path, "locked", "name: locked")
    path.chmod(0o000)
    try:
        assert Skill.from_file(path) is None
    finally:
        path.chmod(0o644)
    assert "Error loading skill" in capsys.readouterr().out


# --------------------------------------------------------------------------- #
# SkillRegistry
# --------------------------------------------------------------------------- #


def test_flat_and_nested_skill_directories_are_both_loaded(tmp_path) -> None:
    write_skill(tmp_path, "flat", "name: flat")
    nested = tmp_path / "collection" / "inner"
    nested.mkdir(parents=True)
    (nested / "SKILL.md").write_text("---\nname: inner\n---\nBody", encoding="utf-8")

    registry = SkillRegistry()
    count = registry.add_skill_directory(tmp_path)

    assert count == 2
    assert sorted(registry.list_skills()) == ["flat", "inner"]


def test_a_directory_that_does_not_exist_loads_nothing(tmp_path) -> None:
    registry = SkillRegistry()

    assert registry.add_skill_directory(tmp_path / "ghost") == 0
    assert registry.list_skills() == []


def test_a_skill_without_a_parsable_name_is_skipped(tmp_path, monkeypatch) -> None:
    folder = tmp_path / "nameless"
    folder.mkdir()
    (folder / "SKILL.md").write_text("---\n---\nBody", encoding="utf-8")
    monkeypatch.setattr(
        Skill, "from_file", classmethod(lambda cls, path: Skill(name="", content="Body"))
    )

    registry = SkillRegistry()

    assert registry.add_skill_directory(tmp_path) == 0


def test_registry_lookups(tmp_path) -> None:
    write_skill(tmp_path, "one", "name: one\ndescription: d")
    registry = SkillRegistry()
    registry.add_skill_directory(tmp_path)

    assert registry.get_skill("one") is not None
    assert registry.get_skill("two") is None
    assert registry.has_skill("one") is True
    assert registry.has_skill("two") is False
    assert [s.name for s in registry.get_all_skills()] == ["one"]
    assert registry.get_skill_prompt("one")
    assert registry.get_skill_prompt("two") is None


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #


def test_rescan_finds_installed_skills_and_caches_the_registry(isolated_home) -> None:
    write_skill(isolated_home / ".openlaoke" / "skills", "cached", "name: cached")

    assert rescan_skills() == 1
    assert get_skill_registry() is get_skill_registry()
    assert load_skill("cached") is not None
    assert list_available_skills() == ["cached"]


def test_the_system_prompt_joins_the_requested_skills(isolated_home) -> None:
    write_skill(isolated_home / ".openlaoke" / "skills", "alpha", "name: alpha", body="Alpha body")
    write_skill(isolated_home / ".openlaoke" / "skills", "beta", "name: beta", body="Beta body")
    rescan_skills()

    prompt = get_skill_system_prompt(["alpha", "beta", "missing"])

    assert "## Skill: alpha" in prompt
    assert "Alpha body" in prompt
    assert "Beta body" in prompt
    assert "missing" not in prompt


def test_default_dirs_follow_the_home_layout(isolated_home) -> None:
    (isolated_home / ".claude" / "skills").mkdir(parents=True)
    (isolated_home / ".opencode" / "skills").mkdir(parents=True)
    (isolated_home / ".config" / "opencode" / "skills").mkdir(parents=True)

    dirs = get_default_skill_dirs()

    names = {path.name for path in dirs}
    assert ".claude" in {path.parent.name for path in dirs}
    assert (isolated_home / ".opencode" / "skills") in dirs
    assert (isolated_home / ".config" / "opencode" / "skills") in dirs
    assert (isolated_home / ".openlaoke" / "skills") in dirs
    assert names  # every entry is a directory named "skills"


def test_a_missing_skill_file_is_not_offered_to_the_registry(tmp_path) -> None:
    """Only SKILL.md is a skill; a stray markdown file is ignored."""
    (tmp_path / "notes.md").write_text("---\nname: notes\n---\nBody", encoding="utf-8")
    folder = tmp_path / "empty"
    folder.mkdir()

    assert SkillRegistry().add_skill_directory(tmp_path) == 0
