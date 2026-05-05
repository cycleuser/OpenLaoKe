"""Generic Web AI Service Client.

This module provides a unified client interface for various
web-based AI services using browser authentication.
"""

from __future__ import annotations

import json
from typing import Any

import httpx


class WebServiceClient:
    """Generic client for web-based AI services."""

    def __init__(
        self,
        provider_type: str,
        cookie: str,
        user_agent: str = "",
        bearer_token: str = "",
        base_url: str = "",
        api_endpoint: str = "",
        custom_headers: dict[str, str] | None = None,
    ) -> None:
        """Initialize the web service client.

        Args:
            provider_type: Provider type (e.g., 'deepseek-chat', 'claude-web')
            cookie: Browser cookies string
            user_agent: User agent string
            bearer_token: Optional bearer token
            base_url: Base URL of the service
            api_endpoint: API endpoint URL
            custom_headers: Additional custom headers
        """
        self.provider_type = provider_type
        self.cookie = cookie
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.bearer_token = bearer_token
        self.base_url = base_url
        self.api_endpoint = api_endpoint
        self.custom_headers = custom_headers or {}

        self._client: httpx.AsyncClient | None = None

    def _get_headers(self) -> dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            "Cookie": self.cookie,
            "User-Agent": self.user_agent,
            "Content-Type": "application/json",
            "Accept": "*/*",
            "Referer": f"{self.base_url}/",
            "Origin": self.base_url,
        }

        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

        headers.update(self.custom_headers)

        return headers

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(300.0, connect=30.0),
                headers=self._get_headers(),
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> dict[str, Any]:
        """Send a chat request.

        Args:
            messages: List of chat messages
            model: Model to use
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            Response dict with content and metadata
        """
        client = await self._get_client()

        # Build request payload based on provider type
        payload = self._build_payload(messages, model, temperature, max_tokens, stream)

        response = await client.post(
            self.api_endpoint,
            json=payload,
        )

        if response.status_code >= 400:
            error_detail = response.text[:500]
            raise httpx.HTTPStatusError(
                f"{self.provider_type} API error: {response.status_code} {response.reason_phrase}\n{error_detail}",
                request=response.request,
                response=response,
            )

        # Parse response based on provider type
        return self._parse_response(response.json())

    def _build_payload(
        self,
        messages: list[dict[str, str]],
        model: str,
        temperature: float,
        max_tokens: int,
        stream: bool,
    ) -> dict[str, Any]:
        """Build request payload based on provider type."""
        # Default OpenAI-compatible format
        return {
            "model": model or self.provider_type,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

    def _parse_response(self, data: dict[str, Any]) -> dict[str, Any]:
        """Parse response based on provider type."""
        # Default OpenAI-compatible format
        choices = data.get("choices", [])
        if not choices:
            return {"content": "", "error": "No choices in response"}

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        return {
            "content": content,
            "model": data.get("model", self.provider_type),
            "usage": data.get("usage", {}),
            "finish_reason": choice.get("finish_reason", "stop"),
        }

    async def chat_stream(
        self,
        messages: list[dict[str, str]],
        model: str = "",
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Any:
        """Send a streaming chat request.

        Yields:
            Text deltas from the stream
        """
        client = await self._get_client()

        payload = self._build_payload(messages, model, temperature, max_tokens, stream=True)

        async with client.stream(
            "POST",
            self.api_endpoint,
            json=payload,
        ) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line:
                    continue

                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        content = self._parse_stream_chunk(data)
                        if content:
                            yield content
                    except json.JSONDecodeError:
                        continue

    def _parse_stream_chunk(self, data: dict[str, Any]) -> str:
        """Parse a streaming chunk based on provider type."""
        # Default OpenAI-compatible format
        choices = data.get("choices", [])
        if choices:
            delta = choices[0].get("delta", {})
            return str(delta.get("content", ""))
        return ""
