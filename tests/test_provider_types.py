"""Tests for provider config types: local reachability probing/caching, the
MultiProviderConfig selection helpers and Ollama model discovery.

All network access is stubbed with a fake httpx client; no sockets are opened.
"""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

from openlaoke.types import providers as mod
from openlaoke.types.providers import (
    MultiProviderConfig,
    ProviderConfig,
    ProviderType,
    _cached_local_reachability,
    _check_local_server,
    _local_probe_url,
    clear_local_probe_cache,
    probe_local_providers,
)

# --------------------------------------------------------------------------- #
# Local probe helpers
# --------------------------------------------------------------------------- #


@pytest.fixture(autouse=True)
def _clean_probe_cache():
    clear_local_probe_cache()
    yield
    clear_local_probe_cache()


@pytest.mark.parametrize(
    "provider,expected",
    [
        (ProviderConfig(provider_type=ProviderType.OLLAMA), "http://localhost:11434"),
        (ProviderConfig(provider_type=ProviderType.LM_STUDIO), "http://localhost:1234"),
        (
            ProviderConfig(provider_type=ProviderType.OLLAMA, base_url="http://127.0.0.1:9000/v1"),
            "http://127.0.0.1:9000/v1",
        ),
        (ProviderConfig(provider_type=ProviderType.OPENAI), ""),
    ],
)
def test_local_probe_url(provider: ProviderConfig, expected: str) -> None:
    assert _local_probe_url(provider) == expected


def test_check_local_server_returns_false_without_url() -> None:
    assert _check_local_server("") is False


class FakeHttpxClient:
    """Minimal stand-in for httpx.Client recording the probe URL."""

    def __init__(self, status: int = 200, exc: Exception | None = None):
        self.status = status
        self.exc = exc
        self.requested: list[str] = []
        self.kwargs: dict = {}

    def __call__(self, *args, **kwargs):
        self.kwargs = kwargs
        return self

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False

    def get(self, url: str):
        self.requested.append(url)
        if self.exc is not None:
            raise self.exc
        return SimpleNamespace(status_code=self.status)


@pytest.fixture()
def fake_httpx(monkeypatch):
    def install(status: int = 200, exc: Exception | None = None) -> FakeHttpxClient:
        fake = FakeHttpxClient(status=status, exc=exc)
        import httpx

        monkeypatch.setattr(httpx, "Client", fake)
        return fake

    return install


@pytest.mark.parametrize(
    "base,expected_probe",
    [
        ("http://localhost:11434", "http://localhost:11434/v1/models"),
        ("http://localhost:11434/", "http://localhost:11434/v1/models"),
        ("http://localhost:8088/v1", "http://localhost:8088/v1/models"),
        ("http://localhost:8088/v1/", "http://localhost:8088/v1/models"),
    ],
)
def test_check_local_server_probe_paths(fake_httpx, base: str, expected_probe: str) -> None:
    fake = fake_httpx(status=200)
    assert _check_local_server(base) is True
    assert fake.requested == [expected_probe]


def test_check_local_server_ignores_proxy_environment(fake_httpx) -> None:
    fake = fake_httpx(status=200)
    _check_local_server("http://localhost:11434")
    assert fake.kwargs["trust_env"] is False


def test_check_local_server_server_error_is_unreachable(fake_httpx) -> None:
    fake_httpx(status=500)
    assert _check_local_server("http://localhost:11434") is False


def test_check_local_server_connection_error_is_unreachable(fake_httpx) -> None:
    fake_httpx(exc=RuntimeError("connection refused"))
    assert _check_local_server("http://localhost:11434") is False


def test_cached_reachability_hits_and_expires(monkeypatch) -> None:
    provider = ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)
    url = _local_probe_url(provider)
    assert _cached_local_reachability(provider) is None

    mod._local_probe_cache[url] = (time.monotonic(), True)
    assert _cached_local_reachability(provider) is True

    stale = time.monotonic() - (mod.LOCAL_PROBE_TTL_SECONDS + 1)
    mod._local_probe_cache[url] = (stale, True)
    assert _cached_local_reachability(provider) is None


def test_clear_local_probe_cache_empties_it() -> None:
    mod._local_probe_cache["x"] = (time.monotonic(), True)
    clear_local_probe_cache()
    assert mod._local_probe_cache == {}


@pytest.mark.asyncio
async def test_probe_local_providers_skips_non_local_and_disabled(monkeypatch) -> None:
    probed: list[str] = []

    def fake_check(url: str, timeout: float = 0.75) -> bool:
        probed.append(url)
        return True

    monkeypatch.setattr(mod, "_check_local_server", fake_check)
    providers = {
        "remote": ProviderConfig(provider_type=ProviderType.OPENAI, api_key="k"),
        "off": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True, enabled=False),
        "ollama": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True),
    }
    outcome = await probe_local_providers(providers)
    assert outcome == {"ollama": True}
    assert probed == ["http://localhost:11434"]


@pytest.mark.asyncio
async def test_probe_local_providers_empty_when_no_locals() -> None:
    assert await probe_local_providers({}) == {}
    providers = {"remote": ProviderConfig(provider_type=ProviderType.OPENAI, api_key="k")}
    assert await probe_local_providers(providers) == {}


@pytest.mark.asyncio
async def test_probe_local_providers_treats_exceptions_as_unreachable(monkeypatch) -> None:
    def boom(url: str, timeout: float = 0.75) -> bool:
        raise RuntimeError("thread exploded")

    monkeypatch.setattr(mod, "_check_local_server", boom)
    providers = {"ollama": ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)}
    assert await probe_local_providers(providers) == {"ollama": False}


@pytest.mark.asyncio
async def test_probe_local_providers_caches_results(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_check_local_server", lambda url, timeout=0.75: True)
    provider = ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)
    await probe_local_providers({"ollama": provider})
    # A second probe is not needed: the cache answers is_configured directly.
    assert _cached_local_reachability(provider) is True


# --------------------------------------------------------------------------- #
# ProviderConfig readiness
# --------------------------------------------------------------------------- #


def test_is_configured_remote_requires_real_key() -> None:
    assert ProviderConfig(provider_type=ProviderType.OPENAI).is_configured() is False
    assert ProviderConfig(provider_type=ProviderType.OPENAI, api_key="none").is_configured() is False
    assert ProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk-1").is_configured() is True


def test_is_configured_opencode_needs_no_key() -> None:
    assert ProviderConfig(provider_type=ProviderType.OPENCODE).is_configured() is True


def test_is_configured_local_uses_cached_reachability(monkeypatch) -> None:
    provider = ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)
    calls: list[str] = []
    monkeypatch.setattr(mod, "_check_local_server", lambda url, timeout=0.75: calls.append(url) or False)
    assert provider.is_configured() is False
    assert len(calls) == 1
    # Second call served from the cache.
    assert provider.is_configured() is False
    assert len(calls) == 1


def test_is_ready_is_cheap_and_honours_enabled() -> None:
    local = ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)
    assert local.is_ready() is True
    local.enabled = False
    assert local.is_ready() is False
    # Remote providers only need a key; no network probe happens here.
    assert ProviderConfig(provider_type=ProviderType.OPENAI, api_key="sk").is_ready() is True
    assert ProviderConfig(provider_type=ProviderType.OPENAI, api_key="").is_ready() is False
    assert ProviderConfig(provider_type=ProviderType.OPENAI, api_key="none").is_ready() is False


def test_is_ready_serves_cached_reachability_for_local(monkeypatch) -> None:
    provider = ProviderConfig(provider_type=ProviderType.OLLAMA, is_local=True)
    url = _local_probe_url(provider)
    mod._local_probe_cache[url] = (time.monotonic(), False)
    assert provider.is_ready() is False
    mod._local_probe_cache[url] = (time.monotonic(), True)
    assert provider.is_ready() is True


def test_get_default_model_prefers_explicit_and_falls_back_to_first() -> None:
    assert ProviderConfig(provider_type=ProviderType.OPENAI, default_model="a", models=["b"]).get_default_model() == "a"
    assert ProviderConfig(provider_type=ProviderType.OPENAI, models=["b", "c"]).get_default_model() == "b"
    assert ProviderConfig(provider_type=ProviderType.OPENAI).get_default_model() == ""


# --------------------------------------------------------------------------- #
# MultiProviderConfig selection
# --------------------------------------------------------------------------- #


def build_config() -> MultiProviderConfig:
    return MultiProviderConfig(
        providers={
            "ollama": ProviderConfig(
                provider_type=ProviderType.OLLAMA,
                is_local=True,
                default_model="local-1",
                models=["local-1"],
            ),
            "deepseek": ProviderConfig(
                provider_type=ProviderType.OPENAI_COMPATIBLE,
                api_key="sk-ds",
                default_model="deepseek-chat",
            ),
            "openai": ProviderConfig(
                provider_type=ProviderType.OPENAI,
                api_key="sk-oa",
                default_model="gpt-4o",
            ),
            "bare": ProviderConfig(provider_type=ProviderType.OPENAI),
            "opencode": ProviderConfig(provider_type=ProviderType.OPENCODE),
        },
        active_provider="ollama",
        active_model="",
    )


def test_get_active_model_precedence() -> None:
    config = build_config()
    assert config.get_active_model() == "local-1"
    config.active_model = "explicit"
    assert config.get_active_model() == "explicit"
    config.active_provider = "missing"
    config.active_model = ""
    assert config.get_active_model() == ""


def test_get_active_provider_missing_returns_none() -> None:
    config = build_config()
    config.active_provider = "nope"
    assert config.get_active_provider() is None


def test_is_configured_follows_active_provider(monkeypatch) -> None:
    config = build_config()
    config.active_provider = "deepseek"
    assert config.is_configured() is True
    config.active_provider = "bare"
    assert config.is_configured() is False
    config.active_provider = "missing"
    assert config.is_configured() is False


def test_has_provider_selected_rules() -> None:
    config = build_config()
    assert config.has_provider_selected() is True  # local
    config.active_provider = "opencode"
    assert config.has_provider_selected() is True  # no key needed
    config.active_provider = "deepseek"
    assert config.has_provider_selected() is True  # real key
    config.active_provider = "bare"
    assert config.has_provider_selected() is False  # no key
    config.active_provider = "missing"
    assert config.has_provider_selected() is False


def test_set_active_provider_validates_name() -> None:
    config = build_config()
    assert config.set_active_provider("deepseek") is True
    assert config.active_provider == "deepseek"
    assert config.set_active_provider("ghost") is False
    assert config.active_provider == "deepseek"


def test_list_available_providers_filters_unconfigured(monkeypatch) -> None:
    monkeypatch.setattr(mod, "_check_local_server", lambda url, timeout=0.75: True)
    config = build_config()
    names = config.list_available_providers()
    assert "ollama" in names
    assert "deepseek" in names
    assert "bare" not in names


def test_fallback_prefers_configured_chain_entry() -> None:
    config = build_config()
    config.fallback_models = ["bare", "openai"]
    result = config.get_fallback_provider()
    assert result is not None
    assert result[0] == "openai"


def test_fallback_skips_active_and_local_when_chain_empty() -> None:
    config = build_config()
    config.fallback_models = []
    result = config.get_fallback_provider()
    assert result is not None
    # First non-active, configured, non-local provider.
    assert result[0] == "deepseek"


def test_fallback_none_when_nothing_configured() -> None:
    config = MultiProviderConfig(
        providers={"bare": ProviderConfig(provider_type=ProviderType.OPENAI)},
        active_provider="bare",
    )
    assert config.get_fallback_provider() is None


def test_planner_provider_lookup() -> None:
    config = build_config()
    assert config.get_planner_provider() is None
    config.planner_model = "openai"
    assert config.get_planner_provider()[0] == "openai"  # type: ignore[index]
    config.planner_model = "ghost"
    assert config.get_planner_provider() is None


def test_subagent_model_override() -> None:
    config = build_config()
    assert config.get_subagent_model("reviewer") == ""
    config.subagent_models = {"reviewer": "gpt-4o"}
    assert config.get_subagent_model("reviewer") == "gpt-4o"


# --------------------------------------------------------------------------- #
# Ollama model discovery
# --------------------------------------------------------------------------- #


@pytest.fixture()
def fake_tags(monkeypatch):
    def install(payload=None, status: int = 200, exc: Exception | None = None):
        class FakeClient:
            def __init__(self, *args, **kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *exc_info):
                return False

            def get(self, url):
                if exc is not None:
                    raise exc
                return SimpleNamespace(status_code=status, json=lambda: payload)

        import httpx

        monkeypatch.setattr(httpx, "Client", FakeClient)

    return install


def test_detect_ollama_models_filters_embeddings(fake_tags) -> None:
    fake_tags(
        {
            "models": [
                {"name": "qwen2.5-coder:7b"},
                {"name": "nomic-embed-text:latest"},
                {"name": "bge-m3"},
                {"name": "llama3.2:3b"},
            ]
        }
    )
    assert mod.MultiProviderConfig._detect_ollama_models() == ["qwen2.5-coder:7b", "llama3.2:3b"]


def test_detect_ollama_models_keeps_all_when_only_embeddings(fake_tags) -> None:
    fake_tags({"models": [{"name": "nomic-embed-text"}, {"name": "bge-small"}]})
    # Better to surface the embedding models than an empty list.
    assert mod.MultiProviderConfig._detect_ollama_models() == ["nomic-embed-text", "bge-small"]


def test_detect_ollama_models_empty_on_error(fake_tags) -> None:
    fake_tags(exc=ConnectionError("no ollama"))
    assert mod.MultiProviderConfig._detect_ollama_models() == []


def test_detect_ollama_models_empty_on_non_200(fake_tags) -> None:
    fake_tags({"models": []}, status=404)
    assert mod.MultiProviderConfig._detect_ollama_models() == []


# --------------------------------------------------------------------------- #
# Coding plan lookup
# --------------------------------------------------------------------------- #


def test_get_active_plan_falls_back_to_default() -> None:
    from openlaoke.types.providers import CodingPlan, PlanConfig

    config = PlanConfig(
        plans={
            "default": CodingPlan(name="default", description="d", max_iterations=10, tools=[]),
            "plan": CodingPlan(name="plan", description="p", max_iterations=80, tools=[]),
        },
        active_plan="missing",
    )
    assert config.get_active_plan().name == "default"
    config.active_plan = "plan"
    assert config.get_active_plan().max_iterations == 80


def test_plan_config_defaults_include_the_four_builtin_plans() -> None:
    from openlaoke.types.providers import PlanConfig

    plans = PlanConfig.defaults()
    assert set(plans.plans) == {"default", "quick", "explorer", "architect"}
    assert plans.active_plan == "default"
    assert plans.plans["quick"].auto_approve is True
    # Explorer is read-only: no write/edit tools.
    assert "Write" not in plans.plans["explorer"].tools
