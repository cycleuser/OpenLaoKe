"""Tests for the pi-compatible slash commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from openlaoke.commands import pi_commands
from openlaoke.commands.base import CommandContext
from openlaoke.commands.registry import _commands, get_command, register_all
from openlaoke.core.state import create_app_state
from openlaoke.types.core_types import AssistantMessage, MessageRole

PI_COMMANDS = {
    "new",
    "name",
    "session",
    "tree",
    "fork",
    "clone",
    "import",
    "share",
    "copy",
    "changelog",
    "hotkeys",
    "trust",
    "login",
    "logout",
    "reload",
    "scoped-models",
    "prompt",
}


@pytest.fixture
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pi_commands, "_OPENLAOKE_DIR", tmp_path)
    register_all()
    state = create_app_state(cwd=str(tmp_path))

    async def run(name: str, args: str = ""):
        command = get_command(name)
        assert command is not None, f"command /{name} not registered"
        return await command.execute(CommandContext(app_state=state, args=args))

    return run, state, tmp_path


class TestRegistration:
    def test_all_pi_commands_registered(self) -> None:
        register_all()
        names = {c.name for c in _commands.values()}
        missing = PI_COMMANDS - names
        assert not missing, f"missing pi commands: {missing}"


class TestSessionCommands:
    async def test_new_resets_session(self, env, monkeypatch: pytest.MonkeyPatch) -> None:
        run, state, tmp = env

        class FakeManager:
            def __init__(self, *args, **kwargs):
                self.session_dir = str(tmp)

            def save_session(self, app_state):
                return str(tmp / "session.json")

        monkeypatch.setattr("openlaoke.core.sessions.SessionManager", FakeManager)
        state.messages.append(AssistantMessage(role=MessageRole.ASSISTANT, content="hi"))
        old_id = state.session_id
        result = await run("new")
        assert result.success
        assert state.messages == []
        assert state.session_id != old_id

    async def test_name_set_and_get(self, env) -> None:
        run, _state, _tmp = env
        assert "unset" in (await run("name")).message
        assert "demo" in (await run("name", "demo")).message
        assert "demo" in (await run("name")).message

    async def test_session_reports_info(self, env) -> None:
        run, _state, _tmp = env
        message = (await run("session")).message
        assert "Session" in message
        assert "messages:" in message

    async def test_tree_without_turns(self, env) -> None:
        run, _state, _tmp = env
        result = await run("tree")
        assert result.success
        assert "No recorded turns" in result.message

    async def test_clone_creates_new_session(self, env) -> None:
        run, state, _tmp = env
        old_id = state.session_id
        result = await run("clone")
        assert result.success
        assert state.session_id != old_id or "Cloned" in result.message


class TestScopedModels:
    async def test_add_list_remove_clear(self, env) -> None:
        run, _state, _tmp = env
        assert "No scoped models" in (await run("scoped-models")).message
        assert "gpt-4o" in (await run("scoped-models", "add gpt-4o")).message
        assert "gpt-4o" in (await run("scoped-models", "list")).message
        assert "gpt-4o" in (await run("scoped-models", "remove gpt-4o")).message
        assert "No scoped models" in (await run("scoped-models")).message
        await run("scoped-models", "add a")
        assert "Cleared" in (await run("scoped-models", "clear")).message


class TestTrust:
    async def test_on_off_status(self, env) -> None:
        run, _state, _tmp = env
        assert "untrusted" in (await run("trust", "status")).message
        assert "trusted" in (await run("trust", "on")).message
        assert "trusted" in (await run("trust", "status")).message
        assert "untrusted" in (await run("trust", "off")).message

    async def test_invalid_subcommand(self, env) -> None:
        run, _state, _tmp = env
        assert not (await run("trust", "maybe")).success


class TestMiscCommands:
    async def test_hotkeys(self, env) -> None:
        run, _state, _tmp = env
        message = (await run("hotkeys")).message
        assert "Ctrl+P" in message

    async def test_changelog(self, env) -> None:
        run, _state, _tmp = env
        result = await run("changelog")
        assert result.success
        assert "Changelog" in result.message

    async def test_copy_without_message(self, env) -> None:
        run, _state, _tmp = env
        assert not (await run("copy")).success

    async def test_import_missing_file(self, env) -> None:
        run, _state, _tmp = env
        result = await run("import", "/nonexistent/session.json")
        assert not result.success

    async def test_import_openlaoke_json(self, env) -> None:
        run, state, tmp = env
        payload = {
            "session_id": "s1",
            "messages": [
                {"role": "user", "content": "hello"},
                {"role": "assistant", "content": "world"},
            ],
        }
        path = tmp / "session.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        result = await run("import", str(path))
        assert result.success
        assert len(state.messages) == 2

    async def test_login_lists_providers(self, env) -> None:
        run, _state, _tmp = env
        result = await run("login")
        assert result.success
        assert "Providers:" in result.message

    async def test_logout_unknown_provider(self, env) -> None:
        run, _state, _tmp = env
        assert not (await run("logout", "definitely-not-a-provider")).success

    async def test_reload(self, env) -> None:
        run, _state, _tmp = env
        result = await run("reload")
        assert result.success
        assert "skill" in result.message


class TestPromptCommand:
    async def test_empty_listing(self, env, monkeypatch: pytest.MonkeyPatch) -> None:
        run, _state, _tmp = env
        from openlaoke.core import prompt_templates as pt

        monkeypatch.setattr(pt, "_global_registry", pt.PromptTemplateRegistry())
        result = await run("prompt")
        assert "No prompt templates" in result.message

    async def test_expand_and_submit(self, env, monkeypatch: pytest.MonkeyPatch) -> None:
        run, _state, tmp = env
        from openlaoke.core import prompt_templates as pt

        prompts = tmp / "prompts"
        prompts.mkdir()
        (prompts / "greet.md").write_text(
            "---\ndescription: Greet someone\n---\nHello $1, focus on ${2:-everything}.\n",
            encoding="utf-8",
        )
        registry = pt.PromptTemplateRegistry()
        registry.add_directory(prompts)
        monkeypatch.setattr(pt, "_global_registry", registry)

        result = await run("prompt", "greet World security")
        assert result.success
        assert result.message == "Hello World, focus on security."
        assert result.submit_text == "Hello World, focus on security."

    async def test_unknown_template(self, env, monkeypatch: pytest.MonkeyPatch) -> None:
        run, _state, _tmp = env
        from openlaoke.core import prompt_templates as pt

        monkeypatch.setattr(pt, "_global_registry", pt.PromptTemplateRegistry())
        result = await run("prompt", "does-not-exist")
        assert not result.success
