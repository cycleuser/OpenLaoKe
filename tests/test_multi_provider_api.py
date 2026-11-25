"""Unit tests for core.multi_provider_api: retry policy, URL classification,
provider detection, response parsing, stream event parsing and message
conversion. No network access: the client is constructed with a config whose
providers are local so cost accounting is deterministic.
"""

from __future__ import annotations

import json

import pytest

from openlaoke.core.multi_provider_api import (
    _BASE_DELAY,
    _MAX_DELAY,
    MultiProviderClient,
)
from openlaoke.types.core_types import StreamEventType
from openlaoke.types.providers import (
    MultiProviderConfig,
    ProviderConfig,
    ProviderType,
)

# --------------------------------------------------------------------------- #
# Fixtures
# --------------------------------------------------------------------------- #


def make_client(
    *, local: bool = True, base_url: str = "http://127.0.0.1:8088"
) -> MultiProviderClient:
    provider = ProviderConfig(
        provider_type=ProviderType.OPENAI_COMPATIBLE,
        base_url=base_url,
        default_model="local-model",
        is_local=local,
    )
    config = MultiProviderConfig(
        providers={"local": provider},
        active_provider="local",
        active_model="local-model",
    )
    return MultiProviderClient(config)


@pytest.fixture()
def client() -> MultiProviderClient:
    return make_client()


# --------------------------------------------------------------------------- #
# _is_local_url
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost:8088/v1",
        "http://127.0.0.1:8088/v1",
        "http://0.0.0.0:8088",
        "http://[::1]:8088",
        "http://host.docker.internal:8088/v1",
        "HTTP://LOCALHOST:8088",  # hostname is lower-cased
    ],
)
def test_is_local_url_true(url: str) -> None:
    from openlaoke.core.multi_provider_api import _is_local_url

    assert _is_local_url(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "https://api.openai.com/v1",
        "https://api.deepseek.com/v1",
        "http://192.168.1.10:8088",  # LAN but not in the local allow-list
        "http://10.0.0.5:1234/v1",
        "not a url",
        "",
    ],
)
def test_is_local_url_false(url: str) -> None:
    from openlaoke.core.multi_provider_api import _is_local_url

    assert _is_local_url(url) is False


# --------------------------------------------------------------------------- #
# _retry_with_backoff
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retryable_statuses_retry(client: MultiProviderClient, status: int) -> None:
    should_retry, delay = client._retry_with_backoff(status, attempt=0)
    assert should_retry is True
    # Base delay ±30% jitter.
    assert _BASE_DELAY <= delay <= _BASE_DELAY * 1.3 + 1e-9


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422, 200])
def test_non_retryable_statuses_do_not_retry(client: MultiProviderClient, status: int) -> None:
    should_retry, delay = client._retry_with_backoff(status, attempt=1)
    assert should_retry is False
    assert delay == 0


def test_backoff_grows_with_attempts_and_is_capped(client: MultiProviderClient) -> None:
    delays = [client._retry_with_backoff(500, attempt=i)[1] for i in range(8)]
    # Attempt 0 vs 1: roughly doubles (allowing jitter on both sides).
    assert delays[1] > delays[0] * 1.3
    # Never exceeds the cap plus jitter.
    assert all(d <= _MAX_DELAY * 1.3 + 1e-9 for d in delays)
    # Large attempts saturate near the cap, not overflow.
    assert delays[-1] >= _MAX_DELAY


def test_backoff_jitter_keeps_delays_varying(client: MultiProviderClient) -> None:
    samples = {round(client._retry_with_backoff(503, attempt=2)[1], 6) for _ in range(8)}
    assert len(samples) > 1


# --------------------------------------------------------------------------- #
# detect_provider_type
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "base_url,expected",
    [
        ("https://api.deepseek.com/v1", ProviderType.OPENAI_COMPATIBLE),
        ("https://api.anthropic.com", ProviderType.ANTHROPIC),
        ("https://api.openai.com/v1", ProviderType.OPENAI),
        ("https://openrouter.ai/api/v1", ProviderType.OPENAI),
        ("http://localhost:11434/v1", ProviderType.OLLAMA),
        ("http://localhost:1234/v1", ProviderType.LM_STUDIO),
        ("https://api.mistral.ai/v1", ProviderType.MISTRAL),
        ("https://api.groq.com/openai/v1", ProviderType.GROQ),
        ("https://generativelanguage.googleapis.com/v1beta", ProviderType.GOOGLE),
        ("https://api.x.ai/v1", ProviderType.XAI),
        ("http://my-proxy.internal/v1", ProviderType.OPENAI_COMPATIBLE),
    ],
)
def test_detect_provider_type(base_url: str, expected: ProviderType) -> None:
    assert MultiProviderClient.detect_provider_type(base_url) == expected


def test_detect_provider_type_is_case_insensitive() -> None:
    assert MultiProviderClient.detect_provider_type("HTTPS://API.ANTHROPIC.COM") == ProviderType.ANTHROPIC


# --------------------------------------------------------------------------- #
# _parse_openai_response
# --------------------------------------------------------------------------- #


def test_parse_openai_plain_text(client: MultiProviderClient) -> None:
    data = {
        "model": "local-model",
        "choices": [
            {
                "message": {"role": "assistant", "content": "hello"},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }
    msg, usage, cost = client._parse_openai_response(data)
    assert msg.content == "hello"
    assert msg.tool_uses == []
    assert msg.stop_reason == "stop"
    assert usage.input_tokens == 10
    assert usage.output_tokens == 5
    # Local provider => zero cost.
    assert cost.input_cost == 0 and cost.output_cost == 0


def test_parse_openai_tool_calls_and_malformed_args(client: MultiProviderClient) -> None:
    data = {
        "choices": [
            {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "id": "call_1",
                            "function": {"name": "read_file", "arguments": '{"path": "a.py"}'},
                        },
                        {
                            "id": "call_2",
                            "function": {"name": "write_file", "arguments": "{not json"},
                        },
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ],
    }
    msg, _, _ = client._parse_openai_response(data)
    assert len(msg.tool_uses) == 2
    assert msg.tool_uses[0].name == "read_file"
    assert msg.tool_uses[0].input == {"path": "a.py"}
    # Malformed JSON must degrade to empty args, not raise.
    assert msg.tool_uses[1].input == {}
    assert msg.stop_reason == "tool_calls"


def test_parse_openai_reasoning_fallback_when_content_empty(client: MultiProviderClient) -> None:
    data = {
        "choices": [
            {
                "message": {"content": "", "reasoning_content": "thinking text"},
                "finish_reason": "stop",
            }
        ]
    }
    msg, _, _ = client._parse_openai_response(data)
    assert msg.content == "thinking text"
    assert msg.thinking == "thinking text"


def test_parse_openai_empty_choices_degrades_gracefully(client: MultiProviderClient) -> None:
    msg, usage, _ = client._parse_openai_response({})
    assert msg.content == ""
    assert msg.tool_uses == []
    assert msg.stop_reason is None
    assert usage.input_tokens == 0 and usage.output_tokens == 0


# --------------------------------------------------------------------------- #
# _parse_anthropic_response
# --------------------------------------------------------------------------- #


def test_parse_anthropic_text_and_tool_use(client: MultiProviderClient) -> None:
    data = {
        "model": "local-model",
        "content": [
            {"type": "text", "text": "Let me "},
            {"type": "text", "text": "check."},
            {"type": "tool_use", "id": "tu_1", "name": "grep", "input": {"pattern": "x"}},
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 12, "output_tokens": 7},
    }
    msg, usage, _ = client._parse_anthropic_response(data)
    assert msg.content == "Let me check."
    assert len(msg.tool_uses) == 1
    assert msg.tool_uses[0].id == "tu_1"
    assert msg.tool_uses[0].input == {"pattern": "x"}
    assert msg.stop_reason == "tool_use"
    assert usage.input_tokens == 12


def test_parse_anthropic_empty_content(client: MultiProviderClient) -> None:
    msg, usage, _ = client._parse_anthropic_response({})
    assert msg.content == ""
    assert msg.tool_uses == []
    assert usage.input_tokens == 0


# --------------------------------------------------------------------------- #
# _parse_openai_stream_events
# --------------------------------------------------------------------------- #


def test_openai_stream_text_delta(client: MultiProviderClient) -> None:
    pending: dict = {}
    chunks = client._parse_openai_stream_events(
        {"choices": [{"delta": {"content": "Hi"}}]}, pending, "local-model"
    )
    assert len(chunks) == 1
    assert chunks[0].event_type == StreamEventType.TEXT
    assert chunks[0].text == "Hi"


def test_openai_stream_reasoning_delta(client: MultiProviderClient) -> None:
    pending: dict = {}
    chunks = client._parse_openai_stream_events(
        {"choices": [{"delta": {"reasoning_content": "hmm"}}]}, pending, "local-model"
    )
    assert [c.event_type for c in chunks] == [StreamEventType.REASONING]
    assert chunks[0].text == "hmm"


def test_openai_stream_accumulates_fragmented_tool_call(client: MultiProviderClient) -> None:
    pending: dict = {}
    base = {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "call_9", "function": {"name": "bash", "arguments": ""}}]}}]}
    client._parse_openai_stream_events(base, pending, "m")
    client._parse_openai_stream_events(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": '{"cmd"'}}]}}]},
        pending,
        "m",
    )
    client._parse_openai_stream_events(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "function": {"arguments": ': "ls"}'}}]}}]},
        pending,
        "m",
    )
    assert pending[0]["id"] == "call_9"
    assert pending[0]["name"] == "bash"
    assert json.loads(pending[0]["arguments"]) == {"cmd": "ls"}


def test_openai_stream_two_parallel_tool_calls_kept_separate(client: MultiProviderClient) -> None:
    pending: dict = {}
    event = {
        "choices": [
            {
                "delta": {
                    "tool_calls": [
                        {"index": 0, "id": "a", "function": {"name": "read", "arguments": "{}"}},
                        {"index": 1, "id": "b", "function": {"name": "ls", "arguments": "{}"}},
                    ]
                }
            }
        ]
    }
    client._parse_openai_stream_events(event, pending, "m")
    assert set(pending) == {0, 1}
    assert pending[0]["name"] == "read"
    assert pending[1]["name"] == "ls"


def test_openai_stream_usage_chunk(client: MultiProviderClient) -> None:
    pending: dict = {}
    event = {"choices": [], "usage": {"prompt_tokens": 3, "completion_tokens": 4}}
    chunks = client._parse_openai_stream_events(event, pending, "local-model")
    assert len(chunks) == 1
    assert chunks[0].event_type == StreamEventType.USAGE
    assert chunks[0].usage is not None
    assert chunks[0].usage.input_tokens == 3


def test_openai_stream_finish_reason_does_not_clear_pending(client: MultiProviderClient) -> None:
    pending: dict = {}
    client._parse_openai_stream_events(
        {"choices": [{"delta": {"tool_calls": [{"index": 0, "id": "x", "function": {"name": "f", "arguments": "{}"}}]}}]},
        pending,
        "m",
    )
    client._parse_openai_stream_events({"choices": [{"delta": {}, "finish_reason": "tool_calls"}]}, pending, "m")
    assert 0 in pending, "pending tool calls must survive finish_reason for the caller to emit"


# --------------------------------------------------------------------------- #
# _parse_anthropic_stream_events
# --------------------------------------------------------------------------- #


def test_anthropic_stream_text_delta(client: MultiProviderClient) -> None:
    chunks = client._parse_anthropic_stream_events(
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "yo"}}, {}, "m"
    )
    assert [c.event_type for c in chunks] == [StreamEventType.TEXT]
    assert chunks[0].text == "yo"


def test_anthropic_stream_input_json_delta_accumulates(client: MultiProviderClient) -> None:
    pending: dict = {0: {"id": "tu_0", "name": "grep", "arguments": ""}}
    client._parse_anthropic_stream_events(
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": '{"pat'}},
        pending,
        "m",
    )
    client._parse_anthropic_stream_events(
        {"type": "content_block_delta", "index": 0, "delta": {"type": "input_json_delta", "partial_json": 'tern": "x"}'}},
        pending,
        "m",
    )
    assert json.loads(pending[0]["arguments"]) == {"pattern": "x"}


def test_anthropic_stream_unknown_event_is_ignored(client: MultiProviderClient) -> None:
    assert client._parse_anthropic_stream_events({"type": "ping"}, {}, "m") == []


# --------------------------------------------------------------------------- #
# _convert_to_openai_format
# --------------------------------------------------------------------------- #


def test_convert_to_openai_skips_system_injected(client: MultiProviderClient) -> None:
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hi", "system_injected": True},
        {"role": "user", "content": "real"},
    ]
    out = client._convert_to_openai_format(messages)
    # system role is kept by the openai converter; system_injected is dropped.
    assert [m["content"] for m in out] == ["sys", "real"]


def test_convert_to_openai_maps_tool_result(client: MultiProviderClient) -> None:
    out = client._convert_to_openai_format(
        [{"role": "tool_result", "tool_use_id": "call_1", "content": "42"}]
    )
    assert out == [{"role": "tool", "tool_call_id": "call_1", "content": "42"}]


def test_convert_to_openai_groups_legacy_tool_use_into_assistant(client: MultiProviderClient) -> None:
    out = client._convert_to_openai_format(
        [
            {"role": "tool_use", "id": "c1", "name": "read", "input": {"path": "a"}},
            {"role": "tool_use", "id": "c2", "name": "ls", "input": {}},
        ]
    )
    assert len(out) == 1
    assert out[0]["role"] == "assistant"
    calls = out[0]["tool_calls"]
    assert [c["function"]["name"] for c in calls] == ["read", "ls"]
    assert json.loads(calls[0]["function"]["arguments"]) == {"path": "a"}


# --------------------------------------------------------------------------- #
# _convert_to_anthropic_format
# --------------------------------------------------------------------------- #


def test_convert_to_anthropic_drops_system_roles(client: MultiProviderClient) -> None:
    out = client._convert_to_anthropic_format(
        [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "hi", "system_injected": True},
            {"role": "user", "content": "real"},
        ]
    )
    assert [m["content"] for m in out] == ["real"]


def test_convert_to_anthropic_passes_block_lists_through(client: MultiProviderClient) -> None:
    blocks = [{"type": "text", "text": "x", "cache_control": {"type": "ephemeral"}}]
    out = client._convert_to_anthropic_format([{"role": "user", "content": blocks}])
    assert out == [{"role": "user", "content": blocks}]


# --------------------------------------------------------------------------- #
# _calculate_cost
# --------------------------------------------------------------------------- #


def test_calculate_cost_zero_for_local_provider(client: MultiProviderClient) -> None:
    cost = client._calculate_cost({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, "any")
    assert cost.input_cost == 0 and cost.output_cost == 0


def test_calculate_cost_nonzero_for_remote_provider() -> None:
    client = make_client(local=False, base_url="https://api.openai.com/v1")
    cost = client._calculate_cost({"input_tokens": 1_000_000, "output_tokens": 1_000_000}, "gpt-4o")
    assert cost.input_cost > 0
    assert cost.output_cost > 0
    # Output is priced above input for current models.
    assert cost.output_cost > cost.input_cost


def test_calculate_cost_unknown_model_uses_default_pricing() -> None:
    client = make_client(local=False, base_url="https://api.openai.com/v1")
    cost = client._calculate_cost({"input_tokens": 1_000_000, "output_tokens": 0}, "totally-unknown-model")
    assert cost.input_cost > 0


# --------------------------------------------------------------------------- #
# health_check
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_health_check_reports_local_and_unconfigured() -> None:
    from openlaoke.types.providers import ProviderConfig, ProviderType

    config = MultiProviderConfig(
        providers={
            "local": ProviderConfig(provider_type=ProviderType.OPENAI_COMPATIBLE, is_local=True),
            "remote": ProviderConfig(provider_type=ProviderType.OPENAI, api_key=""),
        },
        active_provider="local",
    )
    results = await MultiProviderClient.health_check(config)
    assert results["local"] == {"ok": True, "latency_ms": 0, "note": "local"}
    assert results["remote"]["ok"] is False
    assert results["remote"]["note"] == "not configured"
