"""Live model discovery for providers.

The list a provider exposes at ``GET {base_url}/models`` is often incomplete
(DeepSeek reports two models while its catalog has four). So discovery unions
the provider's live endpoint with the models.dev catalog, which is the same
registry pi and opencode use. Both sources are fetched at runtime; the catalog
is cached on disk for a day.

Provider endpoints are tried first, local Ollama falls back to ``/api/tags``,
and the configured model list is only a last resort when everything is
unreachable.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import httpx

from openlaoke.types.providers import ProviderConfig, ProviderType

_TIMEOUT = 10.0
_CATALOG_URL = "https://models.dev/api.json"
_CATALOG_CACHE = Path.home() / ".openlaoke" / "models_catalog.json"
_CATALOG_TTL = 24 * 3600
_catalog_memory: dict | None = None

# ProviderType -> models.dev provider id
_MODELS_DEV_ID = {
    ProviderType.ANTHROPIC: "anthropic",
    ProviderType.OPENAI: "openai",
    ProviderType.DEEPSEEK: "deepseek",
    ProviderType.OLLAMA_CLOUD: "ollama-cloud",
    ProviderType.MINIMAX: "minimax",
    ProviderType.ALIYUN_CODING_PLAN: "alibaba-coding-plan-cn",
    ProviderType.AZURE_OPENAI: "azure",
    ProviderType.GOOGLE: "google",
    ProviderType.GOOGLE_VERTEX: "google-vertex",
    ProviderType.AWS_BEDROCK: "amazon-bedrock",
    ProviderType.XAI: "xai",
    ProviderType.MISTRAL: "mistral",
    ProviderType.GROQ: "groq",
    ProviderType.CEREBRAS: "cerebras",
    ProviderType.COHERE: "cohere",
    ProviderType.DEEPINFRA: "deepinfra",
    ProviderType.TOGETHERAI: "togetherai",
    ProviderType.PERPLEXITY: "perplexity",
    ProviderType.OPENROUTER: "openrouter",
    ProviderType.GITHUB_COPILOT: "github-copilot",
    ProviderType.OPENCODE: "opencode",
}


def _auth_headers(provider: ProviderConfig) -> dict[str, str]:
    if provider.api_key:
        return {"Authorization": f"Bearer {provider.api_key}"}
    return {}


async def _get_models_endpoint(base_url: str, provider: ProviderConfig) -> list[str]:
    if not base_url:
        return []
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{base_url}/models", headers=_auth_headers(provider))
    except Exception:
        return []
    if resp.status_code >= 400:
        return []
    try:
        data = resp.json()
    except Exception:
        return []
    items = data.get("data") if isinstance(data, dict) else data
    ids: list[str] = []
    for item in items or []:
        if isinstance(item, dict):
            name = item.get("id") or item.get("name")
            if name:
                ids.append(str(name))
    return ids


async def _get_ollama_tags(base_url: str) -> list[str]:
    if not base_url:
        return []
    host = base_url[:-3] if base_url.endswith("/v1") else base_url
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(f"{host}/api/tags")
    except Exception:
        return []
    if resp.status_code >= 400:
        return []
    try:
        models = resp.json().get("models", [])
    except Exception:
        return []
    return [str(m.get("name")) for m in models if isinstance(m, dict) and m.get("name")]


async def _load_catalog() -> dict:
    """Fetch and cache the models.dev provider catalog."""
    global _catalog_memory
    if _catalog_memory is not None:
        return _catalog_memory

    fresh = (
        _CATALOG_CACHE.exists() and (time.time() - _CATALOG_CACHE.stat().st_mtime) < _CATALOG_TTL
    )
    if fresh:
        try:
            _catalog_memory = json.loads(_CATALOG_CACHE.read_text(encoding="utf-8"))
            return _catalog_memory
        except Exception:
            pass

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(_CATALOG_URL)
            resp.raise_for_status()
            data = resp.json()
        _CATALOG_CACHE.parent.mkdir(parents=True, exist_ok=True)
        _CATALOG_CACHE.write_text(json.dumps(data), encoding="utf-8")
        _catalog_memory = data
        return data
    except Exception:
        if _CATALOG_CACHE.exists():
            try:
                _catalog_memory = json.loads(_CATALOG_CACHE.read_text(encoding="utf-8"))
                return _catalog_memory
            except Exception:
                pass
        _catalog_memory = {}
        return {}


async def _catalog_models(provider: ProviderConfig) -> list[str]:
    provider_id = _MODELS_DEV_ID.get(provider.provider_type)
    if not provider_id:
        return []
    catalog = await _load_catalog()
    entry = catalog.get(provider_id) or {}
    return list((entry.get("models") or {}).keys())


async def discover_models(provider: ProviderConfig) -> list[str]:
    """Return the live + catalog model list for a provider, or [] on failure."""
    base_url = (provider.base_url or "").rstrip("/")
    live = await _get_models_endpoint(base_url, provider)
    if not live and provider.is_local:
        live = await _get_ollama_tags(base_url)
    catalog = await _catalog_models(provider)
    # de-duplicate, keeping live models first
    return list(dict.fromkeys([*live, *catalog]))
