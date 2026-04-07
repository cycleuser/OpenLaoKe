"""DeepSeek Web API client using browser authentication.

This module provides API access to DeepSeek's web service using
captured browser cookies and authentication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import httpx


@dataclass
class DeepSeekMessage:
    """A single message in a chat."""

    role: str  # "user", "assistant", or "system"
    content: str


@dataclass
class DeepSeekResponse:
    """Response from DeepSeek API."""

    content: str
    model: str
    usage: dict[str, int]
    finish_reason: str


class DeepSeekWebClient:
    """Client for DeepSeek Web API using browser authentication."""

    def __init__(
        self,
        cookie: str,
        user_agent: str = "",
        bearer_token: str = "",
    ) -> None:
        """Initialize the DeepSeek Web client.

        Args:
            cookie: Browser cookies string
            user_agent: User agent string
            bearer_token: Optional bearer token
        """
        self.cookie = cookie
        self.user_agent = user_agent or (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        self.bearer_token = bearer_token
        self.base_url = "https://chat.deepseek.com"
        self.api_endpoint = f"{self.base_url}/api/v1/chat/completions"

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
            "x-client-platform": "web",
            "x-client-version": "1.7.0",
        }

        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"

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

    async def chat_completions(
        self,
        messages: list[DeepSeekMessage],
        model: str = "deepseek-chat",
        temperature: float = 1.0,
        max_tokens: int = 4096,
        stream: bool = False,
    ) -> DeepSeekResponse:
        """Send a chat completion request.

        Args:
            messages: List of chat messages
            model: Model to use
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response

        Returns:
            DeepSeekResponse with the completion
        """
        client = await self._get_client()

        # Convert messages to API format
        api_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": stream,
        }

        response = await client.post(
            self.api_endpoint,
            json=payload,
        )

        if response.status_code >= 400:
            error_detail = response.text[:500]
            raise httpx.HTTPStatusError(
                f"DeepSeek API error: {response.status_code} {response.reason_phrase}\n{error_detail}",
                request=response.request,
                response=response,
            )

        data = response.json()

        # Parse response
        choices = data.get("choices", [])
        if not choices:
            raise ValueError("DeepSeek API returned no choices")

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content", "")

        usage = data.get("usage", {})

        return DeepSeekResponse(
            content=content,
            model=data.get("model", model),
            usage=usage,
            finish_reason=choice.get("finish_reason", "stop"),
        )

    async def chat_completions_stream(
        self,
        messages: list[DeepSeekMessage],
        model: str = "deepseek-chat",
        temperature: float = 1.0,
        max_tokens: int = 4096,
    ) -> Any:
        """Send a streaming chat completion request.

        Args:
            messages: List of chat messages
            model: Model to use
            temperature: Temperature for sampling
            max_tokens: Maximum tokens to generate

        Yields:
            Text deltas from the stream
        """
        client = await self._get_client()

        api_messages = [{"role": msg.role, "content": msg.content} for msg in messages]

        payload = {
            "model": model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }

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
                        choices = data.get("choices", [])
                        if choices:
                            delta = choices[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                    except json.JSONDecodeError:
                        continue
