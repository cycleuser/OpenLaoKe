"""Tests for MultiProviderClient's per-provider body builders, parsers and conversion.

These are the pure functions that decide what each provider actually receives
and how its answer is read back, so they are tested without any HTTP at all.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from openlaoke.core.multi_provider_api import (
    MultiProviderClient,
    _flatten_content,
    _is_local_url,
)
from openlaoke.types.providers import MultiProviderConfig, ProviderConfig, ProviderType


def provider(
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


def client_for(p: ProviderConfig | None = None) -> MultiProviderClient:
    active = p or provider()
    return MultiProviderClient(
        MultiProviderConfig(
            providers={"main": active},
            active_provider="main",
            active_model=active.default_model,
        )
    )


TOOLS = [
    {
        "name": "Read",
        "description": "read a file",
        "input_schema": {"type": "object", "properties": {"file_path": {"type": "string"}}},
    }
]

CONVERSATION = [
    {"role": "user", "content": "look at a.py"},
    {"role": "assistant", "content": "ok", "tool_calls": []},
]


# --------------------------------------------------------------------------- #
# _flatten_content
# --------------------------------------------------------------------------- #


def test_flatten_content_passes_strings_through() -> None:
    assert _flatten_content("hello") == "hello"
    assert _flatten_content("") == ""


def test_flatten_content_handles_none_and_non_strings() -> None:
    assert _flatten_content(None) == ""
    assert _flatten_content(42) == "42"


def test_flatten_content_joins_anthropic_text_blocks() -> None:
    blocks = [
        {"type": "text", "text": "first", "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": "second"},
    ]
    assert _flatten_content(blocks) == "first\nsecond"


def test_flatten_content_reads_tool_result_blocks_and_skips_the_rest() -> None:
    blocks: list[Any] = [
        {"type": "tool_result", "content": "file body"},
        {"type": "image", "source": {}},
        "plain",
    ]
    assert _flatten_content(blocks) == "file body\nplain"


# --------------------------------------------------------------------------- #
# Message conversion
# --------------------------------------------------------------------------- #


def test_anthropic_conversion_moves_system_and_tool_turns_into_blocks() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    messages = [
        {"role": "system", "content": "system prompt"},
        {"role": "user", "content": "hi"},
        {
            "role": "assistant",
            "content": "reading",
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "Read", "arguments": json.dumps({"file_path": "a.py"})},
                }
            ],
        },
        {"role": "tool", "tool_call_id": "call_1", "content": "body"},
    ]

    converted = client._convert_messages_for_provider(messages, ProviderType.ANTHROPIC)

    # The system turn travels as the top-level "system" parameter instead.
    assert [m["role"] for m in converted] == ["user", "assistant", "user"]
    assert converted[1]["content"][0] == {"type": "text", "text": "reading"}
    assert converted[1]["content"][1] == {
        "type": "tool_use",
        "id": "call_1",
        "name": "Read",
        "input": {"file_path": "a.py"},
    }
    assert converted[2]["content"][0] == {
        "type": "tool_result",
        "tool_use_id": "call_1",
        "content": "body",
    }


def test_anthropic_conversion_keeps_existing_content_blocks() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    blocks = [{"type": "text", "text": "x", "cache_control": {"type": "ephemeral"}}]
    converted = client._convert_messages_for_provider(
        [{"role": "user", "content": blocks}], ProviderType.ANTHROPIC
    )
    assert converted[0]["content"] == blocks


def test_anthropic_conversion_handles_internal_tool_result_and_legacy_tool_use() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "find x"},
            {"role": "tool_use", "id": "t1", "name": "Grep", "input": {"pattern": "x"}},
            {"role": "tool_result", "tool_use_id": "t1", "content": "match"},
        ],
        ProviderType.ANTHROPIC,
    )

    assert converted[1]["content"][0] == {
        "type": "tool_use",
        "id": "t1",
        "name": "Grep",
        "input": {"pattern": "x"},
    }
    assert converted[2]["content"][0]["tool_use_id"] == "t1"


def test_anthropic_conversion_survives_unparseable_tool_arguments() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "run it"},
            {
                "role": "assistant",
                "content": "",
                "tool_calls": [
                    {"id": "c", "function": {"name": "Bash", "arguments": "{broken"}}
                ],
            },
        ],
        ProviderType.ANTHROPIC,
    )
    assert converted[-1]["content"][0]["input"] == {}


def test_anthropic_conversion_drops_system_injected_turns() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "hi"},
            {"role": "user", "content": "[session context]", "system_injected": True},
        ],
        ProviderType.ANTHROPIC,
    )
    assert [m["content"] for m in converted] == ["hi"]


def test_openai_conversion_uses_flat_tool_turns() -> None:
    client = client_for()
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "hi"},
            {"role": "tool_result", "tool_use_id": "c1", "content": "42"},
            {"role": "tool_use", "id": "c2", "name": "Read", "input": {"file_path": "a.py"}},
        ],
        ProviderType.OPENAI,
    )

    assert converted[1] == {"role": "tool", "tool_call_id": "c1", "content": "42"}
    # A tool_use with no preceding assistant turn opens one.
    assert converted[2]["role"] == "assistant"
    assert converted[2]["tool_calls"][0]["function"]["name"] == "Read"
    assert json.loads(converted[2]["tool_calls"][0]["function"]["arguments"]) == {
        "file_path": "a.py"
    }


def test_openai_conversion_appends_to_the_previous_assistant_turn() -> None:
    client = client_for()
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "go"},
            {"role": "assistant", "content": "one"},
            {"role": "tool_use", "id": "c1", "name": "Read", "input": {}},
            {"role": "tool_use", "id": "c2", "name": "Grep", "input": {}},
        ],
        ProviderType.OPENAI,
    )

    # Both legacy tool_use turns land on the same assistant message.
    assert [m["role"] for m in converted] == ["user", "assistant"]
    assert [tc["id"] for tc in converted[1]["tool_calls"]] == ["c1", "c2"]


def test_openai_conversion_keeps_native_assistant_tool_calls_and_drops_injected() -> None:
    client = client_for()
    native = {
        "role": "assistant",
        "content": "",
        "tool_calls": [{"id": "c1", "type": "function", "function": {"name": "Read"}}],
    }
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "hi"},
            native,
            {"role": "user", "content": "[ctx]", "system_injected": True},
        ],
        ProviderType.OPENAI,
    )

    # Native assistant turns pass through with their tool_calls intact.
    assert converted[1] == native
    assert [m["role"] for m in converted] == ["user", "assistant"]


# --------------------------------------------------------------------------- #
# Tool schema conversion
# --------------------------------------------------------------------------- #


def test_openai_tool_conversion_wraps_internal_schemas_and_keeps_native_ones() -> None:
    client = client_for()
    native = {"type": "function", "function": {"name": "Native", "parameters": {}}}
    converted = client._convert_tools_to_openai_format([TOOLS[0], native])

    assert converted[1] is native
    assert converted[0] == {
        "type": "function",
        "function": {
            "name": "Read",
            "description": "read a file",
            "parameters": TOOLS[0]["input_schema"],
        },
    }


def test_google_tool_conversion_uses_function_declarations() -> None:
    client = client_for(provider(ProviderType.GOOGLE))
    converted = client._convert_tools_to_google_format(TOOLS)
    assert converted[0]["functionDeclarations"][0]["name"] == "Read"


def test_google_tool_conversion_accepts_already_converted_tools() -> None:
    client = client_for(provider(ProviderType.GOOGLE))
    native = {
        "type": "function",
        "function": {"name": "Read", "description": "d", "parameters": {"type": "object"}},
    }
    assert client._convert_tools_to_google_format([native])[0]["functionDeclarations"][0] == {
        "name": "Read",
        "description": "d",
        "parameters": {"type": "object"},
    }


def test_cohere_tool_conversion_mirrors_openai_shape() -> None:
    client = client_for(provider(ProviderType.COHERE))
    converted = client._convert_tools_to_cohere_format(TOOLS)
    assert converted[0]["type"] == "function"
    assert converted[0]["function"]["name"] == "Read"


# --------------------------------------------------------------------------- #
# Body builders
# --------------------------------------------------------------------------- #


def test_anthropic_body_carries_thinking_and_omits_default_temperature() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    body = client._build_anthropic_body(
        "model-x", [{"role": "user", "content": "hi"}], TOOLS, 512, 1.0, 2048
    )

    assert body["max_tokens"] == 512
    assert "temperature" not in body
    assert body["thinking"] == {"type": "enabled", "budget_tokens": 2048}
    assert body["tools"] == TOOLS


def test_anthropic_body_forwards_a_non_default_temperature() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    body = client._build_anthropic_body(
        "model-x", [{"role": "user", "content": "hi"}], None, 512, 0.2, 0
    )

    assert body["temperature"] == 0.2
    assert "tools" not in body
    assert "thinking" not in body


def test_openai_body_maps_thinking_budget_to_reasoning_effort() -> None:
    client = client_for(provider(ProviderType.OPENAI))
    messages = [{"role": "user", "content": "hi"}]

    low = client._build_openai_body("m", messages, None, 100, 1.0, thinking_budget=400)
    medium = client._build_openai_body("m", messages, None, 100, 1.0, thinking_budget=1500)
    high = client._build_openai_body("m", messages, None, 100, 1.0, thinking_budget=8000)

    assert low["reasoning_effort"] == "low"
    assert medium["reasoning_effort"] == "medium"
    assert high["reasoning_effort"] == "high"


def test_openai_body_uses_deepseek_thinking_kwargs() -> None:
    client = client_for(provider(ProviderType.DEEPSEEK, base_url="https://api.deepseek.com/v1"))
    body = client._build_openai_body(
        "deepseek-chat", [{"role": "user", "content": "hi"}], None, 100, 1.0, thinking_budget=700
    )
    assert body["chat_template_kwargs"] == {"thinking_budget": 700}
    assert "reasoning_effort" not in body


def test_openai_body_silences_thinking_on_a_local_server() -> None:
    client = client_for(
        provider(base_url="http://127.0.0.1:8088/v1", is_local=True)
    )
    body = client._build_openai_body(
        "local", [{"role": "user", "content": "hi"}], None, 100, 1.0
    )
    assert body["reasoning_effort"] == "none"


def test_openai_body_passes_an_explicit_reasoning_effort_through() -> None:
    client = client_for(provider(ProviderType.OPENAI))
    body = client._build_openai_body(
        "m", [{"role": "user", "content": "hi"}], None, 100, 1.0, reasoning_effort="high"
    )
    assert body["reasoning_effort"] == "high"


def test_openai_body_omits_a_default_temperature_and_forwards_tools() -> None:
    client = client_for(provider(ProviderType.OPENAI))
    body = client._build_openai_body(
        "m", [{"role": "user", "content": "hi"}], TOOLS, 100, 1.0
    )
    assert "temperature" not in body
    assert body["tools"][0]["type"] == "function"


def test_google_body_flattens_blocks_and_promotes_the_system_prompt() -> None:
    client = client_for(provider(ProviderType.GOOGLE))
    body = client._build_google_body(
        "be terse",
        [
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            {"role": "tool", "content": "result"},
            {"role": "assistant", "content": "done"},
        ],
        TOOLS,
        256,
        0.5,
    )

    assert body["systemInstruction"] == {"parts": [{"text": "be terse"}]}
    assert body["contents"][0] == {"role": "user", "parts": [{"text": "hi"}]}
    assert body["contents"][1] == {"role": "user", "parts": [{"text": "result"}]}
    assert body["contents"][2] == {"role": "model", "parts": [{"text": "done"}]}
    assert body["generationConfig"] == {"maxOutputTokens": 256, "temperature": 0.5}
    assert "tools" in body


def test_bedrock_body_flattens_blocks_and_skips_the_system_turn() -> None:
    client = client_for(provider(ProviderType.AWS_BEDROCK))
    body = client._build_bedrock_body(
        "be terse",
        [
            {"role": "system", "content": "inline system"},
            {"role": "user", "content": [{"type": "text", "text": "hi"}]},
            {"role": "assistant", "content": "done"},
        ],
        TOOLS,
        128,
        0.2,
    )

    assert body["system"] == "be terse"
    assert body["messages"] == [
        {"role": "user", "content": [{"text": "hi"}]},
        {"role": "assistant", "content": [{"text": "done"}]},
    ]
    assert body["temperature"] == 0.2
    assert "tools" in body


def test_cohere_body_sends_the_last_turn_as_the_message() -> None:
    client = client_for(provider(ProviderType.COHERE))
    body = client._build_cohere_body(
        "model-x",
        "be terse",
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": [{"type": "text", "text": "answer"}]},
        ],
        TOOLS,
        64,
        0.7,
    )

    assert body["preamble"] == "be terse"
    assert body["message"] == "answer"
    assert body["chat_history"] == [{"role": "USER", "message": "hi"}]
    assert body["tools"][0]["type"] == "function"


def test_cohere_body_without_messages_is_still_valid() -> None:
    client = client_for(provider(ProviderType.COHERE))
    body = client._build_cohere_body("model-x", "", [], None, 64, 0.7)
    assert body["message"] == ""
    assert body["chat_history"] == []


# --------------------------------------------------------------------------- #
# Parsers
# --------------------------------------------------------------------------- #


def test_parse_anthropic_response_reads_text_tool_use_and_cache_tokens() -> None:
    client = client_for(provider(ProviderType.ANTHROPIC))
    message, usage, _cost = client._parse_anthropic_response(
        {
            "model": "claude-test",
            "content": [
                {"type": "text", "text": "let me look"},
                {"type": "tool_use", "id": "toolu_1", "name": "Read", "input": {"file_path": "a"}},
            ],
            "stop_reason": "tool_use",
            "usage": {
                "input_tokens": 100,
                "output_tokens": 20,
                "cache_read_input_tokens": 60,
                "cache_creation_input_tokens": 10,
            },
        }
    )

    assert message.content == "let me look"
    assert message.tool_uses[0].id == "toolu_1"
    assert message.tool_uses[0].input == {"file_path": "a"}
    assert message.stop_reason == "tool_use"
    assert usage.cache_read_tokens == 60
    assert usage.cache_creation_tokens == 10


def test_parse_google_response_joins_parts_and_names_tool_calls() -> None:
    client = client_for(provider(ProviderType.GOOGLE))
    message, usage, _cost = client._parse_google_response(
        {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {"text": "hello "},
                            {"text": "world"},
                            {"functionCall": {"name": "Read", "args": {"file_path": "b"}}},
                        ]
                    },
                    "finishReason": "STOP",
                }
            ],
            "usageMetadata": {"promptTokenCount": 12, "candidatesTokenCount": 5},
        },
        "gemini-test",
    )

    assert message.content == "hello world"
    assert message.tool_uses[0].name == "Read"
    assert message.tool_uses[0].id.startswith("Read_")
    assert message.stop_reason == "STOP"
    assert usage.input_tokens == 12
    assert usage.output_tokens == 5


def test_parse_google_response_of_an_empty_candidate_list() -> None:
    client = client_for(provider(ProviderType.GOOGLE))
    message, usage, _cost = client._parse_google_response({}, "gemini-test")
    assert message.content == ""
    assert message.stop_reason is None
    assert usage.input_tokens == 0


def test_parse_bedrock_response_reads_tool_use_blocks() -> None:
    client = client_for(provider(ProviderType.AWS_BEDROCK))
    message, usage, _cost = client._parse_bedrock_response(
        {
            "output": {
                "message": {
                    "content": [
                        {"text": "checking"},
                        {"toolUse": {"toolUseId": "tu-1", "name": "Grep", "input": {"p": "x"}}},
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 9, "outputTokens": 4},
        },
        "bedrock-model",
    )

    assert message.content == "checking"
    assert message.tool_uses[0].id == "tu-1"
    assert message.stop_reason == "tool_use"
    assert usage.input_tokens == 9


def test_parse_cohere_response_reads_tool_calls_and_tokens() -> None:
    client = client_for(provider(ProviderType.COHERE))
    message, usage, _cost = client._parse_cohere_response(
        {
            "text": "done",
            "tool_calls": [{"name": "Read", "parameters": {"file_path": "c"}}],
            "finish_reason": "COMPLETE",
            "meta": {"tokens": {"input_tokens": 30, "output_tokens": 8}},
        },
        "command-r",
    )

    assert message.content == "done"
    assert message.tool_uses[0].name == "Read"
    assert message.tool_uses[0].input == {"file_path": "c"}
    assert usage.input_tokens == 30


# --------------------------------------------------------------------------- #
# Usage, cost and headers
# --------------------------------------------------------------------------- #


def test_openai_usage_reads_both_cache_shapes() -> None:
    client = client_for()
    openai_shape = client._parse_openai_usage(
        {"prompt_tokens": 50, "completion_tokens": 5, "prompt_tokens_details": {"cached_tokens": 40}}
    )
    gateway_shape = client._parse_openai_usage(
        {"prompt_tokens": 10, "completion_tokens": 1, "cache_read_input_tokens": 7}
    )
    empty = client._parse_openai_usage({})

    assert (openai_shape.input_tokens, openai_shape.cache_read_tokens) == (50, 40)
    assert gateway_shape.cache_read_tokens == 7
    assert (empty.input_tokens, empty.output_tokens) == (0, 0)


def test_usage_with_null_fields_does_not_crash() -> None:
    client = client_for()
    usage = client._parse_openai_usage(
        {"prompt_tokens": None, "completion_tokens": None, "prompt_tokens_details": None}
    )
    assert usage.input_tokens == 0
    assert usage.output_tokens == 0


def test_cost_is_zero_for_a_local_endpoint() -> None:
    client = client_for(provider(base_url="http://127.0.0.1:8088/v1", is_local=True))
    cost = client._calculate_cost({"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, "x")
    assert cost.total_cost == 0


def test_cost_uses_the_price_table_for_a_known_model() -> None:
    client = client_for(provider(ProviderType.OPENAI, base_url="https://api.openai.com/v1"))
    cost = client._calculate_cost(
        {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}, "gpt-4o-mini"
    )
    assert cost.input_cost > 0
    assert cost.output_cost > 0


@pytest.mark.parametrize(
    "provider_type,header_name",
    [
        (ProviderType.ANTHROPIC, "x-api-key"),
        (ProviderType.AZURE_OPENAI, "api-key"),
        (ProviderType.GOOGLE, "x-goog-api-key"),
        (ProviderType.OPENAI, "Authorization"),
        (ProviderType.COHERE, "Authorization"),
    ],
)
def test_headers_use_the_providers_auth_convention(
    provider_type: ProviderType, header_name: str
) -> None:
    client = client_for(provider(provider_type))
    headers = client._build_headers(provider(provider_type))
    assert header_name in headers
    assert headers[header_name]


def test_local_provider_needs_no_key() -> None:
    local = provider(base_url="http://127.0.0.1:8088/v1", api_key="", is_local=True)
    headers = client_for(local)._build_headers(local)
    assert "Authorization" not in headers


def test_missing_key_for_a_cloud_provider_is_an_error() -> None:
    cloud = provider(ProviderType.OPENAI, api_key="")
    with pytest.raises(ValueError, match="API key required"):
        client_for(cloud)._build_headers(cloud)


def test_missing_key_for_a_localhost_url_is_tolerated() -> None:
    # A server reached over loopback is trusted even when it was not marked local.
    loopback = provider(ProviderType.OPENAI_COMPATIBLE, base_url="http://localhost:9000/v1", api_key="")
    headers = client_for(loopback)._build_headers(loopback)
    assert headers["Authorization"] == "Bearer not-needed"


def test_cache_markers_are_skipped_for_a_named_non_anthropic_family() -> None:
    from openlaoke.core.cache_guard import CacheGuard

    messages = [{"role": "user", "content": "hi"}]
    assert CacheGuard.apply_cache_markers(messages, provider_type="openai") == [
        {"role": "user", "content": "hi"}
    ]
    # Anthropic keeps the marker behaviour.
    marked = CacheGuard.apply_cache_markers(
        [{"role": "user", "content": "hi"}], provider_type="anthropic"
    )
    assert isinstance(marked[0]["content"], list)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://api.deepseek.com/v1", ProviderType.OPENAI_COMPATIBLE),
        ("https://api.anthropic.com", ProviderType.ANTHROPIC),
        ("https://claude-proxy.example.com/v1", ProviderType.ANTHROPIC),
        ("https://api.openai.com/v1", ProviderType.OPENAI),
        ("https://openrouter.ai/api/v1", ProviderType.OPENAI),
        ("http://localhost:11434/v1", ProviderType.OLLAMA),
        ("http://127.0.0.1:1234/v1", ProviderType.LM_STUDIO),
        ("http://lm-studio.local/v1", ProviderType.LM_STUDIO),
        ("https://api.mistral.ai/v1", ProviderType.MISTRAL),
        ("https://api.groq.com/openai/v1", ProviderType.GROQ),
        ("https://generativelanguage.googleapis.com/v1beta", ProviderType.GOOGLE),
        ("https://api.x.ai/v1", ProviderType.XAI),
        ("http://unknown.example.com/v1", ProviderType.OPENAI_COMPATIBLE),
        # Matching is case-insensitive because the URL is lowercased first.
        ("HTTPS://API.OPENAI.COM/v1", ProviderType.OPENAI),
    ],
)
def test_detect_provider_type_from_a_base_url(url: str, expected: ProviderType) -> None:
    assert MultiProviderClient.detect_provider_type(url) == expected


def test_is_local_url_is_exported_consistently() -> None:
    assert _is_local_url("http://127.0.0.1:1/v1") is True


def test_openai_conversion_keeps_a_native_tool_message() -> None:
    client = client_for()
    converted = client._convert_messages_for_provider(
        [
            {"role": "user", "content": "hi"},
            {"role": "tool", "tool_call_id": "c1", "content": "output"},
        ],
        ProviderType.OPENAI,
    )
    assert converted[1] == {"role": "tool", "tool_call_id": "c1", "content": "output"}


def test_openai_body_keeps_a_non_default_temperature() -> None:
    client = client_for(provider(ProviderType.OPENAI))
    body = client._build_openai_body(
        "m", [{"role": "user", "content": "hi"}], None, 100, 0.25
    )
    assert body["temperature"] == 0.25


def test_reasoning_only_reply_becomes_the_visible_answer() -> None:
    client = client_for()
    message, _usage, _cost = client._parse_openai_response(
        {
            "choices": [
                {
                    "message": {"content": "", "reasoning_content": "  the answer is 42  "},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 1, "completion_tokens": 9},
        }
    )
    assert message.content == "the answer is 42"
    # The reasoning stays available as thinking as well; the caller decides
    # whether to show it.
    assert message.thinking.strip() == "the answer is 42"
    assert message.stop_reason == "length"


def test_empty_openai_response_is_parsed_leniently() -> None:
    client = client_for()
    message, usage, _cost = client._parse_openai_response({"choices": []})
    assert message.content == ""
    assert message.stop_reason is None
    assert usage.input_tokens == 0


@pytest.mark.parametrize(
    "provider_type,env_var",
    [
        (ProviderType.ANTHROPIC, "ANTHROPIC_API_KEY"),
        (ProviderType.OPENAI, "OPENAI_API_KEY"),
        (ProviderType.DEEPSEEK, "DEEPSEEK_API_KEY"),
        (ProviderType.OLLAMA_CLOUD, "OLLAMA_API_KEY"),
        (ProviderType.MINIMAX, "MINIMAX_API_KEY"),
        (ProviderType.ALIYUN_CODING_PLAN, "ALIYUN_API_KEY"),
        (ProviderType.AZURE_OPENAI, "AZURE_OPENAI_API_KEY"),
        (ProviderType.GOOGLE, "GOOGLE_API_KEY"),
        (ProviderType.GOOGLE_VERTEX, "GOOGLE_APPLICATION_CREDENTIALS"),
        (ProviderType.AWS_BEDROCK, "AWS_ACCESS_KEY_ID"),
        (ProviderType.XAI, "XAI_API_KEY"),
        (ProviderType.MISTRAL, "MISTRAL_API_KEY"),
        (ProviderType.GROQ, "GROQ_API_KEY"),
        (ProviderType.CEREBRAS, "CEREBRAS_API_KEY"),
        (ProviderType.COHERE, "COHERE_API_KEY"),
        (ProviderType.DEEPINFRA, "DEEPINFRA_API_KEY"),
        (ProviderType.TOGETHERAI, "TOGETHERAI_API_KEY"),
        (ProviderType.PERPLEXITY, "PERPLEXITY_API_KEY"),
        (ProviderType.OPENROUTER, "OPENROUTER_API_KEY"),
        (ProviderType.GITHUB_COPILOT, "GITHUB_TOKEN"),
        (ProviderType.OPENCODE, "OPENCODE_API_KEY"),
        (ProviderType.OPENAI_COMPATIBLE, "OPENAI_API_KEY"),
    ],
)
def test_api_key_falls_back_to_the_providers_env_variable(
    provider_type: ProviderType, env_var: str, monkeypatch
) -> None:
    monkeypatch.setenv(env_var, "from-env")
    client = client_for()
    assert client._get_api_key(provider(provider_type, api_key="")) == "from-env"
    # A configured key wins over the environment.
    assert client._get_api_key(provider(provider_type, api_key="explicit")) == "explicit"


@pytest.mark.parametrize(
    "provider_type,env_var,default",
    [
        (ProviderType.ANTHROPIC, "ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        (ProviderType.OPENAI, "OPENAI_BASE_URL", "https://api.openai.com/v1"),
        (ProviderType.DEEPSEEK, "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        (ProviderType.OLLAMA_CLOUD, "OLLAMA_CLOUD_BASE_URL", "https://ollama.com/v1"),
        (ProviderType.OPENROUTER, "OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"),
        (ProviderType.GROQ, "GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    ],
)
def test_base_url_uses_the_provider_env_override(
    provider_type: ProviderType, env_var: str, default: str, monkeypatch
) -> None:
    client = client_for()
    monkeypatch.delenv(env_var, raising=False)
    assert client._get_base_url(provider(provider_type, base_url="")) == default

    monkeypatch.setenv(env_var, "https://proxy.example.com/v1")
    assert client._get_base_url(provider(provider_type, base_url="")) == "https://proxy.example.com/v1"

    # An explicit base_url always wins.
    assert (
        client._get_base_url(provider(provider_type, base_url="https://explicit/v1"))
        == "https://explicit/v1"
    )


# --------------------------------------------------------------------------- #
# per-provider defaults, headers and client plumbing
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "provider_type,expected",
    [
        (ProviderType.OPENAI, "https://api.openai.com/v1"),
        (ProviderType.DEEPSEEK, "https://api.deepseek.com/v1"),
        (ProviderType.OLLAMA_CLOUD, "https://ollama.com/v1"),
        (ProviderType.MINIMAX, "https://api.minimaxi.com/v1"),
        (ProviderType.ALIYUN_CODING_PLAN, "https://coding.dashscope.aliyuncs.com/v1"),
        (ProviderType.GOOGLE, "https://generativelanguage.googleapis.com/v1beta"),
        (ProviderType.XAI, "https://api.x.ai/v1"),
        (ProviderType.MISTRAL, "https://api.mistral.ai/v1"),
        (ProviderType.GROQ, "https://api.groq.com/openai/v1"),
        (ProviderType.CEREBRAS, "https://api.cerebras.ai/v1"),
        (ProviderType.COHERE, "https://api.cohere.ai/v2"),
        (ProviderType.DEEPINFRA, "https://api.deepinfra.com/v1/openai"),
        (ProviderType.TOGETHERAI, "https://api.together.xyz/v1"),
        (ProviderType.PERPLEXITY, "https://api.perplexity.ai"),
        (ProviderType.OPENROUTER, "https://openrouter.ai/api/v1"),
        (ProviderType.GITHUB_COPILOT, "https://api.githubcopilot.com"),
        (ProviderType.OPENCODE, "https://opencode.ai/zen/v1"),
        (ProviderType.OPENAI_COMPATIBLE, "https://api.openai.com/v1"),
    ],
)
def test_each_provider_falls_back_to_its_own_default_url(
    provider_type: ProviderType, expected: str
) -> None:
    client = client_for()
    bare = provider(provider_type, base_url="")

    assert client._get_base_url(bare) == expected


def test_a_bare_base_url_env_var_overrides_the_default(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_BASE_URL", "https://proxy.internal/groq")
    client = client_for()

    assert client._get_base_url(provider(ProviderType.GROQ, base_url="")) == (
        "https://proxy.internal/groq"
    )


def test_an_explicit_base_url_beats_every_default(monkeypatch) -> None:
    monkeypatch.setenv("GROQ_BASE_URL", "https://proxy.internal/groq")
    client = client_for()

    assert client._get_base_url(provider(ProviderType.GROQ)) == "https://api.example.com/v1"


def test_headers_carry_the_key(monkeypatch) -> None:
    client = client_for()

    headers = client._build_headers(provider(ProviderType.OPENAI))

    assert headers["Authorization"] == "Bearer sk-test"
    assert headers["Content-Type"] == "application/json"


def test_the_user_agent_can_be_overridden_by_env(monkeypatch) -> None:
    from openlaoke.core.multi_provider_api import _default_http_headers

    monkeypatch.setenv("OPENLAOKE_HTTP_USER_AGENT", "openlaoke-test/1")

    assert _default_http_headers()["User-Agent"] == "openlaoke-test/1"


def test_a_required_api_key_is_enforced() -> None:
    client = client_for()

    with pytest.raises(ValueError, match="API key required"):
        client._build_headers(provider(ProviderType.COHERE, api_key=""))


def test_the_http_client_is_built_once_and_closed(monkeypatch) -> None:
    client = client_for()
    created: list[Any] = []

    import httpx

    real_client = httpx.AsyncClient

    class Recorder(real_client):  # type: ignore[misc, valid-type]
        def __init__(self, **kwargs: Any) -> None:
            created.append(kwargs)
            super().__init__(**kwargs)

    monkeypatch.setattr("openlaoke.core.multi_provider_api.httpx.AsyncClient", Recorder)

    first = client._get_client()
    second = client._get_client()

    assert first is second
    assert len(created) == 1
    assert created[0]["trust_env"] is False

    import asyncio

    asyncio.run(client.close())
    assert client._client is None


def test_an_empty_proxy_setting_means_no_proxy(monkeypatch) -> None:
    client = MultiProviderClient(
        MultiProviderConfig(providers={"main": provider()}, active_provider="main"),
        proxy="",
    )
    seen: list[Any] = []

    import httpx

    real_client = httpx.AsyncClient

    class Recorder(real_client):  # type: ignore[misc, valid-type]
        def __init__(self, **kwargs: Any) -> None:
            seen.append(kwargs.get("proxy"))
            super().__init__(**kwargs)

    monkeypatch.setattr("openlaoke.core.multi_provider_api.httpx.AsyncClient", Recorder)

    client._get_client()

    assert seen == [None]


def test_retry_backoff_only_covers_retryable_statuses() -> None:
    client = client_for()

    assert client._retry_with_backoff(404, 0) == (False, 0)
    assert client._retry_with_backoff(200, 0) == (False, 0)

    retry, delay = client._retry_with_backoff(429, 0)
    assert retry is True
    assert delay > 0

    _retry, capped = client._retry_with_backoff(429, 9)
    # The base delay is capped at 30s; the jitter added on top can push the
    # actual sleep slightly past it.
    assert 30.0 <= capped <= 30.0 * 1.3
    assert capped >= delay


def test_health_check_reports_each_provider_state(monkeypatch) -> None:
    import asyncio

    import httpx

    config = MultiProviderConfig(
        providers={
            "local": provider(ProviderType.OLLAMA, is_local=True),
            "unconfigured": provider(ProviderType.OPENAI, api_key=""),
            "good": provider(ProviderType.OPENAI, base_url="https://ok.example.com/v1"),
            "broken": provider(ProviderType.OPENAI, base_url="https://bad.example.com/v1"),
        },
        active_provider="good",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if "bad.example.com" in str(request.url):
            raise httpx.ConnectError("refused")
        return httpx.Response(200, json={"data": []})

    real_client = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    monkeypatch.setattr("openlaoke.core.multi_provider_api.httpx.AsyncClient", factory)
    monkeypatch.setenv("OPENAI_API_KEY", "")

    results = asyncio.run(MultiProviderClient.health_check(config))

    assert results["local"]["ok"] is True
    assert results["local"]["note"] == "local"
    assert results["unconfigured"]["note"] == "not configured"
    assert results["good"]["ok"] is True
    assert results["good"]["status"] == 200
    assert results["broken"]["ok"] is False
    assert "refused" in results["broken"]["error"]


def test_health_check_treats_a_keyless_opencode_provider_as_healthy(monkeypatch) -> None:
    import asyncio

    import httpx

    config = MultiProviderConfig(
        providers={
            "opencode": provider(
                ProviderType.OPENCODE, api_key="", base_url="https://oc.example.com/v1"
            )
        },
        active_provider="opencode",
    )
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"data": [{"id": "m"}]})

    real_client = httpx.AsyncClient

    def factory(**kwargs: Any) -> httpx.AsyncClient:
        kwargs["transport"] = httpx.MockTransport(handler)
        return real_client(**kwargs)

    monkeypatch.setattr("openlaoke.core.multi_provider_api.httpx.AsyncClient", factory)

    results = asyncio.run(MultiProviderClient.health_check(config))

    # OpenCode needs no key, so it must be probed rather than written off.
    assert results["opencode"]["ok"] is True
    assert results["opencode"]["status"] == 200
    assert len(seen) == 1
    assert "authorization" not in {k.lower() for k in seen[0].headers}
    assert seen[0].headers["content-type"] == "application/json"


def test_google_and_cohere_bodies_drop_system_turns() -> None:
    client = client_for()

    conversation = [
        {"role": "system", "content": "ignored"},
        {"role": "user", "content": "first"},
        {"role": "user", "content": "hi"},
    ]
    google = client._build_google_body("system prompt", conversation, None, 64, 1.0)
    cohere = client._build_cohere_body("m", "system prompt", conversation, None, 64, 1.0)

    assert [c["role"] for c in google["contents"]] == ["user", "user"]
    # Cohere sends the last turn as "message" and the rest as chat_history.
    assert [c["role"] for c in cohere["chat_history"]] == ["USER"]
    assert cohere["message"] == "hi"


def test_cohere_tool_conversion_accepts_both_shapes() -> None:
    client = client_for()

    converted = client._convert_tools_to_cohere_format(
        [
            {"type": "function", "function": {"name": "a", "description": "d", "parameters": {}}},
            {"name": "b", "description": "e", "input_schema": {"type": "object"}},
        ]
    )

    assert [tool["function"]["name"] for tool in converted] == ["a", "b"]
