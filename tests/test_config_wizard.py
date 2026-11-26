"""Tests for the first-run configuration wizard and its helpers.

The wizard is nothing but a sequence of prompts, so the tests script the answers
by replacing ``Prompt.ask`` / ``Confirm.ask`` and then check the config it hands
back. That is the same code path a first-time user goes through.
"""

from __future__ import annotations

import io
import os
from typing import Any

import pytest

from openlaoke.core import config_wizard as wizard
from openlaoke.core.config_wizard import (
    _check_provider_ready,
    _configure_provider,
    _configure_proxy,
    _get_env_var_name,
    _get_provider_status,
    _get_proxy_display,
    _select_model_from_list,
    get_proxy_url,
    quick_setup,
    run_config_wizard,
    show_current_config,
)
from openlaoke.types.providers import ProviderConfig, ProviderType
from openlaoke.utils.config import AppConfig


@pytest.fixture(autouse=True)
def quiet_console(monkeypatch):
    """Silence rich output and drop any proxy the host happens to export."""
    monkeypatch.setattr(wizard, "console", wizard.Console(file=io.StringIO()))
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
        monkeypatch.delenv(name, raising=False)


def script(monkeypatch, answers: dict[str, str], confirms: dict[str, bool] | None = None) -> None:
    """Answer prompts by question text, recording which ones were asked."""

    def fake_ask(question: str, **kwargs: Any) -> str:
        for fragment, answer in answers.items():
            if fragment.lower() in question.lower():
                return answer
        raise AssertionError(f"unscripted prompt: {question!r}")

    def fake_confirm(question: str, **kwargs: Any) -> bool:
        for fragment, answer in (confirms or {}).items():
            if fragment.lower() in question.lower():
                return answer
        raise AssertionError(f"unscripted confirmation: {question!r}")

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(fake_confirm))


def provider(
    provider_type: ProviderType,
    *,
    api_key: str = "",
    base_url: str = "https://api.example.com/v1",
    models: list[str] | None = None,
    default: str = "",
    is_local: bool = False,
) -> ProviderConfig:
    return ProviderConfig(
        provider_type=provider_type,
        api_key=api_key,
        base_url=base_url,
        default_model=default,
        models=models if models is not None else ["m1", "m2"],
        is_local=is_local,
    )


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "mode,url,expected",
    [
        ("none", "", "disabled"),
        ("system", "", "use system proxy"),
        ("custom", "http://127.0.0.1:7890", "http://127.0.0.1:7890"),
        ("custom", "", "(not set)"),
        ("something", "", "unknown"),
    ],
)
def test_proxy_display(mode: str, url: str, expected: str) -> None:
    config = AppConfig()
    config.proxy_mode = mode
    config.proxy_url = url
    assert _get_proxy_display(config) == expected


@pytest.mark.parametrize(
    "mode,env,expected",
    [
        ("none", {"HTTP_PROXY": "http://proxy:1"}, None),
        ("system", {}, None),
        ("system", {"HTTP_PROXY": "http://proxy:1"}, "http://proxy:1"),
        ("system", {"HTTPS_PROXY": "http://proxy:2"}, "http://proxy:2"),
        ("custom", {}, None),
        ("custom", {}, None),
    ],
)
def test_effective_proxy_url(
    mode: str, env: dict[str, str], expected: str | None, monkeypatch
) -> None:
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    config = AppConfig()
    config.proxy_mode = mode
    config.proxy_url = "http://custom:3" if mode == "custom" else ""

    result = get_proxy_url(config)

    assert result == (expected or ("http://custom:3" if mode == "custom" else None))


def test_custom_proxy_url_is_returned() -> None:
    config = AppConfig()
    config.proxy_mode = "custom"
    config.proxy_url = "http://127.0.0.1:7897"
    assert get_proxy_url(config) == "http://127.0.0.1:7897"


@pytest.mark.parametrize(
    "provider_type,expected",
    [
        (ProviderType.ANTHROPIC, "ANTHROPIC_API_KEY"),
        (ProviderType.OPENAI, "OPENAI_API_KEY"),
        (ProviderType.GROQ, "GROQ_API_KEY"),
        (ProviderType.GITHUB_COPILOT, "GITHUB_TOKEN"),
        (ProviderType.OPENCODE, "OPENCODE_API_KEY"),
        (ProviderType.OPENAI_COMPATIBLE, "OPENAI_API_KEY"),
        (ProviderType.OLLAMA, ""),
    ],
)
def test_env_var_names(provider_type: ProviderType, expected: str) -> None:
    assert _get_env_var_name(provider_type) == expected


def test_provider_status_labels(monkeypatch) -> None:
    assert "local" in _get_provider_status(provider(ProviderType.OLLAMA, is_local=True))
    assert "FREE" in _get_provider_status(provider(ProviderType.OPENCODE))
    assert "stored" in _get_provider_status(provider(ProviderType.OPENAI, api_key="sk-1"))

    monkeypatch.setenv("GROQ_API_KEY", "gsk")
    assert "env var" in _get_provider_status(provider(ProviderType.GROQ))

    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert "needs setup" in _get_provider_status(provider(ProviderType.GROQ))


def test_provider_ready_check() -> None:
    from openlaoke.types.providers import MultiProviderConfig

    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI, api_key="sk-1")},
        active_provider="main",
    )

    assert _check_provider_ready(config, "main") is True
    assert _check_provider_ready(config, "absent") is False

    config.providers["main"].api_key = ""
    assert _check_provider_ready(config, "main") is False


# --------------------------------------------------------------------------- #
# _select_model_from_list
# --------------------------------------------------------------------------- #


def test_model_selection_returns_the_default_when_there_are_no_models() -> None:
    assert _select_model_from_list([], "keep-me") == "keep-me"


def test_a_single_model_is_used_without_asking(monkeypatch) -> None:
    def boom(*args: Any, **kwargs: Any) -> str:
        raise AssertionError("should not prompt for a single model")

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(boom))
    assert _select_model_from_list(["solo"], "other") == "solo"


def test_model_selection_honours_the_numbered_choice(monkeypatch) -> None:
    script(monkeypatch, {"Select model": "2"})
    assert _select_model_from_list(["m1", "m2", "m3"], "m1") == "m2"


def test_a_preferred_default_is_preselected(monkeypatch) -> None:
    seen: dict[str, Any] = {}

    def fake_ask(question: str, **kwargs: Any) -> str:
        seen["default"] = kwargs.get("default")
        return kwargs["default"]

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    chosen = _select_model_from_list(["gpt-4o", "gpt-4o-mini"], "gpt-4o-mini")

    assert seen["default"] == "1"
    assert chosen == "gpt-4o"


# --------------------------------------------------------------------------- #
# _configure_proxy
# --------------------------------------------------------------------------- #


def test_proxy_can_be_disabled(monkeypatch) -> None:
    script(monkeypatch, {"Select proxy mode": "1"})
    config = _configure_proxy(AppConfig())

    assert config.proxy_mode == "none"
    assert config.proxy_url == ""


def test_system_proxy_mode(monkeypatch) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://corp:8080")
    script(monkeypatch, {"Select proxy mode": "2"})
    config = _configure_proxy(AppConfig())

    assert config.proxy_mode == "system"
    assert config.proxy_url == ""


def test_custom_proxy_mode(monkeypatch) -> None:
    script(monkeypatch, {"Select proxy mode": "3", "proxy URL": "socks5://127.0.0.1:7897"})
    config = _configure_proxy(AppConfig())

    assert config.proxy_mode == "custom"
    assert config.proxy_url == "socks5://127.0.0.1:7897"


# --------------------------------------------------------------------------- #
# _configure_provider
# --------------------------------------------------------------------------- #


def test_an_unknown_provider_key_is_returned_untouched() -> None:
    from openlaoke.types.providers import MultiProviderConfig

    config = MultiProviderConfig()
    assert _configure_provider(config, "ghost").providers == {}


def test_a_stored_key_is_reused_without_asking_for_the_key_again(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    answers = iter(["1"])
    monkeypatch.setattr(
        wizard.Prompt,
        "ask",
        staticmethod(lambda question, **kwargs: kwargs.get("default", next(answers))),
    )
    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI, api_key="sk-stored")},
        active_provider="main",
    )

    result = _configure_provider(config, "main")

    assert result.providers["main"].api_key == "sk-stored"
    assert result.providers["main"].default_model == ""


def test_a_stored_key_offers_a_reconfigure_option(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "configuration source": "2",
            "API Key": "sk-new",
            "API Base URL": "https://api.example.com/v1",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI, api_key="sk-old")}, active_provider="main"
    )

    result = _configure_provider(config, "main")

    assert result.providers["main"].api_key == "sk-new"


def test_an_environment_key_can_be_used(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
    script(
        monkeypatch,
        {"configuration source": "1", "API Base URL": "https://x/v1", "Select model": "1"},
    )
    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI)}, active_provider="main"
    )

    result = _configure_provider(config, "main")

    assert result.providers["main"].api_key == "sk-from-env"


def test_a_local_provider_asks_for_the_url_and_uses_detected_models(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {"API URL": "http://localhost:11434/v1", "Select model": "2"})
    monkeypatch.setattr(
        MultiProviderConfig,
        "_detect_ollama_models",
        staticmethod(lambda base: ["a", "b"]),
    )
    config = MultiProviderConfig(
        providers={"ollama": provider(ProviderType.OLLAMA, is_local=True, models=[], base_url="")},
        active_provider="ollama",
    )

    result = _configure_provider(config, "ollama")

    assert result.providers["ollama"].base_url == "http://localhost:11434/v1"
    assert result.providers["ollama"].default_model == "b"
    assert result.providers["ollama"].enabled is True


def test_a_local_provider_without_detectable_models_falls_back(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {"API URL": "http://localhost:11434/v1", "Select model": "1"})
    monkeypatch.setattr(MultiProviderConfig, "_detect_ollama_models", staticmethod(lambda base: []))
    config = MultiProviderConfig(
        providers={
            "ollama": provider(ProviderType.OLLAMA, is_local=True, models=["fallback"], base_url="")
        },
        active_provider="ollama",
    )

    result = _configure_provider(config, "ollama")

    assert result.providers["ollama"].default_model == "fallback"


def test_a_custom_endpoint_keeps_a_configured_default_model(monkeypatch) -> None:
    """A base URL and model already in the config must survive Enter.

    Regression: `default_model or models[0] if models else "default"` parses as
    `(default_model or models[0]) if models else "default"`, so an empty model list
    replaced the configured model with the literal string "default".
    """
    from openlaoke.types.providers import MultiProviderConfig

    seen: dict[str, Any] = {}

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Model name" in question:
            seen["default"] = kwargs.get("default")
            return kwargs["default"]
        if "API Base URL" in question:
            return kwargs["default"]
        if "API Key" in question:
            return "sk-custom"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    config = MultiProviderConfig(
        providers={
            "mine": provider(
                ProviderType.OPENAI_COMPATIBLE, models=[], default="my-model", base_url=""
            )
        },
        active_provider="mine",
    )

    result = _configure_provider(config, "mine")

    assert seen["default"] == "my-model"
    assert result.providers["mine"].default_model == "my-model"


def test_a_custom_endpoint_falls_back_to_the_first_model(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "API Base URL": "http://localhost:8000/v1",
            "API Key": "sk-custom",
            "Model name": "chosen",
        },
    )
    config = MultiProviderConfig(
        providers={"mine": provider(ProviderType.OPENAI_COMPATIBLE, models=[], base_url="")},
        active_provider="mine",
    )

    result = _configure_provider(config, "mine")

    assert result.providers["mine"].default_model == "chosen"


def test_opencode_needs_no_key_and_picks_a_model(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {"Select model": "2"})
    config = MultiProviderConfig(
        providers={"opencode": provider(ProviderType.OPENCODE, models=["free-a", "free-b"])},
        active_provider="opencode",
    )

    result = _configure_provider(config, "opencode")

    assert result.providers["opencode"].default_model == "free-b"
    assert result.providers["opencode"].enabled is True


def test_minimax_asks_for_the_key_and_the_url(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "MiniMax API Key": "mm-key",
            "API Base URL": "https://api.minimaxi.com/v1",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"minimax": provider(ProviderType.MINIMAX)}, active_provider="minimax"
    )

    result = _configure_provider(config, "minimax")

    assert result.providers["minimax"].api_key == "mm-key"
    assert result.providers["minimax"].base_url == "https://api.minimaxi.com/v1"


def test_azure_uses_the_endpoint_from_the_environment(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://res.openai.azure.com")
    script(
        monkeypatch,
        {"Azure OpenAI API Key": "az-key", "Select model": "1"},
        confirms={"Use this endpoint": True},
    )
    config = MultiProviderConfig(
        providers={"azure": provider(ProviderType.AZURE_OPENAI, base_url="", models=["dep"])},
        active_provider="azure",
    )

    result = _configure_provider(config, "azure")

    assert result.providers["azure"].base_url == "https://res.openai.azure.com"
    assert result.providers["azure"].api_key == "az-key"


def test_azure_asks_for_the_endpoint_when_the_environment_has_none(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    script(
        monkeypatch,
        {
            "Azure OpenAI Endpoint": "https://typed.openai.azure.com",
            "Azure OpenAI API Key": "az-key",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"azure": provider(ProviderType.AZURE_OPENAI, base_url="", models=["dep"])},
        active_provider="azure",
    )

    result = _configure_provider(config, "azure")

    assert result.providers["azure"].base_url == "https://typed.openai.azure.com"


def test_vertex_asks_for_project_and_location_when_unset(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.delenv("GOOGLE_VERTEX_PROJECT", raising=False)
    monkeypatch.delenv("GOOGLE_VERTEX_LOCATION", raising=False)
    script(
        monkeypatch,
        {"GCP Project ID": "proj-1", "GCP Location": "europe-west4", "Select model": "1"},
    )
    config = MultiProviderConfig(
        providers={"vertex": provider(ProviderType.GOOGLE_VERTEX)}, active_provider="vertex"
    )

    _configure_provider(config, "vertex")

    assert os.environ["GOOGLE_VERTEX_PROJECT"] == "proj-1"
    assert os.environ["GOOGLE_VERTEX_LOCATION"] == "europe-west4"


def test_bedrock_asks_for_the_region_when_unset(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.delenv("AWS_REGION", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    script(monkeypatch, {"AWS Region": "eu-west-1", "Select model": "1"})
    config = MultiProviderConfig(
        providers={"bedrock": provider(ProviderType.AWS_BEDROCK)}, active_provider="bedrock"
    )

    _configure_provider(config, "bedrock")

    assert os.environ["AWS_REGION"] == "eu-west-1"


def test_a_generic_provider_asks_for_key_url_and_model(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "Enter your deepseek API Key": "ds-key",
            "API Base URL": "https://api.deepseek.com/v1",
            "Select model": "2",
        },
    )
    config = MultiProviderConfig(
        providers={
            "deepseek": provider(ProviderType.DEEPSEEK, base_url="", models=["chat", "reasoner"])
        },
        active_provider="deepseek",
    )

    result = _configure_provider(config, "deepseek")

    assert result.providers["deepseek"].api_key == "ds-key"
    assert result.providers["deepseek"].default_model == "reasoner"


# --------------------------------------------------------------------------- #
# run_config_wizard end to end
# --------------------------------------------------------------------------- #


def test_wizard_records_the_language_and_skips_provider_setup(monkeypatch) -> None:
    from openlaoke.core.i18n import SUPPORTED_LANGUAGES

    codes = list(SUPPORTED_LANGUAGES)
    script(monkeypatch, {"Select language": str(codes.index("zh") + 1)}, confirms={})
    skip = __import__("openlaoke.core.provider_presets", fromlist=["wizard_presets"])

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return str(codes.index("zh") + 1)
        if "Select provider" in question:
            return str(len(skip.wizard_presets()) + 2)  # the "Skip" row
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))

    config = run_config_wizard(AppConfig())

    assert config.language == "zh"
    assert config.first_run is False


def test_wizard_configures_a_preset_provider_and_its_proxy(monkeypatch) -> None:
    from openlaoke.core.provider_presets import wizard_presets

    presets = wizard_presets()
    target = next(preset for preset in presets if not preset.is_local)
    index = presets.index(target) + 1

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(index)
        if "configuration source" in question:
            return kwargs["choices"][-1]  # Reconfigure
        if "API Key" in question:
            return "sk-wizard"
        if "API Base URL" in question:
            return kwargs.get("default") or "https://api.example.com/v1"
        if "Select model" in question:
            return "1"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    config = run_config_wizard(AppConfig())

    assert config.providers.active_provider == target.key
    assert config.providers.providers[target.key].api_key == "sk-wizard"
    assert config.proxy_mode == "none"
    assert config.first_run is False


# --------------------------------------------------------------------------- #
# show_current_config / quick_setup
# --------------------------------------------------------------------------- #


def test_show_current_config_runs(capsys) -> None:
    config = AppConfig()
    show_current_config(config)


def test_quick_setup_configures_a_known_provider() -> None:
    config = quick_setup("openai", "sk-quick", model="gpt-4o-mini")

    assert config.providers.active_provider == "openai"
    assert config.providers.providers["openai"].api_key == "sk-quick"
    assert config.providers.providers["openai"].default_model == "gpt-4o-mini"
    assert config.first_run is False


def test_quick_setup_rejects_an_unknown_provider() -> None:
    with pytest.raises(KeyError, match="Unknown provider"):
        quick_setup("no-such-provider", "sk-quick")


# --------------------------------------------------------------------------- #
# The per-provider branches that share one shape
# --------------------------------------------------------------------------- #

KEY_PROMPT_TYPES = [
    ("xai", ProviderType.XAI, "xAI API Key"),
    ("mistral", ProviderType.MISTRAL, "Mistral API Key"),
    ("groq", ProviderType.GROQ, "Groq API Key"),
    ("cerebras", ProviderType.CEREBRAS, "Cerebras API Key"),
    ("cohere", ProviderType.COHERE, "Cohere API Key"),
    ("deepinfra", ProviderType.DEEPINFRA, "DeepInfra API Key"),
    ("togetherai", ProviderType.TOGETHERAI, "Together AI API Key"),
    ("perplexity", ProviderType.PERPLEXITY, "Perplexity API Key"),
    ("openrouter", ProviderType.OPENROUTER, "OpenRouter API Key"),
    ("github_copilot", ProviderType.GITHUB_COPILOT, "GitHub Personal Access Token"),
    ("google", ProviderType.GOOGLE, "Google AI API Key"),
]


@pytest.mark.parametrize("name,provider_type,prompt_text", KEY_PROMPT_TYPES)
def test_simple_api_key_providers(
    name: str, provider_type: ProviderType, prompt_text: str, monkeypatch
) -> None:
    """Each of these branches is just: ask for the key, then pick a model."""
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {prompt_text: f"{name}-key", "Select model": "2"})
    config = MultiProviderConfig(
        providers={name: provider(provider_type, api_key="")}, active_provider=name
    )

    result = _configure_provider(config, name)

    assert result.providers[name].api_key == f"{name}-key"
    assert result.providers[name].default_model == "m2"
    assert result.providers[name].enabled is True


@pytest.mark.parametrize("name,provider_type,prompt_text", KEY_PROMPT_TYPES)
def test_simple_api_key_providers_keep_an_existing_key(
    name: str, provider_type: ProviderType, prompt_text: str, monkeypatch
) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {"configuration source": "1"})
    config = MultiProviderConfig(
        providers={name: provider(provider_type, api_key="kept")}, active_provider=name
    )

    result = _configure_provider(config, name)

    assert result.providers[name].api_key == "kept"


def test_anthropic_asks_for_its_own_base_url(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "Anthropic API Key": "sk-ant",
            "API Base URL": "https://proxy.internal/anthropic",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"anthropic": provider(ProviderType.ANTHROPIC, base_url="https://x")},
        active_provider="anthropic",
    )

    result = _configure_provider(config, "anthropic")

    assert result.providers["anthropic"].base_url == "https://proxy.internal/anthropic"


def test_a_custom_endpoint_without_a_key_warns_but_continues(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "API Base URL": "http://localhost:8000/v1",
            "API Key": "",
            "Model name": "fallback-model",
        },
    )
    config = MultiProviderConfig(
        providers={"mine": provider(ProviderType.OPENAI_COMPATIBLE, models=[], base_url="")},
        active_provider="mine",
    )

    result = _configure_provider(config, "mine")

    assert result.providers["mine"].api_key == ""
    assert result.providers["mine"].default_model == "fallback-model"
    assert result.providers["mine"].enabled is True


def test_a_non_ollama_local_provider_skips_model_detection(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(monkeypatch, {"API URL": "http://localhost:1234/v1", "Select model": "1"})
    config = MultiProviderConfig(
        providers={
            "lm_studio": provider(
                ProviderType.LM_STUDIO, is_local=True, base_url="", models=["local-a"]
            )
        },
        active_provider="lm_studio",
    )

    result = _configure_provider(config, "lm_studio")

    assert result.providers["lm_studio"].base_url == "http://localhost:1234/v1"
    assert result.providers["lm_studio"].default_model == "local-a"


def test_vertex_reads_the_environment_and_bedrock_warns_about_credentials(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("GOOGLE_VERTEX_PROJECT", "proj-2")
    monkeypatch.setenv("GOOGLE_VERTEX_LOCATION", "us-east1")
    monkeypatch.setenv("AWS_REGION", "us-west-2")
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    script(monkeypatch, {"Select model": "1"})
    config = MultiProviderConfig(
        providers={
            "vertex": provider(ProviderType.GOOGLE_VERTEX),
            "bedrock": provider(ProviderType.AWS_BEDROCK),
        },
        active_provider="vertex",
    )

    _configure_provider(config, "vertex")
    _configure_provider(config, "bedrock")

    assert config.providers["vertex"].enabled is True
    assert config.providers["bedrock"].enabled is True


def test_reconfigure_wins_over_both_stored_and_environment_keys(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    script(
        monkeypatch,
        {
            "configuration source": "3",
            "API Key": "sk-typed",
            "API Base URL": "https://api.example.com/v1",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI, api_key="sk-stored")},
        active_provider="main",
    )

    result = _configure_provider(config, "main")

    assert result.providers["main"].api_key == "sk-typed"


def test_the_environment_option_is_second_when_a_key_is_stored(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("OPENAI_API_KEY", "sk-env")
    script(
        monkeypatch,
        {
            "configuration source": "2",
            "API Base URL": "https://api.example.com/v1",
            "Select model": "1",
        },
    )
    config = MultiProviderConfig(
        providers={"main": provider(ProviderType.OPENAI, api_key="sk-stored")},
        active_provider="main",
    )

    result = _configure_provider(config, "main")

    assert result.providers["main"].api_key == "sk-env"


def test_proxy_system_mode_without_any_detected_proxy(monkeypatch) -> None:
    script(monkeypatch, {"Select proxy mode": "2"})
    config = _configure_proxy(AppConfig())

    assert config.proxy_mode == "system"


def test_unknown_proxy_mode_yields_no_url() -> None:
    config = AppConfig()
    config.proxy_mode = "mystery"
    assert get_proxy_url(config) is None


# --------------------------------------------------------------------------- #
# run_config_wizard: the remaining rows of the provider table
# --------------------------------------------------------------------------- #


def test_wizard_can_configure_a_custom_endpoint(monkeypatch) -> None:
    from openlaoke.core.provider_presets import wizard_presets

    custom_opt = len(wizard_presets()) + 1

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(custom_opt)
        if "API Base URL" in question:
            return "http://127.0.0.1:8088/v1"
        if "API Key" in question:
            return "sk-local"
        if "Model name" in question:
            return "lfm3"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    config = run_config_wizard(AppConfig())

    custom = config.providers.providers["openai_compatible"]
    assert custom.base_url == "http://127.0.0.1:8088/v1"
    assert custom.default_model == "lfm3"
    assert config.providers.active_provider == "openai_compatible"


def test_wizard_reuses_a_preset_already_in_the_config(monkeypatch) -> None:
    """Choosing a provider that is already configured must not rebuild it."""
    from openlaoke.core.provider_presets import wizard_presets

    presets = wizard_presets()
    target = next(preset for preset in presets if preset.key == "openai")
    config = AppConfig()
    config.providers.providers["openai"] = provider(
        ProviderType.OPENAI, api_key="sk-existing", default="gpt-4o"
    )

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(presets.index(target) + 1)
        if "configuration source" in question:
            return "1"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    result = run_config_wizard(config)

    assert result.providers.providers["openai"].api_key == "sk-existing"
    assert result.providers.active_provider == "openai"


def test_wizard_lets_the_user_bail_out_of_a_failed_setup(monkeypatch) -> None:
    from openlaoke.core.provider_presets import wizard_presets

    presets = wizard_presets()
    target = next(preset for preset in presets if preset.key == "openai")

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(presets.index(target) + 1)
        if "configuration source" in question:
            return kwargs["choices"][-1]  # Reconfigure
        if "API Key" in question:
            return "sk-x"
        if "API Base URL" in question:
            return "https://api.example.com/v1"
        if "Select model" in question:
            return "1"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    # Never accept the provider as ready, then decline to continue.
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: False))
    monkeypatch.setattr(wizard, "_check_provider_ready", lambda config, key: False)

    config = run_config_wizard(AppConfig())

    assert config.providers.active_provider != "openai"


def test_aliyun_coding_plan_asks_for_key_and_url(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    script(
        monkeypatch,
        {
            "Aliyun Coding Plan API Key": "sk-sp-123",
            "API Base URL": "https://coding.dashscope.aliyuncs.com/v1",
            "Select model": "2",
        },
    )
    config = MultiProviderConfig(
        providers={"aliyun": provider(ProviderType.ALIYUN_CODING_PLAN, base_url="")},
        active_provider="aliyun",
    )

    result = _configure_provider(config, "aliyun")

    assert result.providers["aliyun"].api_key == "sk-sp-123"
    assert result.providers["aliyun"].base_url == "https://coding.dashscope.aliyuncs.com/v1"
    assert result.providers["aliyun"].default_model == "m2"


def test_bedrock_notes_credentials_found_in_the_environment(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA-test")
    monkeypatch.setenv("AWS_REGION", "us-east-1")
    script(monkeypatch, {"configuration source": "1", "Select model": "1"})
    config = MultiProviderConfig(
        providers={"bedrock": provider(ProviderType.AWS_BEDROCK)}, active_provider="bedrock"
    )

    _configure_provider(config, "bedrock")

    assert config.providers["bedrock"].enabled is True


def test_azure_declines_the_environment_endpoint_and_asks(monkeypatch) -> None:
    from openlaoke.types.providers import MultiProviderConfig

    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://env.openai.azure.com")
    script(
        monkeypatch,
        {
            "Azure OpenAI Endpoint": "https://typed.openai.azure.com",
            "Azure OpenAI API Key": "az-key",
            "Select model": "1",
        },
        confirms={"Use this endpoint": False},
    )
    config = MultiProviderConfig(
        providers={"azure": provider(ProviderType.AZURE_OPENAI, base_url="", models=["dep"])},
        active_provider="azure",
    )

    result = _configure_provider(config, "azure")

    assert result.providers["azure"].base_url == "https://typed.openai.azure.com"


def test_wizard_marks_a_local_preset_as_local_in_the_table(monkeypatch) -> None:
    """A local provider already in the config shows the 'local' badge, not 'needs key'."""
    from openlaoke.core.provider_presets import wizard_presets

    presets = wizard_presets()
    skip_opt = len(presets) + 2
    config = AppConfig()
    config.providers.providers["lm_studio"] = ProviderConfig(
        provider_type=ProviderType.LM_STUDIO,
        base_url="http://localhost:1234/v1",
        is_local=True,
        enabled=False,  # not ready yet, so the table must show the local badge
    )

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(skip_opt)
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))

    result = run_config_wizard(config)

    assert result.first_run is False


def test_wizard_keeps_an_existing_custom_provider_entry(monkeypatch) -> None:
    """Picking the custom row twice must not wipe the endpoint already stored."""
    from openlaoke.core.provider_presets import wizard_presets

    custom_opt = len(wizard_presets()) + 1
    config = AppConfig()
    config.providers.providers["openai_compatible"] = provider(
        ProviderType.OPENAI_COMPATIBLE, api_key="sk-kept", default="kept-model"
    )

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(custom_opt)
        if "configuration source" in question:
            return "1"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    result = run_config_wizard(config)

    assert result.providers.providers["openai_compatible"].api_key == "sk-kept"


def test_wizard_builds_a_preset_that_is_not_in_the_defaults(monkeypatch) -> None:
    """Provider presets added later are missing from a default config; picking one builds it."""
    from openlaoke.core.provider_presets import wizard_presets

    presets = wizard_presets()
    target = next(preset for preset in presets if preset.key == "cycleuser-llm")
    config = AppConfig()
    assert target.key not in config.providers.providers

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(presets.index(target) + 1)
        if "configuration source" in question:
            return kwargs["choices"][-1]
        if "API Key" in question:
            return "cu-key"
        if "API Base URL" in question:
            return kwargs.get("default") or target.base_url
        if "Model name" in question:
            return "cu-model"
        if "Select model" in question:
            return "1"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    result = run_config_wizard(config)

    built = result.providers.providers["cycleuser-llm"]
    assert built.base_url == target.base_url
    assert built.api_key == "cu-key"
    assert built.default_model == "cu-model"
    assert result.providers.active_provider == "cycleuser-llm"


def test_wizard_creates_the_custom_provider_entry_when_it_is_missing(monkeypatch) -> None:
    """A config saved by an older version may lack the custom provider row."""
    from openlaoke.core.provider_presets import wizard_presets

    custom_opt = len(wizard_presets()) + 1
    config = AppConfig()
    del config.providers.providers["openai_compatible"]

    def fake_ask(question: str, **kwargs: Any) -> str:
        if "Select language" in question:
            return kwargs.get("default", "1")
        if "Select provider" in question:
            return str(custom_opt)
        if "API Base URL" in question:
            return "http://localhost:8088/v1"
        if "API Key" in question:
            return "sk-new"
        if "Model name" in question:
            return "local-model"
        if "Select proxy mode" in question:
            return "1"
        raise AssertionError(question)

    monkeypatch.setattr(wizard.Prompt, "ask", staticmethod(fake_ask))
    monkeypatch.setattr(wizard.Confirm, "ask", staticmethod(lambda *a, **k: True))

    result = run_config_wizard(config)

    created = result.providers.providers["openai_compatible"]
    assert created.provider_type == ProviderType.OPENAI_COMPATIBLE
    assert created.base_url == "http://localhost:8088/v1"
    assert result.providers.active_provider == "openai_compatible"
