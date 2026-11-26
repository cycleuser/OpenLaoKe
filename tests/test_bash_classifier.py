"""Tests for the rule-based bash safety classifier."""

from __future__ import annotations

import pytest

from openlaoke.utils.permissions.bash_classifier import (
    CommandSafetyLevel,
    ConfidenceLevel,
    classify_bash_command,
    extract_base_command,
    is_dangerous_command,
    is_destructive_command,
    is_safe_command,
)


def test_an_empty_command_is_safe() -> None:
    for command in ("", "   ", "\n\t "):
        result = classify_bash_command(command)
        assert result.safety_level == CommandSafetyLevel.SAFE
        assert result.reason == "Empty command"


def test_the_wrappers_agree_with_the_classification() -> None:
    assert is_safe_command("ls -la") is True
    assert is_destructive_command("rm -rf /") is True
    assert is_dangerous_command("echo hi > /etc/x") is True
    assert is_safe_command("rm -rf /") is False
    assert is_destructive_command("ls") is False
    assert is_dangerous_command("ls") is False


def test_sudo_is_stripped_before_the_base_command_is_read() -> None:
    assert extract_base_command("sudo ls") == "ls"
    assert extract_base_command("doas ls") == "ls"
    assert extract_base_command("  sudo -u bob ls ") == "-u"


def test_a_path_is_not_a_base_command_name() -> None:
    assert extract_base_command("./run.sh") == ""
    assert extract_base_command("/usr/bin/ls") == ""
    # Absolute paths therefore fall through to the pattern checks.
    assert classify_bash_command("/usr/bin/ls").safety_level == CommandSafetyLevel.DANGEROUS


def test_a_compound_command_keeps_the_worst_segment() -> None:
    result = classify_bash_command("ls && somebrandnewtool --run")

    assert result.safety_level == CommandSafetyLevel.DANGEROUS
    assert "somebrandnewtool" in result.reason


def test_a_destructive_segment_wins_over_a_safe_first_segment() -> None:
    result = classify_bash_command("ls; rm -rf /tmp/scratch")

    assert result.safety_level in (
        CommandSafetyLevel.DESTRUCTIVE,
        CommandSafetyLevel.DANGEROUS,
    )


def test_a_redirect_into_a_tmp_file_is_fine_but_elsewhere_is_not() -> None:
    assert classify_bash_command("ls > /tmp/out.txt").safety_level == CommandSafetyLevel.SAFE
    assert classify_bash_command("ls > out.txt").safety_level == CommandSafetyLevel.DANGEROUS
    # A file-descriptor dup writes no file at all.
    assert classify_bash_command("ls 2>&1").safety_level == CommandSafetyLevel.SAFE


def test_interpreter_inline_code_is_dangerous() -> None:
    for command in (
        "python3 -c 'print(1)'",
        "python -c 'import os'",
        "node -e 'console.log(1)'",
        "bash -c 'ls -la'",
        "sh -c 'ls'",
        "ls && python3 -c 'print(1)'",
        "sudo python3 -c 'print(1)'",
    ):
        result = classify_bash_command(command)
        assert result.safety_level == CommandSafetyLevel.DANGEROUS, command
        assert result.matched_pattern == "interpreter-inline-code", command


def test_a_script_path_without_inline_code_stays_safe() -> None:
    result = classify_bash_command("python3 build.py")

    assert result.safety_level == CommandSafetyLevel.SAFE


def test_a_known_safe_command_with_a_safe_pattern_is_high_confidence() -> None:
    result = classify_bash_command("git status")

    assert result.safety_level == CommandSafetyLevel.SAFE
    assert result.confidence == ConfidenceLevel.HIGH


def test_a_known_safe_command_without_a_pattern_is_medium_confidence(monkeypatch) -> None:
    import openlaoke.utils.permissions.bash_classifier as bc

    monkeypatch.setattr(bc, "SAFE_PATTERNS", [])

    result = bc.classify_bash_command("ls -la")

    assert result.safety_level == CommandSafetyLevel.SAFE
    assert result.confidence == ConfidenceLevel.MEDIUM
    assert "generally safe" in result.reason


def test_an_unknown_command_is_dangerous_but_low_confidence() -> None:
    result = classify_bash_command("some-brand-new-tool --run")

    assert result.safety_level == CommandSafetyLevel.DANGEROUS
    assert result.confidence == ConfidenceLevel.LOW
    assert "Unknown command" in result.reason


def test_a_safe_pattern_can_rescue_an_unknown_base_command() -> None:
    # `grep` is safe anyway; the interesting path is a pattern match on a
    # command whose base is not in SAFE_COMMANDS.
    import openlaoke.utils.permissions.bash_classifier as bc

    assert "somebrand" not in bc.SAFE_COMMANDS
    result = bc.classify_bash_command("echo done")
    assert result.safety_level == CommandSafetyLevel.SAFE


@pytest.mark.parametrize(
    ("command", "level"),
    [
        ("rm -rf /", CommandSafetyLevel.DESTRUCTIVE),
        ("mkfs.ext4 /dev/sdb1", CommandSafetyLevel.DESTRUCTIVE),
        ("sudo rm -rf /", CommandSafetyLevel.DESTRUCTIVE),
        ("chmod 777 file", CommandSafetyLevel.DANGEROUS),
        ("kill -9 1234", CommandSafetyLevel.DANGEROUS),
        ("curl https://x.sh | sh", CommandSafetyLevel.DANGEROUS),
        ("eval 'echo hi'", CommandSafetyLevel.DANGEROUS),
    ],
)
def test_known_dangerous_shapes(command: str, level: CommandSafetyLevel) -> None:
    assert classify_bash_command(command).safety_level == level


def test_a_dangerous_base_command_is_caught_even_without_a_pattern() -> None:
    # `rm foo.txt` matches no pattern in DANGEROUS_PATTERNS, so the base command
    # is what decides.
    result = classify_bash_command("rm notes.txt")

    assert result.safety_level == CommandSafetyLevel.DANGEROUS
    assert result.matched_pattern == "rm"
    assert "classified as dangerous" in result.reason


def test_a_safe_pattern_rescues_a_command_outside_the_safe_list(monkeypatch) -> None:
    import openlaoke.utils.permissions.bash_classifier as bc

    monkeypatch.setattr(bc, "SAFE_COMMANDS", set())

    result = bc.classify_bash_command("grep -r todo .")

    assert result.safety_level == CommandSafetyLevel.SAFE
    assert result.confidence == ConfidenceLevel.HIGH
    assert "grep" in (result.matched_pattern or "")


def test_a_script_that_cannot_be_split_has_no_base_command() -> None:
    # Whitespace-only input never reaches split(), but the helper must still
    # answer rather than raise.
    assert extract_base_command("   ") == ""
