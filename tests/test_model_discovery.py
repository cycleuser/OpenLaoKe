"""Tests for live model discovery and context-window resolution.

All HTTP is stubbed with a fake httpx.AsyncClient; the models.dev catalog cache
is redirected into tmp_path so no real network or home directory is touched.
"""

from __future__ import annotations

import json
import time

import pytest

from openlaoke.core import model_discovery as md
from openlaoke.core.model_discovery import (
    _auth_headers,
    _catalog_models,
    _get_models_endpoint_details,
    _get_ollama_tags,
    _load_catalog,
    _local_runtime_context,
    _model_id_candidates,
    _url_is_local,
    discover_model_details,
    discover_models,
    get_context_limit,
    get_effective_context_limit,
)
from openlaoke.types.providers import ProviderConfig, ProviderType

# --------------------------------------------------------------------------- #
# Fake HTTP layer
# --------------------------------------------------------------------------- #


class FakeResponse:
    def __init__(self, payload=None, status: int = 200, raise_http: bool = False, bad_json: bool = False):
        self.status_code = status
        self._payload = payload
        self._bad_json = bad_json
        self._raise = raise_http

    def json(self):
        if self._bad_json:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self._raise:
            raise RuntimeError("http error")


class FakeClient:
    def __init__(self, response=None, exc: Exception | None = None):
        self.response = response
        self.exc = exc
        self.requests: list[str] = []
        self.headers: list[dict] = []
        self.timeouts: list[object] = []

    def __call__(self, *args, **kwargs):
        self.timeouts.append(kwargs.get("timeout"))
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return False

    async def get(self, url, headers=None):
        self.requests.append(url)
        self.headers.append(headers or {})
        if self.exc is not None:
            raise self.exc
        return self.response


@pytest.fixture()
def http(monkeypatch):
    """Install a fake httpx.AsyncClient; the returned client records calls."""
    client = FakeClient()

    def factory(*args, **kwargs):
        # Each AsyncClient(...) construction returns the same recorder.
        client.timeouts.append(kwargs.get("timeout"))
        return client

    monkeypatch.setattr(md.httpx, "AsyncClient", factory)
    return client


@pytest.fixture(autouse=True)
def isolated_catalog(tmp_path, monkeypatch):
    cache = tmp_path / "models_catalog.json"
    monkeypatch.setattr(md, "_CATALOG_CACHE", cache)
    monkeypatch.setattr(md, "_catalog_memory", None)
    yield cache
    monkeypatch.setattr(md, "_catalog_memory", None)


def provider(kind: ProviderType = ProviderType.OPENAI, **kwargs) -> ProviderConfig:
    return ProviderConfig(provider_type=kind, **kwargs)


# --------------------------------------------------------------------------- #
# Headers / URL helpers
# --------------------------------------------------------------------------- #


def test_auth_headers_only_when_a_key_exists() -> None:
    assert _auth_headers(provider(api_key="sk-1")) == {"Authorization": "Bearer sk-1"}
    assert _auth_headers(provider()) == {}


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:11434/v1", True),
        ("http://127.0.0.1:8088", True),
        ("http://0.0.0.0:1", True),
        ("http://[::1]:8088", True),
        ("http://host.docker.internal:80", True),
        ("https://api.openai.com/v1", False),
        ("http://192.168.1.4:8080", False),
        ("", False),
    ],
)
def test_url_is_local(url: str, expected: bool) -> None:
    assert _url_is_local(url) is expected


# --------------------------------------------------------------------------- #
# /models endpoint
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_models_endpoint_without_base_url_returns_nothing(http) -> None:
    assert await _get_models_endpoint_details("", provider()) == ([], {})
    assert http.requests == []


@pytest.mark.asyncio
async def test_models_endpoint_network_error(http) -> None:
    http.response = None
    http.exc = ConnectionError("refused")
    assert await _get_models_endpoint_details("https://x/v1", provider()) == ([], {})


@pytest.mark.asyncio
async def test_models_endpoint_http_error_status(http) -> None:
    http.response = FakeResponse({"data": [{"id": "m"}]}, status=401)
    assert await _get_models_endpoint_details("https://x/v1", provider()) == ([], {})


@pytest.mark.asyncio
async def test_models_endpoint_bad_json(http) -> None:
    http.response = FakeResponse(bad_json=True)
    assert await _get_models_endpoint_details("https://x/v1", provider()) == ([], {})


@pytest.mark.asyncio
async def test_models_endpoint_openai_shape_with_labels(http) -> None:
    http.response = FakeResponse(
        {
            "data": [
                {"id": "gpt-4o", "name": "GPT-4o"},
                {"id": "gpt-4o", "name": "GPT-4o"},  # duplicate id
                {"id": "plain"},  # no label
                {"name": "name-only"},  # id from "name"
                "not a dict",
                {},
            ]
        }
    )
    ids, labels = await _get_models_endpoint_details("https://x/v1/", provider(api_key="sk"))
    assert ids == ["gpt-4o", "plain", "name-only"]
    assert labels == {"gpt-4o": "GPT-4o"}
    assert http.requests == ["https://x/v1//models"]
    assert http.headers[0] == {"Authorization": "Bearer sk"}


@pytest.mark.asyncio
async def test_models_endpoint_accepts_a_bare_list(http) -> None:
    http.response = FakeResponse([{"id": "a"}, {"id": "b"}])
    ids, labels = await _get_models_endpoint_details("https://x/v1", provider())
    assert ids == ["a", "b"]
    assert labels == {}


@pytest.mark.asyncio
async def test_models_endpoint_ignores_a_name_equal_to_the_id(http) -> None:
    http.response = FakeResponse({"data": [{"id": "same", "name": "same"}]})
    _, labels = await _get_models_endpoint_details("https://x/v1", provider())
    assert labels == {}


# --------------------------------------------------------------------------- #
# Ollama /api/tags
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_ollama_tags_without_base_url(http) -> None:
    assert await _get_ollama_tags("") == []


@pytest.mark.asyncio
async def test_ollama_tags_strips_the_v1_suffix(http) -> None:
    http.response = FakeResponse({"models": [{"name": "lfm3-1.7b-q4"}, {"model": "no-name"}, "junk"]})
    assert await _get_ollama_tags("http://localhost:11434/v1") == ["lfm3-1.7b-q4"]
    assert http.requests == ["http://localhost:11434/api/tags"]


@pytest.mark.asyncio
async def test_ollama_tags_errors(http) -> None:
    http.exc = OSError("down")
    assert await _get_ollama_tags("http://localhost:11434") == []

    http.exc = None
    http.response = FakeResponse({}, status=404)
    assert await _get_ollama_tags("http://localhost:11434") == []

    http.response = FakeResponse(bad_json=True)
    assert await _get_ollama_tags("http://localhost:11434") == []


# --------------------------------------------------------------------------- #
# models.dev catalog
# --------------------------------------------------------------------------- #


CATALOG = {"openai": {"models": {"gpt-4o": {"limit": {"context": 128000}}}}}


@pytest.mark.asyncio
async def test_catalog_uses_memory_cache_first(http) -> None:
    md._catalog_memory = {"cached": {}}
    assert await _load_catalog() == {"cached": {}}
    assert http.requests == []


@pytest.mark.asyncio
async def test_catalog_reads_a_fresh_cache_file(http, isolated_catalog) -> None:
    isolated_catalog.write_text(json.dumps(CATALOG), encoding="utf-8")
    assert await _load_catalog() == CATALOG
    assert http.requests == []  # no network needed


@pytest.mark.asyncio
async def test_catalog_downloads_and_caches_when_stale(http, isolated_catalog) -> None:
    http.response = FakeResponse(CATALOG)
    assert await _load_catalog() == CATALOG
    assert http.requests == [md._CATALOG_URL]
    assert json.loads(isolated_catalog.read_text(encoding="utf-8")) == CATALOG


@pytest.mark.asyncio
async def test_catalog_falls_back_to_a_stale_cache_when_download_fails(
    http, isolated_catalog
) -> None:
    isolated_catalog.write_text(json.dumps(CATALOG), encoding="utf-8")
    stale = time.time() - (md._CATALOG_TTL + 100)
    import os

    os.utime(isolated_catalog, (stale, stale))
    http.exc = ConnectionError("offline")
    assert await _load_catalog() == CATALOG


@pytest.mark.asyncio
async def test_catalog_returns_empty_when_everything_fails(http, isolated_catalog) -> None:
    isolated_catalog.write_text("{corrupt", encoding="utf-8")
    stale = time.time() - (md._CATALOG_TTL + 100)
    import os

    os.utime(isolated_catalog, (stale, stale))
    http.exc = ConnectionError("offline")
    assert await _load_catalog() == {}


@pytest.mark.asyncio
async def test_catalog_raise_for_status_is_honoured(http, isolated_catalog) -> None:
    http.response = FakeResponse(CATALOG, raise_http=True)
    assert await _load_catalog() == {}
    assert not isolated_catalog.exists()


@pytest.mark.asyncio
async def test_catalog_models_for_a_known_provider(http) -> None:
    md._catalog_memory = CATALOG
    assert await _catalog_models(provider(ProviderType.OPENAI)) == ["gpt-4o"]


@pytest.mark.asyncio
async def test_catalog_models_for_an_unmapped_provider(http) -> None:
    md._catalog_memory = CATALOG
    assert await _catalog_models(provider(ProviderType.OPENAI_COMPATIBLE)) == []


# --------------------------------------------------------------------------- #
# discover_model_details
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_discover_prefers_the_live_endpoint(http) -> None:
    http.response = FakeResponse({"data": [{"id": "live-1"}, {"id": "live-1"}]})
    ids, _ = await discover_model_details(provider(base_url="https://x/v1"))
    assert ids == ["live-1"]  # deduped
    assert http.requests == ["https://x/v1/models"]


@pytest.mark.asyncio
async def test_discover_falls_back_to_ollama_tags_for_local(http) -> None:
    responses = [
        FakeResponse({}, status=404),  # /v1/models missing
        FakeResponse({"models": [{"name": "local-a"}, {"name": "local-b"}]}),
    ]

    class SequenceClient(FakeClient):
        async def get(self, url, headers=None):
            self.requests.append(url)
            return responses.pop(0)

    client = SequenceClient()
    md.httpx.AsyncClient = lambda *a, **k: client  # type: ignore[assignment]
    ids, _ = await discover_model_details(
        provider(ProviderType.OLLAMA, base_url="http://localhost:11434/v1", is_local=True)
    )
    assert ids == ["local-a", "local-b"]
    assert client.requests == [
        "http://localhost:11434/v1/models",
        "http://localhost:11434/api/tags",
    ]


@pytest.mark.asyncio
async def test_discover_uses_the_catalog_when_nothing_live(http) -> None:
    md._catalog_memory = CATALOG
    http.response = FakeResponse({}, status=500)
    ids, labels = await discover_model_details(provider(ProviderType.OPENAI, base_url="https://x/v1"))
    assert ids == ["gpt-4o"]
    assert labels == {}


@pytest.mark.asyncio
async def test_discover_can_skip_the_catalog(http) -> None:
    md._catalog_memory = CATALOG
    http.response = FakeResponse({}, status=500)
    ids, _ = await discover_model_details(provider(ProviderType.OPENAI), use_catalog=False)
    assert ids == []


@pytest.mark.asyncio
async def test_discover_models_wrapper(http) -> None:
    http.response = FakeResponse({"data": [{"id": "x"}]})
    assert await discover_models(provider(base_url="https://x/v1")) == ["x"]


# --------------------------------------------------------------------------- #
# Model id candidates and catalog context limits
# --------------------------------------------------------------------------- #


def test_model_id_candidates_expand_provider_naming_styles() -> None:
    candidates = _model_id_candidates("LiquidAI-dev/lfm2.5-2.6b:latest")
    # Both the namespaced id and the bare name are tried, with ":latest"
    # stripped and "-" / ":" swapped to cover the catalog's naming variants.
    assert "LiquidAI-dev/lfm2.5-2.6b" in candidates
    assert "lfm2.5-2.6b" in candidates
    assert "lfm2.5:2.6b" in candidates
    assert all(not c.endswith(":latest") for c in candidates)
    assert len(candidates) == len(set(candidates))


@pytest.mark.asyncio
async def test_context_limit_requires_a_mapped_provider_and_a_model(http) -> None:
    md._catalog_memory = CATALOG
    assert await get_context_limit(provider(ProviderType.OPENAI_COMPATIBLE), "gpt-4o") is None
    assert await get_context_limit(provider(ProviderType.OPENAI), "") is None


@pytest.mark.asyncio
async def test_context_limit_reads_the_catalog(http) -> None:
    md._catalog_memory = CATALOG
    assert await get_context_limit(provider(ProviderType.OPENAI), "gpt-4o") == 128000
    # Namespaced ids resolve through the candidate list.
    assert await get_context_limit(provider(ProviderType.OPENAI), "openai/gpt-4o:latest") == 128000


@pytest.mark.asyncio
async def test_context_limit_ignores_missing_or_invalid_entries(http) -> None:
    md._catalog_memory = {
        "openai": {
            "models": {
                "zero": {"limit": {"context": 0}},
                "text": {"limit": {"context": "128k"}},
                "nolimit": {},
            }
        }
    }
    for model in ("zero", "text", "nolimit", "absent"):
        assert await get_context_limit(provider(ProviderType.OPENAI), model) is None


# --------------------------------------------------------------------------- #
# Local runtime context
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_local_runtime_context_requires_a_base_url(http) -> None:
    assert await _local_runtime_context("", "m") is None
    assert http.requests == []


@pytest.mark.asyncio
async def test_local_runtime_context_reads_api_ps(http) -> None:
    http.response = FakeResponse(
        {
            "models": [
                "junk",
                {"name": "lfm3:latest", "context_length": 32768},
            ]
        }
    )
    assert await _local_runtime_context("http://localhost:11434/v1", "lfm3:latest") == 32768
    assert http.requests == ["http://localhost:11434/api/ps"]


@pytest.mark.asyncio
async def test_local_runtime_context_matches_on_the_base_model_name(http) -> None:
    http.response = FakeResponse({"models": [{"model": "qwen2.5:7b", "context_length": 8192}]})
    # The tag/suffix is ignored, so any qwen2.5 variant matches the loaded model.
    assert await _local_runtime_context("http://localhost:11434", "qwen2.5:7b-instruct") == 8192
    assert await _local_runtime_context("http://localhost:11434", "qwen2.5:14b") == 8192
    # A different base name does not match.
    assert await _local_runtime_context("http://localhost:11434", "llama3:8b") is None


@pytest.mark.asyncio
async def test_local_runtime_context_ignores_bad_entries(http) -> None:
    http.response = FakeResponse({"models": [{"name": "m"}, {"name": "m", "context_length": 0}]})
    assert await _local_runtime_context("http://localhost:11434", "m") is None


@pytest.mark.asyncio
async def test_local_runtime_context_errors(http) -> None:
    http.exc = OSError("down")
    assert await _local_runtime_context("http://localhost:11434", "m") is None

    http.exc = None
    http.response = FakeResponse({}, status=500)
    assert await _local_runtime_context("http://localhost:11434", "m") is None

    http.response = FakeResponse(bad_json=True)
    assert await _local_runtime_context("http://localhost:11434", "m") is None


# --------------------------------------------------------------------------- #
# get_effective_context_limit
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_effective_limit_for_cloud_models_is_the_catalog_value(http) -> None:
    md._catalog_memory = CATALOG
    http.response = FakeResponse({"data": []})
    effective = await get_effective_context_limit(
        provider(ProviderType.OPENAI, base_url="https://api.openai.com/v1"), "gpt-4o"
    )
    assert effective == 128000
    # A cloud endpoint is never probed locally (the catalog came from memory).
    assert http.requests == []


@pytest.mark.asyncio
async def test_effective_limit_prefers_the_local_runtime_window(http) -> None:
    md._catalog_memory = {"ollama": {"models": {"big": {"limit": {"context": 262144}}}}}
    http.response = FakeResponse({"models": [{"name": "big", "context_length": 16384}]})
    effective = await get_effective_context_limit(
        provider(ProviderType.OLLAMA, base_url="http://localhost:11434/v1", is_local=True), "big"
    )
    assert effective == 16384  # runtime wins over the catalogued 256k


@pytest.mark.asyncio
async def test_effective_limit_caps_a_catalogued_local_model_at_the_default(http) -> None:
    md._catalog_memory = {"ollama": {"models": {"big": {"limit": {"context": 262144}}}}}
    http.response = FakeResponse({"models": []})
    effective = await get_effective_context_limit(
        provider(ProviderType.OLLAMA, base_url="http://localhost:11434/v1", is_local=True), "big"
    )
    assert effective == md._DEFAULT_LOCAL_CONTEXT


@pytest.mark.asyncio
async def test_effective_limit_defaults_for_an_uncatalogued_local_model(http) -> None:
    md._catalog_memory = {}
    http.response = FakeResponse({"models": []})
    effective = await get_effective_context_limit(
        provider(ProviderType.OLLAMA, base_url="http://127.0.0.1:11434/v1", is_local=True), "unknown"
    )
    assert effective == md._DEFAULT_LOCAL_CONTEXT


@pytest.mark.asyncio
async def test_effective_limit_uses_runtime_when_the_catalog_is_empty(http) -> None:
    md._catalog_memory = {}
    http.response = FakeResponse({"models": [{"name": "m", "context_length": 4096}]})
    effective = await get_effective_context_limit(
        provider(ProviderType.OLLAMA, base_url="http://localhost:11434", is_local=True), "m"
    )
    assert effective == 4096


@pytest.mark.asyncio
async def test_effective_limit_treats_a_localhost_url_as_local(http) -> None:
    md._catalog_memory = {}
    http.response = FakeResponse({"models": [{"name": "m", "context_length": 2048}]})
    effective = await get_effective_context_limit(
        provider(ProviderType.OPENAI_COMPATIBLE, base_url="http://localhost:8088/v1"), "m"
    )
    assert effective == 2048
