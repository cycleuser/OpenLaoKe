"""Tests for the permission rule engine (deny-first, subject narrowing).

The module's documented invariant is "deny > ask > allow > approved > default",
and a stored "Always allow" must never override an explicit deny. These are the
checks that decide whether a tool call actually runs, so they are worth pinning.
"""

from __future__ import annotations

from openlaoke.types.core_types import PermissionMode, PermissionResult
from openlaoke.types.permissions import PermissionConfig, PermissionRule


def test_bypass_and_auto_allow_everything():
    for mode in (PermissionMode.BYPASS, PermissionMode.AUTO):
        cfg = PermissionConfig(mode=mode)
        assert cfg.check_tool("Bash") == PermissionResult.ALLOW
        assert cfg.check_tool_subject("Bash", "rm -rf /") == PermissionResult.ALLOW


def test_deny_beats_allow():
    cfg = PermissionConfig(
        always_allow_rules=[PermissionRule("Bash", PermissionResult.ALLOW)],
        always_deny_rules=[PermissionRule("Bash", PermissionResult.DENY)],
    )
    assert cfg.check_tool("Bash") == PermissionResult.DENY


def test_deny_beats_stored_approval():
    cfg = PermissionConfig()
    cfg.approve_tool("Bash", remember=True)
    cfg.deny_tool("Bash")
    assert cfg.check_tool("Bash") == PermissionResult.DENY
    # deny_tool also drops the tool-level approval
    assert "Bash" not in cfg.approved_tools


def test_ask_rule_for_defaults():
    cfg = PermissionConfig.defaults()
    assert cfg.check_tool("Read") == PermissionResult.ALLOW
    assert cfg.check_tool("Bash") == PermissionResult.ASK
    assert cfg.check_tool("Write") == PermissionResult.ASK


def test_subject_approval_is_narrow():
    cfg = PermissionConfig()
    cfg.approve_subject("Bash", "git status")
    assert cfg.check_tool_subject("Bash", "git status") == PermissionResult.ALLOW
    # A different subject still falls back to the tool-level ask.
    assert cfg.check_tool_subject("Bash", "rm -rf /") == PermissionResult.ASK


def test_empty_subject_falls_back_to_tool_approval():
    cfg = PermissionConfig()
    cfg.approve_subject("Bash", "")
    assert "Bash" in cfg.approved_tools
    assert cfg.check_tool_subject("Bash", "anything") == (
        # tool-level approval wins -> ALLOW via check_tool ordering
        PermissionResult.ALLOW
    )


def test_deny_subject_beats_approved_subject():
    cfg = PermissionConfig()
    cfg.approve_subject("Bash", "git status")
    cfg.deny_subject("Bash", "git status")
    assert cfg.check_tool_subject("Bash", "git status") == PermissionResult.DENY


def test_deny_subject_wildcard_subject():
    cfg = PermissionConfig()
    cfg.always_deny_rules.append(PermissionRule("Bash(rm *)", PermissionResult.DENY))
    assert cfg.check_tool_subject("Bash", "rm -rf /") == PermissionResult.DENY
    # A non-matching subject is not denied by that rule.
    assert cfg.check_tool_subject("Bash", "git status") != PermissionResult.DENY
