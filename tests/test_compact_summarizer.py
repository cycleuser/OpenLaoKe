"""Tests for MessageSummarizer and the inline compaction prompt builder.

A fake provider client records the request so we can assert on what the
summariser actually sends; no network is used.
"""

from __future__ import annotations

import pytest

from openlaoke.core.compact.summarizer import (
    INLINE_COMPACTION_PREFIX,
    SUMMARY_SYSTEM_PROMPT,
    MessageSummarizer,
    SummaryConfig,
    SummaryResult,
    build_inline_compaction_messages,
)
from openlaoke.types.core_types import (
    AssistantMessage,
    CostInfo,
    MessageRole,
    SystemMessage,
    TokenUsage,
    UserMessage,
)


def user(text: str) -> UserMessage:
    return UserMessage(role=MessageRole.USER, content=text)


def assistant(text: str, tool_uses=None, stop_reason=None) -> AssistantMessage:
    return AssistantMessage(
        role=MessageRole.ASSISTANT, content=text, tool_uses=tool_uses or [], stop_reason=stop_reason
    )


def system(text: str, subtype: str = "info") -> SystemMessage:
    return SystemMessage(role=MessageRole.SYSTEM, content=text, subtype=subtype)


class FakeClient:
    """Records send_message kwargs and returns a canned completion."""

    def __init__(self, content: str = "SUMMARY TEXT", output_tokens: int = 42, model: str = "active-model"):
        self.content = content
        self.output_tokens = output_tokens
        self.calls: list[dict] = []
        self.config = type("Cfg", (), {"get_active_model": lambda _self: model})()

    async def send_message(self, **kwargs):
        self.calls.append(kwargs)
        return (
            AssistantMessage(role=MessageRole.ASSISTANT, content=self.content),
            TokenUsage(input_tokens=100, output_tokens=self.output_tokens),
            CostInfo(),
        )


# --------------------------------------------------------------------------- #
# SummaryResult / SummaryConfig
# --------------------------------------------------------------------------- #


def test_summary_result_compression_ratio() -> None:
    result = SummaryResult(summary="s", original_tokens=1000, summary_tokens=250, messages_summarized=2, messages_preserved=1)
    assert result.compression_ratio == pytest.approx(0.75)


def test_summary_result_ratio_zero_without_original_tokens() -> None:
    result = SummaryResult(summary="", original_tokens=0, summary_tokens=0, messages_summarized=0, messages_preserved=0)
    assert result.compression_ratio == 0.0


def test_system_prompt_defaults_and_override() -> None:
    assert SummaryConfig().get_system_prompt() == SUMMARY_SYSTEM_PROMPT
    assert SummaryConfig(custom_prompt="be terse").get_system_prompt() == "be terse"


# --------------------------------------------------------------------------- #
# Token estimation and formatting
# --------------------------------------------------------------------------- #


def test_estimate_tokens_is_four_chars_per_token() -> None:
    summarizer = MessageSummarizer(FakeClient())
    assert summarizer.estimate_tokens("a" * 400) == 100
    assert summarizer.estimate_tokens("") == 0


def test_estimate_message_tokens_uses_extracted_content() -> None:
    summarizer = MessageSummarizer(FakeClient())
    assert summarizer.estimate_message_tokens(user("b" * 800)) == 200
    # System messages carry their content the same way.
    assert summarizer.estimate_message_tokens(system("c" * 400)) == 100


def test_format_messages_for_summary_numbers_and_labels_role() -> None:
    summarizer = MessageSummarizer(FakeClient())
    text = summarizer.format_messages_for_summary([user("hello"), assistant("hi there")])
    assert text == "[0] user: hello\n\n[1] assistant: hi there"


# --------------------------------------------------------------------------- #
# summarize_messages
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_summarize_empty_messages_short_circuits() -> None:
    client = FakeClient()
    summarizer = MessageSummarizer(client)
    result = await summarizer.summarize_messages([])
    assert result.summary == ""
    assert result.original_tokens == 0
    assert result.messages_summarized == 0
    assert client.calls == []


@pytest.mark.asyncio
async def test_summarize_sends_system_prompt_and_formatted_conversation() -> None:
    client = FakeClient(content="the brief", output_tokens=17)
    summarizer = MessageSummarizer(client)
    messages = [user("what is up"), assistant("not much")]
    result = await summarizer.summarize_messages(messages)

    assert result.summary == "the brief"
    assert result.summary_tokens == 17
    assert result.messages_summarized == 2
    call = client.calls[0]
    assert call["system_prompt"] == SUMMARY_SYSTEM_PROMPT
    assert "[0] user: what is up" in call["messages"][0]["content"]
    assert call["max_tokens"] == SummaryConfig().max_summary_tokens
    assert call["temperature"] == SummaryConfig().summary_temperature


@pytest.mark.asyncio
async def test_summarize_uses_explicit_summary_model() -> None:
    client = FakeClient()
    summarizer = MessageSummarizer(client, SummaryConfig(summary_model="cheap-model"))
    await summarizer.summarize_messages([user("x")])
    assert client.calls[0]["model"] == "cheap-model"


@pytest.mark.asyncio
async def test_summarize_falls_back_to_the_active_model() -> None:
    client = FakeClient(model="active-model")
    summarizer = MessageSummarizer(client)
    await summarizer.summarize_messages([user("x")])
    assert client.calls[0]["model"] == "active-model"


@pytest.mark.asyncio
async def test_summarize_honours_custom_prompt_and_target_tokens() -> None:
    client = FakeClient()
    summarizer = MessageSummarizer(client, SummaryConfig(custom_prompt="custom!"))
    await summarizer.summarize_messages([user("x")], target_tokens=123)
    # max_tokens is still the configured summary budget, not the target.
    assert client.calls[0]["system_prompt"] == "custom!"
    assert client.calls[0]["max_tokens"] == SummaryConfig().max_summary_tokens


@pytest.mark.asyncio
async def test_summarize_reports_original_tokens_of_input() -> None:
    client = FakeClient()
    summarizer = MessageSummarizer(client)
    result = await summarizer.summarize_messages([user("d" * 400), user("e" * 400)])
    assert result.original_tokens == 200
    assert result.messages_preserved == 0


# --------------------------------------------------------------------------- #
# Preservation policy
# --------------------------------------------------------------------------- #


def test_recent_messages_are_always_preserved() -> None:
    summarizer = MessageSummarizer(FakeClient(), SummaryConfig(preserve_recent_messages=2))
    total = 6
    assert summarizer.should_preserve_message(assistant("plain"), 3, total) is False
    assert summarizer.should_preserve_message(assistant("plain"), 4, total) is True
    assert summarizer.should_preserve_message(assistant("plain"), 5, total) is True


def test_user_queries_are_preserved_by_default_and_configurable() -> None:
    keeping = MessageSummarizer(FakeClient(), SummaryConfig(preserve_recent_messages=0))
    assert keeping.should_preserve_message(user("question"), 0, 10) is True

    dropping = MessageSummarizer(
        FakeClient(), SummaryConfig(preserve_recent_messages=0, preserve_user_queries=False)
    )
    assert dropping.should_preserve_message(user("question"), 0, 10) is False


def test_assistant_tool_calls_are_preserved_by_default_and_configurable() -> None:
    keeping = MessageSummarizer(FakeClient(), SummaryConfig(preserve_recent_messages=0))
    assert keeping.should_preserve_message(assistant("call", tool_uses=[object()]), 0, 10) is True
    # Plain assistant text is not preserved.
    assert keeping.should_preserve_message(assistant("done"), 0, 10) is False

    dropping = MessageSummarizer(
        FakeClient(), SummaryConfig(preserve_recent_messages=0, preserve_tool_results=False)
    )
    assert dropping.should_preserve_message(assistant("call", tool_uses=[object()]), 0, 10) is False


def test_error_and_warning_messages_are_preserved() -> None:
    summarizer = MessageSummarizer(FakeClient(), SummaryConfig(preserve_recent_messages=0))
    assert summarizer.should_preserve_message(system("bad", subtype="error"), 0, 10) is True
    assert summarizer.should_preserve_message(system("hmm", subtype="warning"), 0, 10) is True
    assert summarizer.should_preserve_message(system("ok", subtype="info"), 0, 10) is False


def test_split_messages_partitions_in_order() -> None:
    summarizer = MessageSummarizer(FakeClient(), SummaryConfig(preserve_recent_messages=1))
    messages = [
        user("q1"),
        assistant("a1"),
        system("error", subtype="error"),
        user("q2"),
    ]
    to_summarize, to_preserve = summarizer.split_messages(messages)
    # Preserved: the error, all user queries, and the single recent message.
    assert to_preserve == [messages[0], messages[2], messages[3]]
    assert to_summarize == [messages[1]]


# --------------------------------------------------------------------------- #
# summarize_with_preserve
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_summarize_with_preserve_short_circuits_when_all_preserved() -> None:
    client = FakeClient()
    summarizer = MessageSummarizer(client, SummaryConfig(preserve_recent_messages=10))
    messages = [user("q1"), user("q2")]
    result = await summarizer.summarize_with_preserve(messages)
    assert result.summary == ""
    assert result.messages_summarized == 0
    assert result.messages_preserved == 2
    assert client.calls == []  # no LLM call needed


@pytest.mark.asyncio
async def test_summarize_with_preserve_combines_summary_and_preserved_tokens() -> None:
    client = FakeClient(content="the brief", output_tokens=10)
    summarizer = MessageSummarizer(client, SummaryConfig(preserve_recent_messages=1))
    messages = [assistant("a" * 400), assistant("b" * 400)]
    result = await summarizer.summarize_with_preserve(messages)
    assert result.summary == "the brief"
    assert result.messages_summarized == 1
    assert result.messages_preserved == 1
    # Only the old message is sent for summarisation.
    assert "[0] assistant: " + "a" * 400 in client.calls[0]["messages"][0]["content"]
    assert "b" * 400 not in client.calls[0]["messages"][0]["content"]
    assert result.original_tokens == 200  # 100 summarised + 100 preserved
    assert result.summary_tokens == 110  # 10 output + 100 preserved


def test_create_summary_message_is_a_compact_system_message() -> None:
    summarizer = MessageSummarizer(FakeClient())
    message = summarizer.create_summary_message("the brief")
    assert isinstance(message, SystemMessage)
    assert message.subtype == "compact"
    assert message.role == MessageRole.SYSTEM
    assert message.content == "[Context Summary]\nthe brief"


# --------------------------------------------------------------------------- #
# build_inline_compaction_messages
# --------------------------------------------------------------------------- #


def convo(n: int) -> list[dict]:
    return [{"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(n)]


def test_inline_compaction_leaves_empty_and_short_histories_untouched() -> None:
    assert build_inline_compaction_messages([]) == []
    short = convo(4)  # keep_count floors at 4, so nothing to compact
    assert build_inline_compaction_messages(short) == short


def test_inline_compaction_inserts_instruction_before_recent_window() -> None:
    messages = convo(20)
    result = build_inline_compaction_messages(messages)
    assert len(result) == 21
    injected = [m for m in result if m.get("content") == INLINE_COMPACTION_PREFIX]
    assert len(injected) == 1
    assert injected[0]["system_injected"] is True
    assert injected[0]["role"] == "user"
    # keep_count = max(4, 20 // 4) = 5, so the marker precedes the last 5.
    assert result.index(injected[0]) == 15
    assert [m["content"] for m in result[16:]] == [f"m{i}" for i in range(15, 20)]


def test_inline_compaction_does_not_mutate_the_input_list() -> None:
    messages = convo(20)
    snapshot = list(messages)
    build_inline_compaction_messages(messages)
    assert messages == snapshot


def test_inline_compaction_respects_target_compact_count() -> None:
    messages = convo(20)
    # target smaller than the default set: still only one injection point.
    result = build_inline_compaction_messages(messages, target_compact_count=2)
    assert len(result) == 21
    assert sum(1 for m in result if m.get("system_injected")) == 1


def test_inline_compaction_target_covering_everything_keeps_recent_window() -> None:
    messages = convo(8)
    # compact_count is capped at len - keep_count, so recent messages survive.
    result = build_inline_compaction_messages(messages, target_compact_count=99)
    assert len(result) == 9
    assert result[-1]["content"] == "m7"
