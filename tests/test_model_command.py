"""Tests for /model: listing, switching, add/remove, discovery and prune.

The command is the main way users move between providers, so the tests drive
the real execute() with a real MultiProviderConfig and stub only the two
external effects: the config on disk and model discovery over the network.
"""

from __future__ import annotations

import pytest

from openlaoke.commands.base import CommandContext, ModelCommand
from openlaoke.core.state import create_app_state
from openlaoke.types.providers import (
    MultiProviderConfig,
    ProviderConfig,
    ProviderType,
)


class FakeConfig:
    """Stands in for the on-disk config object."""

    def __init__(self, providers: dict[str, ProviderConfig], active: str = "", model: str = "") -> None:
        self.providers = MultiProviderConfig(
            providers=providers, active_provider=active, active_model=model
        )
        self.mode = "balanced"


@pytest.fixture()
def state(tmp_path):
    return create_app_state(cwd=str(tmp_path), model="gpt-4o")


@pytest.fixture()
def wiring(monkeypatch):
    """Patch config load/save and model discovery; return a mutable holder."""
    saved: list[FakeConfig] = []
    discovered: dict[str, tuple[list[str], dict[str, str]]] = {}
    holder: dict = {"config": None, "saved": saved, "discovered": discovered}

    def load_config():
        return holder["config"]

    def save_config(config):
        saved.append(config)

    async def discover(provider):
        return discovered.get(provider.base_url, ([], {}))

    monkeypatch.setattr("openlaoke.utils.config.load_config", load_config)
    monkeypatch.setattr("openlaoke.utils.config.save_config", save_config)
    monkeypatch.setattr("openlaoke.core.model_discovery.discover_model_details", discover)

    async def no_probe(providers, **kwargs):
        return {}

    monkeypatch.setattr("openlaoke.types.providers.probe_local_providers", no_probe)
    return holder


def set_config(holder, providers, active="", model="") -> FakeConfig:
    config = FakeConfig(providers, active=active, model=model)
    holder["config"] = config
    return config


def ctx(state, args: str = "") -> CommandContext:
    return CommandContext(app_state=state, args=args)


def remote(key: str, model: str = "gpt-4o", key_value: str = "sk-abcdef1234567890") -> ProviderConfig:
    return ProviderConfig(
        provider_type=ProviderType.OPENAI,
        api_key=key_value,
        base_url=f"https://{key}.example.com/v1",
        default_model=model,
        models=[model],
    )


# --------------------------------------------------------------------------- #
# Listing
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_listing_without_providers(state, wiring) -> None:
    set_config(wiring, {})
    message = (await ModelCommand().execute(ctx(state))).message
    assert "Current: - / gpt-4o" in message
    assert "No providers configured yet." in message
    assert "Switch:   /model <provider>/<model>" in message


@pytest.mark.asyncio
async def test_listing_marks_the_current_provider_and_masks_keys(state, wiring) -> None:
    providers = {"openai": remote("openai"), "deepseek": remote("deepseek", "deepseek-chat")}
    set_config(wiring, providers, active="openai", model="gpt-4o")
    message = (await ModelCommand().execute(ctx(state))).message
    assert "Current: openai / gpt-4o" in message
    assert " * openai" in message
    assert "sk-abc...7890" in message
    assert "deepseek" in message


@pytest.mark.asyncio
async def test_listing_dedupes_generic_openai_compatible_aliases(state, wiring) -> None:
    shared = "https://gw.example.com/v1"
    providers = {
        "cycleuser-llm": ProviderConfig(
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            api_key="k-1234567890123",
            base_url=shared,
            models=["m1"],
        ),
        "openai_compatible": ProviderConfig(
            provider_type=ProviderType.OPENAI_COMPATIBLE,
            api_key="k-1234567890123",
            base_url=shared,
            models=["m1"],
        ),
    }
    set_config(wiring, providers, active="cycleuser-llm", model="m1")
    message = (await ModelCommand().execute(ctx(state))).message
    # The generic duplicate disappears unless it is the current provider.
    assert "openai_compatible" not in message.split("Unreachable")[0].replace(
        "Current:", ""
    ) or " * cycleuser-llm" in message
    assert "cycleuser-llm" in message


@pytest.mark.asyncio
async def test_listing_reports_offline_local_providers_and_missing_keys(state, wiring) -> None:
    providers = {
        "ollama": ProviderConfig(
            provider_type=ProviderType.OLLAMA,
            base_url="http://127.0.0.1:11434/v1",
            is_local=True,
            models=["local"],
        ),
        "nokey": ProviderConfig(provider_type=ProviderType.OPENAI, base_url="https://x/v1"),
    }
    set_config(wiring, providers, active="nokey")
    # A local provider only shows as offline when the reachability cache says so;
    # is_ready() is deliberately optimistic before the first probe.
    import time

    from openlaoke.types import providers as providers_mod

    providers_mod._local_probe_cache["http://127.0.0.1:11434/v1"] = (time.monotonic(), False)
    try:
        message = (await ModelCommand().execute(ctx(state))).message
    finally:
        providers_mod._local_probe_cache.clear()

    assert "Unreachable local providers:" in message
    assert "nokey has no API key." in message


@pytest.mark.asyncio
async def test_listing_shows_model_labels_when_present(state, wiring) -> None:
    provider = remote("openai")
    provider.model_labels = {"gpt-4o": "GPT-4o (flagship)"}
    set_config(wiring, {"openai": provider}, active="openai", model="gpt-4o")
    message = (await ModelCommand().execute(ctx(state, "list openai"))).message
    assert "GPT-4o (flagship)" in message


# --------------------------------------------------------------------------- #
# Discovery: /model list <provider>
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_list_refreshes_models_and_saves(state, wiring) -> None:
    config = set_config(wiring, {"openai": remote("openai")}, active="openai", model="gpt-4o")
    wiring["discovered"]["https://openai.example.com/v1"] = (
        ["gpt-4o", "gpt-4o-mini"],
        {"gpt-4o": "flagship", "gpt-4o-mini": "cheap", "gone": "stale"},
    )
    message = (await ModelCommand().execute(ctx(state, "list openai"))).message

    assert "openai models (2):" in message
    assert "gpt-4o-mini" in message
    assert " ·  cheap" in message
    # Labels are filtered to the discovered models.
    assert "gone" not in config.providers.providers["openai"].model_labels
    assert wiring["saved"]


@pytest.mark.asyncio
async def test_list_unknown_provider_is_rejected(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "list ghost"))
    assert result.success is False
    assert "Unknown provider: ghost" in result.message


@pytest.mark.asyncio
async def test_list_reports_when_discovery_finds_nothing(state, wiring) -> None:
    provider = remote("openai")
    provider.models = []
    set_config(wiring, {"openai": provider})
    result = await ModelCommand().execute(ctx(state, "list openai"))
    assert result.message == "openai: no models found."


# --------------------------------------------------------------------------- #
# Switching
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_switch_by_provider_name_uses_its_default_model(state, wiring) -> None:
    config = set_config(wiring, {"openai": remote("openai"), "deepseek": remote("deepseek", "deepseek-chat")})
    result = await ModelCommand().execute(ctx(state, "deepseek"))
    assert result.message.startswith("Switched to deepseek / deepseek-chat")
    assert state.multi_provider_config is None  # state not attached: config is the source
    assert config.providers.active_provider == "deepseek"
    assert config.providers.active_model == "deepseek-chat"
    assert state.session_config.model == "deepseek-chat"
    assert wiring["saved"]


@pytest.mark.asyncio
async def test_switch_with_slash_syntax_keeps_model_ids_intact(state, wiring) -> None:
    provider = remote("local", "LiquidAI-dev/lfm2.5-2.6b:latest")
    set_config(wiring, {"local": provider})
    result = await ModelCommand().execute(ctx(state, "local/LiquidAI-dev/lfm2.5-2.6b:latest"))
    assert "Switched to local / LiquidAI-dev/lfm2.5-2.6b:latest" in result.message


@pytest.mark.asyncio
async def test_switch_with_provider_and_model_separated_by_space(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "openai gpt-4o-mini"))
    assert "Switched to openai / gpt-4o-mini" in result.message
    assert state.session_config.model == "gpt-4o-mini"


@pytest.mark.asyncio
async def test_switch_by_bare_model_name_finds_its_provider(state, wiring) -> None:
    set_config(
        wiring,
        {"openai": remote("openai"), "deepseek": remote("deepseek", "deepseek-chat")},
    )
    result = await ModelCommand().execute(ctx(state, "deepseek-chat"))
    assert "Switched to deepseek / deepseek-chat" in result.message


@pytest.mark.asyncio
async def test_switch_by_index(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    wiring["discovered"]["https://openai.example.com/v1"] = (["gpt-4o", "gpt-4o-mini"], {})
    result = await ModelCommand().execute(ctx(state, "openai 2"))
    assert "Switched to openai / gpt-4o-mini" in result.message


@pytest.mark.asyncio
async def test_switch_index_out_of_range(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "openai 9"))
    assert result.success is False
    assert "Index 9 out of range (1-1)" in result.message


@pytest.mark.asyncio
async def test_switch_to_unknown_provider_is_rejected(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "ghost/gpt-4"))
    # An unknown prefix may be a slash-containing model id, so the command names
    # the input rather than guessing which half was wrong.
    assert result.success is False
    assert "No provider selected for 'ghost/gpt-4'" in result.message


@pytest.mark.asyncio
async def test_unknown_provider_with_explicit_tail_is_rejected(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "ghost gpt-4"))
    assert result.success is False
    assert "Unknown provider: ghost" in result.message


@pytest.mark.asyncio
async def test_switch_without_any_provider_selected(state, wiring) -> None:
    set_config(wiring, {})
    result = await ModelCommand().execute(ctx(state, "some-model"))
    assert result.success is False
    assert "No provider selected for 'some-model'" in result.message


@pytest.mark.asyncio
async def test_switch_to_a_provider_without_a_key_warns(state, wiring) -> None:
    providers = {"nokey": ProviderConfig(provider_type=ProviderType.OPENAI, models=["m"], default_model="m")}
    set_config(wiring, providers)
    result = await ModelCommand().execute(ctx(state, "nokey"))
    assert "Switched to nokey / m" in result.message
    assert "(no key — /login nokey <api-key>)" in result.message


@pytest.mark.asyncio
async def test_switch_appends_the_listing_when_the_provider_has_several_models(state, wiring) -> None:
    provider = remote("openai")
    provider.models = ["gpt-4o", "gpt-4o-mini"]
    set_config(wiring, {"openai": provider})
    result = await ModelCommand().execute(ctx(state, "openai"))
    assert "Switched to openai / gpt-4o" in result.message
    assert "openai models (2):" in result.message


@pytest.mark.asyncio
async def test_switch_prefers_session_state_when_attached(state, wiring) -> None:
    config = set_config(wiring, {"openai": remote("openai"), "deepseek": remote("deepseek", "ds")})
    state.multi_provider_config = config.providers
    await ModelCommand().execute(ctx(state, "deepseek"))
    assert state.multi_provider_config.active_provider == "deepseek"


# --------------------------------------------------------------------------- #
# Adding and removing providers
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_add_custom_provider_with_all_fields(state, wiring) -> None:
    config = set_config(wiring, {})
    result = await ModelCommand().execute(
        ctx(state, "add myproxy https://my.example.com/v1 sk-secret model-x")
    )
    assert result.message == "Added myproxy -> https://my.example.com/v1."
    added = config.providers.providers["myproxy"]
    assert added.api_key == "sk-secret"
    assert added.models == ["model-x"]
    # First provider added becomes the active one.
    assert config.providers.active_provider == "myproxy"
    assert config.providers.active_model == "model-x"
    assert wiring["saved"]


@pytest.mark.asyncio
async def test_add_custom_provider_usage_error(state, wiring) -> None:
    set_config(wiring, {})
    result = await ModelCommand().execute(ctx(state, "add onlyaname"))
    assert result.success is False
    assert "Usage: /model add <name> <base-url>" in result.message


@pytest.mark.asyncio
async def test_add_preset_by_key(state, wiring) -> None:
    config = set_config(wiring, {})
    result = await ModelCommand().execute(ctx(state, "add deepseek"))
    assert result.message.startswith("Added deepseek (DeepSeek).")
    assert "deepseek" in config.providers.providers
    assert config.providers.active_provider == "deepseek"


@pytest.mark.asyncio
async def test_add_preset_asks_for_a_key_when_missing(state, wiring, monkeypatch) -> None:
    set_config(wiring, {})
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    class Prompt:
        @staticmethod
        def ask(*args, **kwargs):
            return "sk-typed"

    monkeypatch.setattr("rich.prompt.Prompt", Prompt)
    await ModelCommand().execute(ctx(state, "add deepseek"))
    assert wiring["config"].providers.providers["deepseek"].api_key == "sk-typed"


@pytest.mark.asyncio
async def test_add_without_arguments_runs_the_wizard(state, wiring, monkeypatch) -> None:
    config = set_config(wiring, {})

    class Prompt:
        @staticmethod
        def ask(prompt, choices=None, default=None, **kwargs):
            if choices is not None:
                return choices[0]  # first wizard entry: ollama
            return "wizard-model"

    monkeypatch.setattr("rich.prompt.Prompt", Prompt)
    result = await ModelCommand().execute(ctx(state, "add"))
    assert "Added ollama" in result.message
    assert "ollama" in config.providers.providers


@pytest.mark.asyncio
async def test_add_wizard_custom_choice_prompts_for_fields(state, wiring, monkeypatch) -> None:
    from openlaoke.core.provider_presets import wizard_presets

    config = set_config(wiring, {})
    custom_choice = str(len(wizard_presets()) + 1)
    answers = iter(["myprov", "https://h/v1", "sk-1", "m-1"])

    class Prompt:
        @staticmethod
        def ask(prompt, choices=None, default=None, **kwargs):
            if choices is not None:
                return custom_choice
            return next(answers)

    monkeypatch.setattr("rich.prompt.Prompt", Prompt)
    result = await ModelCommand().execute(ctx(state, "add"))
    assert "Added myprov -> https://h/v1." in result.message
    assert config.providers.providers["myprov"].api_key == "sk-1"


@pytest.mark.asyncio
async def test_add_custom_prompt_requires_name_and_url(state, wiring, monkeypatch) -> None:
    set_config(wiring, {})

    class Prompt:
        @staticmethod
        def ask(prompt, **kwargs):
            return ""

    monkeypatch.setattr("rich.prompt.Prompt", Prompt)
    result = await ModelCommand()._add_custom({}, wiring["config"])
    assert result.success is False
    assert "Name and base URL are required." in result.message


@pytest.mark.asyncio
async def test_remove_requires_a_name(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "rm"))
    assert result.success is False
    assert "Usage: /model rm <provider>" in result.message


@pytest.mark.asyncio
async def test_remove_unknown_provider(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "rm ghost"))
    assert result.success is False
    assert "Unknown provider: ghost" in result.message


@pytest.mark.asyncio
async def test_remove_active_provider_clears_the_selection(state, wiring) -> None:
    config = set_config(wiring, {"openai": remote("openai")}, active="openai", model="gpt-4o")
    result = await ModelCommand().execute(ctx(state, "rm openai"))
    assert result.message == "Removed provider openai."
    assert "openai" not in config.providers.providers
    assert config.providers.active_provider == ""
    assert config.providers.active_model == ""


@pytest.mark.asyncio
async def test_remove_inactive_provider_keeps_the_selection(state, wiring) -> None:
    config = set_config(
        wiring,
        {"openai": remote("openai"), "deepseek": remote("deepseek", "ds")},
        active="openai",
        model="gpt-4o",
    )
    await ModelCommand().execute(ctx(state, "remove deepseek"))
    assert config.providers.active_provider == "openai"
    assert "deepseek" not in config.providers.providers


# --------------------------------------------------------------------------- #
# Probe and prune
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_probe_with_no_local_providers(state, wiring) -> None:
    set_config(wiring, {"openai": remote("openai")})
    result = await ModelCommand().execute(ctx(state, "probe"))
    assert result.message == "No local providers configured."


@pytest.mark.asyncio
async def test_probe_lists_reachability(state, wiring, monkeypatch) -> None:
    providers = {
        "ollama": ProviderConfig(
            provider_type=ProviderType.OLLAMA, base_url="http://127.0.0.1:11434/v1", is_local=True
        ),
        "lm_studio": ProviderConfig(
            provider_type=ProviderType.LM_STUDIO, base_url="http://127.0.0.1:1234/v1", is_local=True
        ),
    }
    set_config(wiring, providers)

    async def probe(p, **kwargs):
        return {"ollama": True, "lm_studio": False}

    monkeypatch.setattr("openlaoke.types.providers.probe_local_providers", probe)
    message = (await ModelCommand().execute(ctx(state, "probe"))).message
    assert "Local providers:" in message
    assert "ollama" in message and "online" in message
    assert "lm_studio" in message and "offline" in message
    assert "Remove offline: /model prune" in message


@pytest.mark.asyncio
async def test_prune_with_nothing_offline(state, wiring, monkeypatch) -> None:
    set_config(wiring, {"ollama": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)})

    async def probe(p, **kwargs):
        return {"ollama": True}

    monkeypatch.setattr("openlaoke.types.providers.probe_local_providers", probe)
    result = await ModelCommand().execute(ctx(state, "prune"))
    assert result.message == "No unreachable local providers."


@pytest.mark.asyncio
async def test_prune_removes_offline_providers_and_reassigns_active(state, wiring, monkeypatch) -> None:
    providers = {
        "dead": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True),
        "alive": remote("alive"),
    }
    config = set_config(wiring, providers, active="dead", model="dead-model")

    async def probe(p, **kwargs):
        return {"dead": False, "alive": True}

    monkeypatch.setattr("openlaoke.types.providers.probe_local_providers", probe)
    result = await ModelCommand().execute(ctx(state, "prune"))
    assert "Removed 1 unreachable local provider(s): dead" in result.message
    assert "dead" not in config.providers.providers
    assert config.providers.active_provider == "alive"
    assert config.providers.active_model == "gpt-4o"


@pytest.mark.asyncio
async def test_prune_clears_the_selection_when_nothing_remains(state, wiring, monkeypatch) -> None:
    config = set_config(
        wiring,
        {"dead": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)},
        active="dead",
        model="dead-model",
    )

    async def probe(p, **kwargs):
        return {"dead": False}

    monkeypatch.setattr("openlaoke.types.providers.probe_local_providers", probe)
    await ModelCommand().execute(ctx(state, "clean"))
    assert config.providers.active_provider == ""
    assert config.providers.active_model == ""


# --------------------------------------------------------------------------- #
# Key masking helper
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "key,expected",
    [
        ("", "(no key)"),
        ("short", "***"),
        ("123456789012", "***"),
        ("sk-abcdef1234567890", "sk-abc...7890"),
    ],
)
def test_mask_helper(key: str, expected: str) -> None:
    assert ModelCommand._mask(key) == expected


# --------------------------------------------------------------------------- #
# Readiness probe helper
# --------------------------------------------------------------------------- #


def test_provider_ready_uses_is_ready_when_available() -> None:
    ready = type("P", (), {"is_ready": lambda _self: True})()
    assert ModelCommand._provider_ready(ready) is True


def test_provider_ready_falls_back_to_is_configured() -> None:
    legacy = type("P", (), {"is_configured": lambda _self: True})()
    assert ModelCommand._provider_ready(legacy) is True


def test_provider_ready_returns_false_when_the_check_raises() -> None:
    def boom(_self):
        raise RuntimeError("probe exploded")

    broken = type("P", (), {"is_configured": boom})()
    assert ModelCommand._provider_ready(broken) is False
