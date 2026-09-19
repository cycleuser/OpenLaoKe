"""Live model discovery for providers.

Most providers expose an OpenAI-compatible ``GET {base_url}/models``. Local
Ollama also exposes ``GET {host}/api/tags``. Discovery falls back to the
configured model list when the endpoint is unreachable or unauthenticated, so
it never makes things worse than a static list.
"""

from __future__ import annotations

import httpx

from openlaoke.types.providers import ProviderConfig

_TIMEOUT = 10.0


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


async def discover_models(provider: ProviderConfig) -> list[str]:
    """Return the provider's live model list, or an empty list on failure."""
    base_url = (provider.base_url or "").rstrip("/")
    ids = await _get_models_endpoint(base_url, provider)
    if not ids and provider.is_local:
        ids = await _get_ollama_tags(base_url)
    # de-duplicate while keeping a stable order
    return sorted(dict.fromkeys(ids))
