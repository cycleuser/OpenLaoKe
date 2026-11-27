"""Subprocess environment hygiene and crash-safe session writes.

Both come from reading learn-workbuddy (see docs/learn-workbuddy-review.md):
its tool runner hands a child process an allowlist of PATH/locale/TMPDIR
instead of the whole environment, and its transcript appends a single line and
fsyncs instead of rewriting a file in place.
"""

from __future__ import annotations

import json
import os

from openlaoke.core.state import create_app_state
from openlaoke.types.core_types import MessageRole, UserMessage
from openlaoke.utils.security import is_secret_env_name, scrub_environment


def make(tmp_path):
    state = create_app_state(cwd=str(tmp_path))
    state._persist_path = None
    return state


def test_credential_shaped_names_are_recognised() -> None:
    for name in (
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
        "AWS_SECRET_ACCESS_KEY",
        "AZURE_CLIENT_SECRET",
        "MY_SERVICE_PASSWORD",
        "DB_PASSWD",
        "SOME_CREDENTIALS",
        "SSH_AUTH_SOCK",
        "GPG_AGENT_INFO",
        "aws_access_key_id",
    ):
        assert is_secret_env_name(name) is True, name

    for name in ("PATH", "HOME", "LANG", "TMPDIR", "PWD", "SHELL", "TERM", "MY_FLAG"):
        assert is_secret_env_name(name) is False, name


def test_scrub_environment_drops_secrets_and_keeps_the_rest() -> None:
    env = {
        "PATH": "/usr/bin",
        "LANG": "en_US.UTF-8",
        "ANTHROPIC_API_KEY": "sk-ant-secret",
        "GITHUB_TOKEN": "ghp_x",
        "SSH_AUTH_SOCK": "/tmp/agent.sock",
    }

    cleaned = scrub_environment(env)

    assert cleaned == {"PATH": "/usr/bin", "LANG": "en_US.UTF-8"}


def test_scrub_environment_can_be_told_to_keep_one_name() -> None:
    env = {"PATH": "/usr/bin", "NPM_TOKEN": "npm_x"}

    assert scrub_environment(env, allow={"npm_token"})["NPM_TOKEN"] == "npm_x"


def test_the_agent_subprocess_cannot_read_host_keys(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-secret")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    monkeypatch.setenv("OPENLAOKE_TEST_VISIBLE", "yes")
    monkeypatch.delenv("OPENLAOKE_PASS_ENV", raising=False)
    monkeypatch.delenv("OPENLAOKE_NO_ENV_FILTER", raising=False)
    state = make(tmp_path)

    env = state.get_env_vars()

    assert "ANTHROPIC_API_KEY" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert env["OPENLAOKE_TEST_VISIBLE"] == "yes"
    assert "PATH" in env


def test_a_session_variable_is_passed_through_even_if_it_looks_secret(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.delenv("OPENLAOKE_NO_ENV_FILTER", raising=False)
    state = make(tmp_path)
    state.set_env_var("DEPLOY_TOKEN", "explicitly-given")

    assert state.snapshot_env()["DEPLOY_TOKEN"] == "explicitly-given"


def test_the_filter_can_be_switched_off_or_narrowed(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    state = make(tmp_path)

    monkeypatch.setenv("OPENLAOKE_NO_ENV_FILTER", "1")
    assert state.get_env_vars()["OPENAI_API_KEY"] == "sk-test"

    monkeypatch.delenv("OPENLAOKE_NO_ENV_FILTER")
    monkeypatch.setenv("OPENLAOKE_PASS_ENV", "OPENAI_API_KEY")
    assert state.get_env_vars()["OPENAI_API_KEY"] == "sk-test"


# --------------------------------------------------------------------------- #
# atomic session persistence
# --------------------------------------------------------------------------- #
def test_a_saved_session_round_trips(tmp_path) -> None:
    state = make(tmp_path)
    path = tmp_path / "session.json"
    state.set_persist_path(str(path))
    state.add_message(UserMessage(role=MessageRole.USER, content="hello"))

    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["session_id"] == state.session_id
    assert payload["messages"][0]["content"] == "hello"


def test_a_failed_write_leaves_the_previous_session_intact(tmp_path, monkeypatch) -> None:
    state = make(tmp_path)
    path = tmp_path / "session.json"
    state.set_persist_path(str(path))
    state.add_message(UserMessage(role=MessageRole.USER, content="first"))
    good = path.read_text(encoding="utf-8")

    real_dump = json.dump

    def exploding(value, handle, **kwargs):
        handle.write('{"session_id": "half')
        raise OSError("disk full")

    monkeypatch.setattr(json, "dump", exploding)
    try:
        state._persist()
    finally:
        monkeypatch.setattr(json, "dump", real_dump)

    assert path.read_text(encoding="utf-8") == good
    assert not any(name.endswith(".tmp") for name in os.listdir(tmp_path))


def test_the_session_file_is_not_world_readable(tmp_path) -> None:
    state = make(tmp_path)
    path = tmp_path / "session.json"
    state.set_persist_path(str(path))
    state.add_message(UserMessage(role=MessageRole.USER, content="secret plan"))

    assert path.stat().st_mode & 0o077 == 0
