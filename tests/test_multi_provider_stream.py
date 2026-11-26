"""Tests for the HTTP side of MultiProviderClient: requests, streaming, fallback.

Everything goes through ``httpx.MockTransport``, so the real request building,
header assembly, SSE parsing and retry logic run without a network. Only the
socket is replaced.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from openlaoke.core.multi_provider_api import MultiProviderClient, _is_local_url
from openlaoke.types.core_types import StreamEventType
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType


def make_provider(
    provider_type: ProviderType = ProviderType.OPENAI,
    *,
    base_url: str = "https://api.example.com/v1",
    api_key: str = "sk-test",
    default_model: str = "test-model",
    is_local: bool = False,
) -> ProviderConfig:
    return ProviderConfig(
        provider_type=provider_type,
        api_key=api_key,
        base_url=base_url,
        default_model=default_model,
        models=[default_model],
        is_local=is_local,
    )


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    *,
    provider: ProviderConfig | None = None,
    extra: dict[str, ProviderConfig] | None = None,
    fallbacks: list[str] | None = None,
) -> MultiProviderClient:
    providers = {"main": provider or make_provider()}
    if extra:
        providers.update(extra)
    config = MultiProviderConfig(
        providers=providers,
        active_provider="main",
        active_model="test-model",
        fallback_models=fallbacks or [],
    )
    client = MultiProviderClient(config)
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


def sse(*events: dict[str, Any]) -> bytes:
    lines = [f"data: {json.dumps(event)}" for event in events]
    lines.append("data: [DONE]")
    return ("\n\n".join(lines) + "\n\n").encode()


def text_chunk(content: str) -> dict[str, Any]:
    return {"choices": [{"index": 0, "delta": {"content": content}}]}


def tool_chunk(index: int, *, call_id: str = "", name: str = "", arguments: str = "") -> dict:
    function: dict[str, Any] = {}
    if name:
        function["name"] = name
    if arguments:
        function["arguments"] = arguments
    tc: dict[str, Any] = {"index": index, "function": function}
    if call_id:
        tc["id"] = call_id
    return {"choices": [{"index": 0, "delta": {"tool_calls": [tc]}}]}


MESSAGES = [{"role": "user", "content": "hi"}]


async def collect(client: MultiProviderClient, **kwargs: Any) -> list:
    return [
        chunk
        async for chunk in client.stream_message(
            system_prompt="be brief", messages=MESSAGES, **kwargs
        )
    ]


# --------------------------------------------------------------------------- #
# _is_local_url
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url,expected",
    [
        ("http://localhost:8080/v1", True),
        ("http://127.0.0.1:11434/v1", True),
        ("http://0.0.0.0:1234/v1", True),
        ("http://[::1]:8088/v1", True),
        ("http://host.docker.internal:8080/v1", True),
        ("https://api.openai.com/v1", False),
        ("http://192.168.1.5:8080/v1", False),
        ("", False),
    ],
)
def test_is_local_url(url: str, expected: bool) -> None:
    assert _is_local_url(url) is expected


# --------------------------------------------------------------------------- #
# send_message: request shape
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_send_message_posts_an_openai_request_with_the_system_prompt_first() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["body"] = json.loads(request.content)
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(
            200,
            json={
                "model": "test-model",
                "choices": [
                    {"message": {"role": "assistant", "content": "hello"}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 10, "completion_tokens": 3},
            },
        )

    client = make_client(handler)
    message, usage, cost = await client.send_message("be brief", MESSAGES, max_tokens=64)
    await client.close()

    assert seen["url"] == "https://api.example.com/v1/chat/completions"
    assert seen["body"]["model"] == "test-model"
    assert seen["body"]["messages"][0] == {"role": "system", "content": "be brief"}
    assert seen["body"]["messages"][1] == {"role": "user", "content": "hi"}
    assert seen["body"]["max_tokens"] == 64
    assert seen["auth"] == "Bearer sk-test"

    assert message.content == "hello"
    assert message.stop_reason == "stop"
    assert usage.input_tokens == 10
    assert usage.output_tokens == 3
    assert cost.input_cost > 0


@pytest.mark.asyncio
async def test_send_message_keeps_cached_prompt_tokens() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "x"}}],
                "usage": {
                    "prompt_tokens": 100,
                    "completion_tokens": 5,
                    "prompt_tokens_details": {"cached_tokens": 90},
                },
            },
        )

    client = make_client(handler)
    _message, usage, _cost = await client.send_message("sys", MESSAGES)
    await client.close()

    assert usage.input_tokens == 100
    assert usage.cache_read_tokens == 90


@pytest.mark.asyncio
async def test_send_message_parses_tool_calls_and_a_reasoning_only_reply() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_1",
                                    "function": {
                                        "name": "Read",
                                        "arguments": json.dumps({"file_path": "a.py"}),
                                    },
                                },
                                {
                                    "id": "call_2",
                                    "function": {"name": "Bash", "arguments": "not json"},
                                },
                            ],
                        }
                    }
                ],
                "usage": {},
            },
        )

    client = make_client(handler)
    message, _usage, _cost = await client.send_message("sys", MESSAGES)
    await client.close()

    assert [t.name for t in message.tool_uses] == ["Read", "Bash"]
    assert message.tool_uses[0].input == {"file_path": "a.py"}
    # Unparseable arguments degrade to an empty dict instead of raising.
    assert message.tool_uses[1].input == {}


@pytest.mark.asyncio
async def test_send_message_surfaces_an_http_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": {"message": "bad key"}})

    client = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await client.send_message("sys", MESSAGES)
    await client.close()


@pytest.mark.asyncio
async def test_send_message_without_an_active_provider_raises() -> None:
    client = MultiProviderClient(MultiProviderConfig(providers={}))
    with pytest.raises(ValueError, match="No active provider"):
        await client.send_message("sys", MESSAGES)


# --------------------------------------------------------------------------- #
# send_message: fallback
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_fallback_to_the_same_family_uses_the_fallback_model() -> None:
    models: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        models.append(body["model"])
        if request.url.host == "api.example.com":
            return httpx.Response(503, text="overloaded")
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "from backup"}}], "usage": {}}
        )

    backup = make_provider(base_url="https://backup.example.com/v1", default_model="backup-model")
    client = make_client(handler, extra={"backup": backup}, fallbacks=["backup"])

    message, _usage, _cost = await client.send_message("sys", MESSAGES)
    await client.close()

    assert models == ["test-model", "backup-model"]
    assert message.content == "from backup"


@pytest.mark.asyncio
async def test_fallback_across_families_parses_with_the_provider_that_answered() -> None:
    """An OpenAI primary failing over to Anthropic must be parsed as Anthropic.

    Regression: the response dispatch used the *primary* provider type, so the
    Anthropic payload went through the OpenAI parser and came back empty (or
    raised), making a cross-family fallback useless.
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.example.com":
            return httpx.Response(502, text="bad gateway")
        assert str(request.url).endswith("/v1/messages")
        body = json.loads(request.content)
        assert body["system"] == "sys"
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "answered by claude"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 7, "output_tokens": 4},
            },
        )

    backup = make_provider(
        ProviderType.ANTHROPIC,
        base_url="https://api.anthropic.com",
        default_model="claude-test",
    )
    client = make_client(handler, extra={"backup": backup}, fallbacks=["backup"])

    message, usage, _cost = await client.send_message("sys", MESSAGES)
    await client.close()

    assert message.content == "answered by claude"
    assert usage.input_tokens == 7


@pytest.mark.asyncio
async def test_no_fallback_on_a_client_error() -> None:
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(400, text="bad request")

    backup = make_provider(base_url="https://backup.example.com/v1")
    client = make_client(handler, extra={"backup": backup}, fallbacks=["backup"])

    with pytest.raises(httpx.HTTPStatusError):
        await client.send_message("sys", MESSAGES)
    await client.close()

    # 400 is the caller's fault: retrying elsewhere would hide it.
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_fallback_that_also_fails_raises_the_second_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "api.example.com":
            return httpx.Response(500, text="boom")
        return httpx.Response(500, text="also boom")

    backup = make_provider(base_url="https://backup.example.com/v1")
    client = make_client(handler, extra={"backup": backup}, fallbacks=["backup"])

    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        await client.send_message("sys", MESSAGES)
    await client.close()

    assert excinfo.value.request.url.host == "backup.example.com"


# --------------------------------------------------------------------------- #
# stream_message: request shape
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stream_requests_usage_and_streaming() -> None:
    seen: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, content=sse(text_chunk("hi")))

    client = make_client(handler)
    await collect(client)
    await client.close()

    assert seen["body"]["stream"] is True
    # Without this the server sends no token counts at all (see llama.cpp).
    assert seen["body"]["stream_options"] == {"include_usage": True}


@pytest.mark.asyncio
async def test_stream_drops_stream_options_when_the_server_rejects_them() -> None:
    bodies: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        bodies.append(body)
        if "stream_options" in body:
            return httpx.Response(400, text='{"error":"unknown field stream_options"}')
        return httpx.Response(200, content=sse(text_chunk("ok")))

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    assert len(bodies) == 2
    assert "stream_options" not in bodies[1]
    assert bodies[1]["stream"] is True
    assert "".join(c.text for c in chunks if c.event_type == StreamEventType.TEXT) == "ok"


@pytest.mark.asyncio
async def test_stream_keeps_a_400_that_is_not_about_stream_options() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text='{"error":"invalid model"}')

    client = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await collect(client)
    await client.close()


# --------------------------------------------------------------------------- #
# stream_message: event parsing
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stream_yields_text_reasoning_usage_and_tool_calls() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse(
                {"choices": [{"delta": {"reasoning_content": "thinking"}}]},
                text_chunk("Let me "),
                text_chunk("look."),
                tool_chunk(0, call_id="call_1", name="Read", arguments='{"file_p'),
                tool_chunk(0, arguments='ath": "a.py"}'),
                {
                    "choices": [],
                    "usage": {
                        "prompt_tokens": 42,
                        "completion_tokens": 9,
                        "prompt_tokens_details": {"cached_tokens": 30},
                    },
                },
            ),
        )

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    text = "".join(c.text for c in chunks if c.event_type == StreamEventType.TEXT)
    reasoning = "".join(c.text for c in chunks if c.event_type == StreamEventType.REASONING)
    tool_calls = [c for c in chunks if c.event_type == StreamEventType.TOOL_CALL_START]
    usage_chunks = [c for c in chunks if c.event_type == StreamEventType.USAGE]

    assert text == "Let me look."
    assert reasoning == "thinking"
    assert len(tool_calls) == 1
    assert tool_calls[0].tool_call_name == "Read"
    assert json.loads(tool_calls[0].tool_call_arguments) == {"file_path": "a.py"}
    # A usage chunk arrives from the final SSE event and again as the closing
    # summary; the last one is authoritative and keeps the cache-read count.
    assert usage_chunks
    assert usage_chunks[-1].usage.input_tokens == 42
    assert usage_chunks[-1].usage.cache_read_tokens == 30


@pytest.mark.asyncio
async def test_stream_emits_an_empty_usage_chunk_when_none_is_reported() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=sse(text_chunk("x")))

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    usage = [c for c in chunks if c.event_type == StreamEventType.USAGE]
    assert len(usage) == 1
    assert usage[0].usage is None


@pytest.mark.asyncio
async def test_stream_repairs_unparseable_tool_arguments() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            content=sse(
                tool_chunk(0, call_id="c", name="Bash", arguments="{oops"),
                {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
            ),
        )

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    tool_calls = [c for c in chunks if c.event_type == StreamEventType.TOOL_CALL_START]
    assert tool_calls[0].tool_call_arguments == "{}"


@pytest.mark.asyncio
async def test_stream_skips_event_lines_that_are_not_data_or_are_broken() -> None:
    body = (
        b": keep-alive\n\n"
        b"data: {not json}\n\n"
        b'data: {"choices":[{"delta":{"content":"ok"}}]}\n\n'
        b"data: [DONE]\n\n"
    )

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    assert "".join(c.text for c in chunks if c.event_type == StreamEventType.TEXT) == "ok"


@pytest.mark.asyncio
async def test_stream_parses_anthropic_sse() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url).endswith("/v1/messages")
        body = json.loads(request.content)
        assert body["stream"] is True
        assert "stream_options" not in body
        events = [
            {
                "type": "content_block_start",
                "index": 0,
                "content_block": {"type": "tool_use", "id": "toolu_1", "name": "Read"},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": '{"file_path":'},
            },
            {
                "type": "content_block_delta",
                "index": 0,
                "delta": {"type": "input_json_delta", "partial_json": ' "b.py"}'},
            },
            {"type": "content_block_start", "index": 1, "content_block": {"type": "text"}},
            {
                "type": "content_block_delta",
                "index": 1,
                "delta": {"type": "text_delta", "text": "reading"},
            },
            {"type": "message_delta", "usage": {"input_tokens": 11, "output_tokens": 2}},
            {"type": "message_stop"},
        ]
        return httpx.Response(200, content=sse(*events))

    client = make_client(handler, provider=make_provider(ProviderType.ANTHROPIC))
    chunks = await collect(client)
    await client.close()

    assert "".join(c.text for c in chunks if c.event_type == StreamEventType.TEXT) == "reading"
    tool_calls = [c for c in chunks if c.event_type == StreamEventType.TOOL_CALL_START]
    assert tool_calls[0].tool_call_name == "Read"
    assert json.loads(tool_calls[0].tool_call_arguments) == {"file_path": "b.py"}
    usage = [c for c in chunks if c.event_type == StreamEventType.USAGE]
    assert usage[-1].usage.input_tokens == 11


# --------------------------------------------------------------------------- #
# stream_message: retries
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_stream_retries_a_503_then_succeeds(monkeypatch) -> None:
    sleeps: list[float] = []

    async def fake_sleep(delay: float) -> None:
        sleeps.append(delay)

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    attempts: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        if len(attempts) == 1:
            return httpx.Response(503, text="overloaded")
        return httpx.Response(200, content=sse(text_chunk("second try")))

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    assert len(attempts) == 2
    assert sleeps and sleeps[0] > 0
    assert "".join(c.text for c in chunks if c.event_type == StreamEventType.TEXT) == "second try"


@pytest.mark.asyncio
async def test_stream_does_not_duplicate_tool_calls_from_a_failed_attempt(monkeypatch) -> None:
    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    calls: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) == 1:
            # A tool call arrives, then the stream dies mid-flight.
            return httpx.Response(
                200,
                content=(
                    b'data: {"choices":[{"delta":{"tool_calls":[{"index":0,"id":"c1",'
                    b'"function":{"name":"Read","arguments":"{\\"file_path\\": \\"a.py\\"}"}}]}}]}\n\n'
                ),
            )
        return httpx.Response(
            200,
            content=sse(
                tool_chunk(0, call_id="c1", name="Read", arguments='{"file_path": "a.py"}'),
                {"choices": [], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
            ),
        )

    client = make_client(handler)
    chunks = await collect(client)
    await client.close()

    tool_calls = [c for c in chunks if c.event_type == StreamEventType.TOOL_CALL_START]
    # The second attempt yields the call once; the first attempt's copy was
    # cleared before the retry.
    assert len(tool_calls) == 1


@pytest.mark.asyncio
async def test_stream_gives_up_after_the_retry_budget(monkeypatch) -> None:
    async def fake_sleep(_delay: float) -> None:
        return None

    monkeypatch.setattr("asyncio.sleep", fake_sleep)
    attempts: list[int] = []

    def handler(_request: httpx.Request) -> httpx.Response:
        attempts.append(1)
        return httpx.Response(500, text="down")

    client = make_client(handler)
    with pytest.raises(httpx.HTTPStatusError):
        await collect(client)
    await client.close()

    assert len(attempts) == 4  # 1 attempt + 3 retries


@pytest.mark.asyncio
async def test_stream_without_an_active_provider_raises() -> None:
    client = MultiProviderClient(MultiProviderConfig(providers={}))
    with pytest.raises(ValueError, match="No active provider"):
        await collect(client)
