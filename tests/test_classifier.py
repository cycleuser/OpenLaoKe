"""Tests for the permission classifier (fast rules + AI/hybrid paths).

The fast path delegates to bash_classifier; the AI/hybrid paths call a client
that may be missing, absent, or failing - all of which must fall back to the
rule-based result rather than raising or silently allowing.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from openlaoke.types.core_types import PermissionResult
from openlaoke.utils.permissions import classifier as clf


# ---- fakes -----------------------------------------------------------------
class _Block:
    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _Client:
    def __init__(self, text=None, raises=False):
        self._text = text
        self._raises = raises
        self.called = 0

    async def create_message(self, **_kw):
        self.called += 1
        if self._raises:
            raise RuntimeError("no network")
        return _Resp(self._text)


def _state(client):
    return SimpleNamespace(get_client=lambda: client)


# ---- fast path -------------------------------------------------------------
def test_fast_classify_decision_mapping():
    safe = clf.fast_classify_bash("ls -la")
    assert safe.decision == PermissionResult.ALLOW
    assert safe.safety_level == clf.CommandSafetyLevel.SAFE

    destructive = clf.fast_classify_bash("rm -rf /")
    assert destructive.decision == PermissionResult.DENY

    dangerous = clf.fast_classify_bash("echo hi > /etc/x")
    assert dangerous.decision == PermissionResult.ASK


# ---- AI path fallbacks -----------------------------------------------------
async def test_ai_missing_get_client_returns_fast():
    r = await clf.ai_classify_bash("npm install", object())
    assert r.decision == clf.fast_classify_bash("npm install").decision


async def test_ai_client_none_returns_fast():
    r = await clf.ai_classify_bash("npm install", _state(None))
    assert r.decision == PermissionResult.ALLOW


async def test_ai_client_without_create_message_returns_fast():
    r = await clf.ai_classify_bash("npm install", _state(object()))
    assert r.decision == PermissionResult.ALLOW


async def test_ai_safe_text_allows():
    client = _Client("SAFE: installing dependencies")
    r = await clf.ai_classify_bash("npm install", _state(client))
    assert r.decision == PermissionResult.ALLOW
    assert client.called == 1
    assert r.reason.startswith("AI analysis")


async def test_ai_destructive_text_denies():
    r = await clf.ai_classify_bash("npm install", _state(_Client("DESTRUCTIVE: wipes disk")))
    assert r.decision == PermissionResult.DENY


async def test_ai_exception_falls_back_to_fast():
    r = await clf.ai_classify_bash("npm install", _state(_Client(raises=True)))
    assert r.decision == PermissionResult.ALLOW  # fast result for npm install


async def test_ai_short_circuits_on_high_confidence():
    # 'ls -la' is HIGH-confidence safe -> no client call at all.
    client = _Client(raises=True)
    r = await clf.ai_classify_bash("ls -la", _state(client))
    assert r.decision == PermissionResult.ALLOW
    assert client.called == 0


async def test_ai_short_circuits_on_destructive():
    # Destructive is never overridden by the AI, even if it would say SAFE.
    client = _Client("SAFE")
    r = await clf.ai_classify_bash("rm -rf /", _state(client))
    assert r.decision == PermissionResult.DENY
    assert client.called == 0


# ---- hybrid + dispatch -----------------------------------------------------
async def test_hybrid_uses_ai_for_medium_confidence():
    client = _Client("SAFE")
    r = await clf.hybrid_classify_bash("npm install", _state(client))
    assert r.decision == PermissionResult.ALLOW
    assert client.called == 1


async def test_classify_bash_fast_mode_skips_ai():
    client = _Client(raises=True)
    r = await clf.classify_bash("npm install", _state(client), mode=clf.ClassifierMode.FAST)
    assert client.called == 0
    assert r.decision == PermissionResult.ALLOW


# ---- classify_tool ---------------------------------------------------------
@pytest.mark.parametrize(
    ("tool", "inp", "expected"),
    [
        ("Read", {}, PermissionResult.ALLOW),
        ("Glob", {}, PermissionResult.ALLOW),
        ("Write", {}, PermissionResult.ASK),
        ("Edit", {}, PermissionResult.ASK),
        ("Bash", {"command": "ls"}, PermissionResult.ALLOW),
        ("Bash", {"command": "rm -rf /"}, PermissionResult.DENY),
        ("Mystery", {}, PermissionResult.ASK),
    ],
)
def test_classify_tool(tool, inp, expected):
    assert clf.classify_tool(tool, inp).decision == expected
