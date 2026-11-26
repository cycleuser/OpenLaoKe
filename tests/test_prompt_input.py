"""Tests for the interactive input layer: the model list and the completer.

Both are pure enough to drive without a terminal: the model list is built from a
config object and the completer is fed a document stub, which is exactly what
prompt_toolkit does when the user types "/".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from openlaoke.core.prompt_input import (
    OpenLaoKeCompleter,
    PromptResult,
    _collect_all_models,
    _get_skill_source,
)
from openlaoke.types.providers import ProviderConfig, ProviderType


@dataclass
class FakeDocument:
    text_before_cursor: str


@dataclass
class FakeProviders:
    providers: dict[str, ProviderConfig]
    active_provider: str = "main"
    active_model: str = ""


@dataclass
class FakeConfig:
    providers: FakeProviders


def provider(
    name: str,
    *,
    models: list[str] | None = None,
    default: str = "",
    label: dict[str, str] | None = None,
    enabled: bool = True,
    base_url: str = "https://api.example.com/v1",
    is_local: bool = False,
    api_key: str = "sk-test",
) -> ProviderConfig:
    return ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key=api_key,
        base_url=base_url,
        default_model=default,
        models=models or [],
        model_labels=label or {},
        enabled=enabled,
        is_local=is_local,
    )


def config_with(
    providers: dict[str, ProviderConfig], active: str = "main", active_model: str = ""
) -> FakeConfig:
    return FakeConfig(FakeProviders(providers=providers, active_provider=active, active_model=active_model))


# --------------------------------------------------------------------------- #
# _collect_all_models
# --------------------------------------------------------------------------- #


def test_models_of_every_ready_provider_are_listed() -> None:
    config = config_with(
        {
            "main": provider("main", models=["a", "b"], default="a"),
            "backup": provider("backup", models=["c"]),
        }
    )

    entries = _collect_all_models(config)

    # The active model first, then grouped by provider name.
    assert [e["display"] for e in entries] == ["main/a", "backup/c", "main/b"]
    assert entries[0]["active"] is True


def test_disabled_and_keyless_providers_are_hidden() -> None:
    config = config_with(
        {
            "main": provider("main", models=["a"]),
            "off": provider("off", models=["b"], enabled=False),
            "nokey": provider("nokey", models=["c"], api_key=""),
        }
    )

    assert [e["provider"] for e in _collect_all_models(config)] == ["main"]


def test_a_provider_default_model_is_never_lost() -> None:
    """A stale models list must not hide the model the provider would use.

    The picker is the only way to choose a model, so a default that the list does
    not mention still has to appear.
    """
    config = config_with({"main": provider("main", models=["old"], default="new")})

    entries = _collect_all_models(config)

    assert [e["model"] for e in entries] == ["new", "old"]


def test_the_active_model_is_added_even_when_unlisted() -> None:
    config = config_with({"main": provider("main", models=["a"])}, active_model="from-cli")

    models = [e["model"] for e in _collect_all_models(config)]

    assert "from-cli" in models
    assert models[0] == "from-cli"


def test_the_active_model_defaults_to_the_provider_default() -> None:
    config = config_with({"main": provider("main", models=["a"], default="a")})

    entries = _collect_all_models(config)

    assert entries[0]["active"] is True
    assert entries[0]["model"] == "a"


def test_labels_are_carried_through() -> None:
    config = config_with(
        {"main": provider("main", models=["a"], label={"a": "Alpha model"})}
    )

    assert _collect_all_models(config)[0]["label"] == "Alpha model"


def test_a_generic_openai_compatible_entry_on_a_typed_provider_url_is_dropped() -> None:
    shared = "https://api.example.com/v1"
    typed = ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key="sk-test",
        base_url=shared,
        default_model="a",
        models=["a"],
    )
    generic = ProviderConfig(
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        api_key="sk-test",
        base_url=shared,
        default_model="a",
        models=["a"],
    )
    config = config_with({"typed": typed, "openai_compatible": generic}, active="typed")

    providers = {e["provider"] for e in _collect_all_models(config)}

    assert providers == {"typed"}


def test_a_generic_entry_stays_when_it_is_the_active_provider() -> None:
    shared = "https://api.example.com/v1"
    typed = ProviderConfig(
        provider_type=ProviderType.OPENAI, api_key="sk-test", base_url=shared, models=["a"]
    )
    generic = ProviderConfig(
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        api_key="sk-test",
        base_url=shared,
        models=["a"],
    )
    config = config_with({"typed": typed, "openai_compatible": generic}, active="openai_compatible")

    assert "openai_compatible" in {e["provider"] for e in _collect_all_models(config)}


def test_duplicate_displays_are_collapsed() -> None:
    config = config_with({"main": provider("main", models=["a", "a"])})
    assert [e["display"] for e in _collect_all_models(config)] == ["main/a"]


def test_no_ready_provider_means_an_empty_list() -> None:
    assert _collect_all_models(config_with({})) == []


def test_collect_loads_the_configuration_when_none_is_passed(monkeypatch) -> None:
    import openlaoke.utils.config as config_module

    fake = config_with({"main": provider("main", models=["a"])})
    monkeypatch.setattr(config_module, "load_config", lambda: fake)

    assert [e["display"] for e in _collect_all_models()] == ["main/a"]


# --------------------------------------------------------------------------- #
# _get_skill_source
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "path,expected",
    [
        ("/Users/x/.config/opencode/skills/a/SKILL.md", "[OpenCode]"),
        ("/Users/x/.opencode/skills/a/SKILL.md", "[OpenCode]"),
        ("/Users/x/.claude/skills/a/SKILL.md", "[Claude]"),
        ("/Users/x/.openlaoke/skills/a/SKILL.md", "[Installed]"),
        ("/tmp/elsewhere/SKILL.md", ""),
        (None, ""),
    ],
)
def test_skill_source_labels(path: Any, expected: str) -> None:
    assert _get_skill_source(path) == expected


# --------------------------------------------------------------------------- #
# Completer
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def isolated_skills(tmp_path, monkeypatch):
    import openlaoke.core.skill_system as skill_system

    home = tmp_path / "home"
    skills = home / ".openlaoke" / "skills"
    skills.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setattr(skill_system, "_global_registry", None)
    monkeypatch.setattr(OpenLaoKeCompleter, "_options_cache", None)
    yield skills
    skill_system._global_registry = None
    OpenLaoKeCompleter._options_cache = None


def install_skill(skills, name: str, description: str = "does a thing") -> None:
    folder = skills / name
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\nBody.\n", encoding="utf-8"
    )


def complete(text: str) -> list[Any]:
    return list(OpenLaoKeCompleter().get_completions(FakeDocument(text), None))


def displays(text: str) -> list[str]:
    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.formatted_text.utils import fragment_list_to_text

    return [fragment_list_to_text(to_formatted_text(c.display)).strip() for c in complete(text)]


def test_nothing_is_completed_unless_the_line_starts_with_a_slash() -> None:
    assert complete("hello") == []
    assert complete("") == []


def test_a_bare_slash_offers_commands_and_skills(isolated_skills) -> None:
    install_skill(isolated_skills, "reviewer")

    offered = displays("/")

    assert "/help" in offered
    assert "/reviewer" in offered


def test_typing_a_prefix_filters_the_commands() -> None:
    offered = displays("/he")

    assert "/help" in offered
    # Prefix matches come first; subsequence matches such as /hotkeys follow.
    assert offered[0] == "/help"


def test_hidden_commands_are_not_offered() -> None:
    assert "/use-skill" not in displays("/use-skill")


def test_aliases_are_offered_with_a_note() -> None:
    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.formatted_text.utils import fragment_list_to_text

    completions = {
        fragment_list_to_text(to_formatted_text(c.display)).strip(): fragment_list_to_text(to_formatted_text(c.display_meta)).strip()
        for c in complete("/diffstat")
    }

    assert completions["/diffstat"] == "Alias for /edits"


def test_a_fuzzy_prefix_still_matches() -> None:
    # "hlp" is a subsequence of "help".
    assert "/help" in displays("/hlp")


def test_completion_replaces_the_whole_typed_text() -> None:
    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.formatted_text.utils import fragment_list_to_text

    completion = next(
        c for c in complete("/he") if fragment_list_to_text(to_formatted_text(c.display)).strip() == "/help"
    )
    # The typed "/he" is replaced wholesale rather than appended to.
    assert completion.start_position == -len("/he")
    assert completion.text == "/help"


def test_skill_completions_carry_their_source(isolated_skills) -> None:
    install_skill(isolated_skills, "writer", "polish prose")
    OpenLaoKeCompleter._options_cache = None

    from prompt_toolkit.formatted_text import to_formatted_text
    from prompt_toolkit.formatted_text.utils import fragment_list_to_text

    completion = next(
        c for c in complete("/writer") if fragment_list_to_text(to_formatted_text(c.display)).strip() == "/writer"
    )
    meta = fragment_list_to_text(to_formatted_text(completion.display_meta))

    assert "[Installed]" in meta
    assert "polish prose" in meta


def test_the_option_list_is_cached_between_keystrokes(isolated_skills) -> None:
    completer = OpenLaoKeCompleter()
    first = completer._get_options()
    second = completer._get_options()
    assert first is second


def test_a_skill_description_is_cut_to_one_line(isolated_skills) -> None:
    folder = isolated_skills / "multiline"
    folder.mkdir()
    (folder / "SKILL.md").write_text(
        '---\nname: multiline\ndescription: "first line\\nsecond line"\n---\n\nBody.\n',
        encoding="utf-8",
    )
    OpenLaoKeCompleter._options_cache = None

    option = next(o for o in OpenLaoKeCompleter()._get_options() if o["name"] == "multiline")

    assert "\n" not in option["description"]


# --------------------------------------------------------------------------- #
# PromptResult helpers
# --------------------------------------------------------------------------- #


def test_prompt_result_predicates() -> None:
    from openlaoke.core.prompt_input import PromptAction

    assert PromptResult(action=PromptAction.TEXT, text="hi").is_text is True
    assert PromptResult(action=PromptAction.EXIT).is_exit is True
    assert PromptResult(action=PromptAction.PICKER).is_picker is True
    assert PromptResult(action=PromptAction.LANG_PICKER).is_lang_picker is True
    assert PromptResult(action=PromptAction.TOGGLE_THINKING).is_toggle_thinking is True
    assert PromptResult(action=PromptAction.TEXT, text="hi").is_exit is False


# --------------------------------------------------------------------------- #
# The text fallback pickers
# --------------------------------------------------------------------------- #


def entries(**kwargs: Any) -> list[dict[str, Any]]:
    return _collect_all_models(config_with({"main": provider("main", models=["a", "b"], default="a")}, **kwargs))


@pytest.mark.asyncio
async def test_text_picker_returns_the_first_entry_on_enter(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert await prompt_input._run_model_picker_text(entries()) == "main/a"


@pytest.mark.asyncio
async def test_text_picker_accepts_a_number_picked_by_the_user(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "2")
    assert await prompt_input._run_model_picker_text(entries()) == "main/b"


@pytest.mark.asyncio
async def test_text_picker_accepts_a_name_fragment(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "B")
    assert await prompt_input._run_model_picker_text(entries()) == "main/b"


@pytest.mark.asyncio
async def test_text_picker_rejects_an_out_of_range_number(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "9")
    assert await prompt_input._run_model_picker_text(entries()) is None


@pytest.mark.asyncio
async def test_text_picker_rejects_an_unknown_name(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "nonexistent")
    assert await prompt_input._run_model_picker_text(entries()) is None


@pytest.mark.asyncio
async def test_text_picker_cancels_on_ctrl_c() -> None:
    from openlaoke.core import prompt_input

    def boom(_prompt="") -> str:
        raise KeyboardInterrupt

    original = __import__("builtins").input
    __import__("builtins").input = boom
    try:
        assert await prompt_input._run_model_picker_text(entries()) is None
    finally:
        __import__("builtins").input = original


# --------------------------------------------------------------------------- #
# The language picker
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_language_picker_returns_an_indexed_language(monkeypatch) -> None:
    from openlaoke.core import prompt_input
    from openlaoke.core.i18n import SUPPORTED_LANGUAGES

    first_code = next(iter(SUPPORTED_LANGUAGES))
    monkeypatch.setattr("builtins.input", lambda _prompt="": "1")

    assert await prompt_input.run_lang_picker_async("en") == first_code


@pytest.mark.asyncio
async def test_language_picker_accepts_a_code(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "zh")
    assert await prompt_input.run_lang_picker_async("en") == "zh"


@pytest.mark.asyncio
async def test_language_picker_accepts_a_display_name(monkeypatch) -> None:
    from openlaoke.core import prompt_input
    from openlaoke.core.i18n import SUPPORTED_LANGUAGES

    code, name = next(iter(SUPPORTED_LANGUAGES.items()))
    monkeypatch.setattr("builtins.input", lambda _prompt="": name.lower())
    assert await prompt_input.run_lang_picker_async("en") == code


@pytest.mark.asyncio
async def test_language_picker_returns_none_for_an_empty_answer(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "")
    assert await prompt_input.run_lang_picker_async("en") is None


@pytest.mark.asyncio
async def test_language_picker_returns_none_for_an_out_of_range_index(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "99")
    assert await prompt_input.run_lang_picker_async("en") is None


@pytest.mark.asyncio
async def test_language_picker_returns_none_for_gibberish(monkeypatch) -> None:
    from openlaoke.core import prompt_input

    monkeypatch.setattr("builtins.input", lambda _prompt="": "klingon")
    assert await prompt_input.run_lang_picker_async("en") is None


@pytest.mark.asyncio
async def test_language_picker_survives_a_closed_stdin() -> None:
    from openlaoke.core import prompt_input

    def boom(_prompt="") -> str:
        raise EOFError

    original = __import__("builtins").input
    __import__("builtins").input = boom
    try:
        assert await prompt_input.run_lang_picker_async("en") is None
    finally:
        __import__("builtins").input = original


# --------------------------------------------------------------------------- #
# The full-screen picker, driven through a pipe
# --------------------------------------------------------------------------- #


def picker_entries(count: int = 6, active_index: int = 0) -> list[dict[str, Any]]:
    return [
        {
            "provider": "p",
            "model": f"m{i}",
            "display": f"p/m{i}",
            "label": "",
            "active": i == active_index,
        }
        for i in range(count)
    ]


def run_picker(entries: list[dict[str, Any]], keys: str) -> Any:
    """Drive the real Application with keystrokes and return its result."""
    from prompt_toolkit.input import create_pipe_input
    from prompt_toolkit.output import DummyOutput

    from openlaoke.core.prompt_input import _build_model_picker_app

    with create_pipe_input() as pipe:
        app = _build_model_picker_app(entries, input=pipe, output=DummyOutput())
        pipe.send_text(keys)
        return app.run()


def test_picker_accepts_the_selected_row_on_enter() -> None:
    assert run_picker(picker_entries(), "\r") == "p/m0"


def test_picker_preselects_the_active_model() -> None:
    assert run_picker(picker_entries(active_index=3), "\r") == "p/m3"


def test_picker_moves_down_and_up() -> None:
    assert run_picker(picker_entries(), "\x1b[B\x1b[B\x1b[A\r") == "p/m1"


def test_picker_wraps_at_the_bottom() -> None:
    # Six rows: five downs reach the last one, a sixth wraps to the first.
    keys = "\x1b[B" * 6 + "\r"
    assert run_picker(picker_entries(6), keys) == "p/m0"


def test_picker_page_down_and_home_and_end() -> None:
    assert run_picker(picker_entries(40), "\x1b[6~\r") != "p/m0"
    assert run_picker(picker_entries(40), "\x1b[6~\x1b[H\r") == "p/m0"
    assert run_picker(picker_entries(40), "\x1b[F\r") == "p/m39"


def test_picker_page_up_from_the_end() -> None:
    result = run_picker(picker_entries(40), "\x1b[F\x1b[5~\r")
    assert result is not None
    assert result != "p/m39"


def test_picker_filters_by_typed_text() -> None:
    assert run_picker(picker_entries(), "m4\r") == "p/m4"


def test_picker_filter_with_no_match_accepts_nothing() -> None:
    assert run_picker(picker_entries(), "zzzz\r") is None


def test_picker_cancels_with_ctrl_c() -> None:
    assert run_picker(picker_entries(), "\x03") is None


# --------------------------------------------------------------------------- #
# run_model_picker_async
# --------------------------------------------------------------------------- #


class FakeApp:
    def __init__(self, result: Any = None, raises: BaseException | None = None) -> None:
        self.result = result
        self.raises = raises
        self.ran = False

    async def run_async(self) -> Any:
        self.ran = True
        if self.raises is not None:
            raise self.raises
        return self.result


@pytest.fixture()
def picker_env(monkeypatch):
    """Stub out discovery, probing and the config for run_model_picker_async."""
    import openlaoke.core.model_discovery as discovery
    import openlaoke.core.prompt_input as prompt_input
    import openlaoke.types.providers as providers_module
    import openlaoke.utils.config as config_module

    main = provider("main", models=["listed"], default="listed")
    config = config_with({"main": main}, active="main")

    async def no_probe(_providers):
        return {}

    async def discovery_result(provider_config, timeout=2.5, use_catalog=False):
        return ["live-a", "live-b"], {"live-a": "Alpha", "live-b": "Beta"}

    monkeypatch.setattr(config_module, "load_config", lambda: config)
    monkeypatch.setattr(providers_module, "probe_local_providers", no_probe)
    monkeypatch.setattr(discovery, "discover_model_details", discovery_result)
    return {"config": config, "module": prompt_input, "provider": main}


@pytest.mark.asyncio
async def test_picker_uses_the_live_model_list(picker_env, monkeypatch) -> None:
    app = FakeApp(result="p/live-b")
    monkeypatch.setattr(picker_env["module"], "_build_model_picker_app", lambda entries: app)

    result = await picker_env["module"].run_model_picker_async()

    assert result == "p/live-b"
    assert app.ran is True
    # The discovered ids and labels replaced what the config had.
    assert picker_env["provider"].models == ["live-a", "live-b"]
    assert picker_env["provider"].model_labels == {"live-a": "Alpha", "live-b": "Beta"}


@pytest.mark.asyncio
async def test_picker_returns_none_when_nothing_is_selectable(picker_env, monkeypatch) -> None:
    picker_env["provider"].api_key = ""
    picker_env["provider"].enabled = False
    monkeypatch.setattr(picker_env["module"], "_build_model_picker_app", lambda entries: FakeApp())

    assert await picker_env["module"].run_model_picker_async() is None


@pytest.mark.asyncio
async def test_picker_returns_none_when_the_app_is_cancelled(picker_env, monkeypatch) -> None:
    monkeypatch.setattr(
        picker_env["module"], "_build_model_picker_app", lambda entries: FakeApp(result=None)
    )
    assert await picker_env["module"].run_model_picker_async() is None


@pytest.mark.asyncio
async def test_picker_returns_none_on_ctrl_c(picker_env, monkeypatch) -> None:
    monkeypatch.setattr(
        picker_env["module"],
        "_build_model_picker_app",
        lambda entries: FakeApp(raises=KeyboardInterrupt()),
    )
    assert await picker_env["module"].run_model_picker_async() is None


@pytest.mark.asyncio
async def test_picker_falls_back_to_the_text_menu_when_the_app_cannot_start(
    picker_env, monkeypatch
) -> None:
    async def fallback(entries):
        return "text-choice"

    monkeypatch.setattr(
        picker_env["module"],
        "_build_model_picker_app",
        lambda entries: FakeApp(raises=RuntimeError("no terminal")),
    )
    monkeypatch.setattr(picker_env["module"], "_run_model_picker_text", fallback)

    assert await picker_env["module"].run_model_picker_async() == "text-choice"


@pytest.mark.asyncio
async def test_a_failing_discovery_keeps_the_configured_models(picker_env, monkeypatch) -> None:
    import openlaoke.core.model_discovery as discovery

    async def broken(provider_config, timeout=2.5, use_catalog=False):
        raise RuntimeError("endpoint down")

    monkeypatch.setattr(discovery, "discover_model_details", broken)
    monkeypatch.setattr(
        picker_env["module"], "_build_model_picker_app", lambda entries: FakeApp(result="p/listed")
    )

    assert await picker_env["module"].run_model_picker_async() == "p/listed"
    assert picker_env["provider"].models == ["listed"]


@pytest.mark.asyncio
async def test_an_empty_discovery_result_keeps_the_configured_models(picker_env, monkeypatch) -> None:
    import openlaoke.core.model_discovery as discovery

    async def empty(provider_config, timeout=2.5, use_catalog=False):
        return [], {}

    monkeypatch.setattr(discovery, "discover_model_details", empty)
    monkeypatch.setattr(
        picker_env["module"], "_build_model_picker_app", lambda entries: FakeApp(result="p/listed")
    )

    await picker_env["module"].run_model_picker_async()

    assert picker_env["provider"].models == ["listed"]


# --------------------------------------------------------------------------- #
# PromptSessionManager
# --------------------------------------------------------------------------- #


@pytest.fixture()
def manager_env(tmp_path, monkeypatch):
    import openlaoke.core.prompt_input as prompt_input

    history = tmp_path / "history.txt"
    monkeypatch.setattr(prompt_input, "HISTORY_FILE", history)
    return prompt_input, history


def test_session_is_built_once_and_configured(manager_env) -> None:
    prompt_input, history = manager_env

    manager = prompt_input.PromptSessionManager(multiline=True)
    session = manager.get_session()

    assert manager.get_session() is session
    assert session.multiline is True
    assert history.parent.exists()


def test_style_defines_the_prompt_and_completion_classes(manager_env) -> None:
    prompt_input, _history = manager_env

    style = prompt_input.PromptSessionManager()._build_style()

    # style_rules is a list of (class name, style string) pairs.
    rules = {rule[0] for rule in style.style_rules}
    assert "prompt" in rules
    assert "completion" in rules


def test_keybindings_cover_the_three_pickers(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()

    kb = manager._build_keybindings()
    keys = {binding.keys for binding in kb.bindings}

    assert ("c-p",) in keys
    assert ("c-g",) in keys
    assert ("c-l",) in keys


def test_each_picker_key_requests_its_action_and_leaves_the_prompt(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()

    class FakeEvent:
        class app:  # noqa: N801 - mimics prompt_toolkit's event.app
            @staticmethod
            def exit(**kwargs: Any) -> None:
                assert isinstance(kwargs["exception"], EOFError)

    event = FakeEvent()
    for binding in manager._build_keybindings().bindings:
        binding.handler(event)

    assert manager._picker_requested is True
    assert manager._toggle_thinking_requested is True
    assert manager._lang_picker_requested is True


class FakeSession:
    def __init__(self, result: Any = "", raises: BaseException | None = None) -> None:
        self.result = result
        self.raises = raises
        self.prompts: list[str] = []

    async def prompt_async(self, text: str) -> Any:
        self.prompts.append(text)
        if self.raises is not None:
            raise self.raises
        return self.result


@pytest.mark.asyncio
async def test_text_input_is_stripped(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()
    session = FakeSession(result="  list the files  \n")
    manager.get_session = lambda: session  # type: ignore[method-assign]

    result = await manager.get_user_input()

    assert result.action is prompt_input.PromptAction.TEXT
    assert result.text == "list the files"
    assert session.prompts == ["OpenLaoKe: "]


@pytest.mark.asyncio
async def test_an_empty_line_is_still_a_text_result(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()
    manager.get_session = lambda: FakeSession(result="   ")  # type: ignore[method-assign]

    result = await manager.get_user_input()

    assert result.is_text is True
    assert result.text == ""


@pytest.mark.asyncio
async def test_ctrl_c_requests_an_exit(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()
    manager.get_session = lambda: FakeSession(raises=KeyboardInterrupt())  # type: ignore[method-assign]

    assert (await manager.get_user_input()).is_exit is True


@pytest.mark.asyncio
async def test_eof_without_a_request_is_an_exit(manager_env) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()
    manager.get_session = lambda: FakeSession(raises=EOFError())  # type: ignore[method-assign]

    assert (await manager.get_user_input()).is_exit is True


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "flag,expected",
    [
        ("_picker_requested", "is_picker"),
        ("_toggle_thinking_requested", "is_toggle_thinking"),
        ("_lang_picker_requested", "is_lang_picker"),
    ],
)
async def test_eof_carries_the_requested_action(manager_env, flag: str, expected: str) -> None:
    prompt_input, _history = manager_env
    manager = prompt_input.PromptSessionManager()
    setattr(manager, flag, True)

    class FlagSession:
        async def prompt_async(self, _text: str) -> Any:
            # The keybinding sets the flag and exits with EOFError; get_user_input
            # resets the flags first, so set it here to model that sequence.
            setattr(manager, flag, True)
            raise EOFError

    manager.get_session = lambda: FlagSession()  # type: ignore[method-assign]

    result = await manager.get_user_input()

    assert getattr(result, expected) is True


def test_create_prompt_session_returns_a_session(manager_env) -> None:
    prompt_input, _history = manager_env
    assert prompt_input.create_prompt_session() is not None


@pytest.mark.asyncio
async def test_module_level_get_user_input_maps_the_results(manager_env) -> None:
    prompt_input, _history = manager_env
    prompt_input._fallback_manager = None

    class Session:
        def __init__(self, result: Any = "") -> None:
            self.result = result

        async def prompt_async(self, _text: str) -> Any:
            return self.result

    assert await prompt_input.get_user_input(Session("hello")) == "hello"
    assert await prompt_input.get_user_input(Session("")) is None
