"""Tests for openlaoke.core.anti_stall — ported from sekrun."""

from __future__ import annotations

from openlaoke.core.anti_stall import NUDGE_MESSAGE, should_continue_for_promised_tool_use


class TestAntiStall:
    def test_empty_returns_false(self):
        assert should_continue_for_promised_tool_use("") is False
        assert should_continue_for_promised_tool_use("   ") is False

    def test_none_returns_false(self):
        assert should_continue_for_promised_tool_use(None) is False  # type: ignore[arg-type]

    # Chinese patterns
    def test_chinese_scan_project(self):
        assert should_continue_for_promised_tool_use("让我先扫描一下项目结构，然后开始修改") is True

    def test_chinese_next_step(self):
        assert should_continue_for_promised_tool_use("接下来我会执行修改操作") is True

    def test_chinese_analysis_complete(self):
        assert should_continue_for_promised_tool_use("分析完毕，接下来开始实现") is True

    def test_chinese_plan_intro(self):
        assert should_continue_for_promised_tool_use("我的计划如下：第一步读取文件") is True

    def test_chinese_review_code(self):
        assert should_continue_for_promised_tool_use("我先看一下代码结构") is True

    def test_chinese_check_project(self):
        assert should_continue_for_promised_tool_use("先检查一下项目结构和实现") is True

    # English patterns
    def test_english_let_me_analyze(self):
        assert should_continue_for_promised_tool_use("Let me analyze the codebase first.") is True

    def test_english_here_is_plan(self):
        assert should_continue_for_promised_tool_use("Here is my plan for the changes.") is True

    def test_english_phase1(self):
        assert (
            should_continue_for_promised_tool_use("Phase 1: read files and understand structure.")
            is True
        )

    def test_english_examine(self):
        assert (
            should_continue_for_promised_tool_use("I will examine the project structure.") is True
        )

    def test_english_let_me_review(self):
        assert (
            should_continue_for_promised_tool_use("Let me review the relevant files first.") is True
        )

    def test_english_step1(self):
        assert should_continue_for_promised_tool_use("Step 1: Read the main file") is True

    # No-plan responses should NOT trigger
    def test_simple_answer_no_trigger(self):
        assert should_continue_for_promised_tool_use("The answer is 42.") is False

    def test_code_output_no_trigger(self):
        assert (
            should_continue_for_promised_tool_use(
                "Here is the fixed code:\n```python\nprint('hello')\n```"
            )
            is False
        )

    def test_greeting_no_trigger(self):
        assert should_continue_for_promised_tool_use("Hello, how can I help you today?") is False

    def test_single_word_no_trigger(self):
        assert should_continue_for_promised_tool_use("Done") is False

    def test_short_no_trigger(self):
        assert should_continue_for_promised_tool_use("OK I understand.") is False

    # Fallback: long text ending with proceed
    def test_long_text_ending_proceed(self):
        long_text = "This is a very long analysis. " * 30 + "\nNow let us proceed."
        assert should_continue_for_promised_tool_use(long_text) is True

    def test_long_text_ending_continue(self):
        long_text = (
            "A detailed breakdown of what needs to be done.\n" * 20
            + "\nLet's continue with the implementation."
        )
        assert should_continue_for_promised_tool_use(long_text) is True

    def test_nudge_message_is_string(self):
        assert isinstance(NUDGE_MESSAGE, str)
        assert len(NUDGE_MESSAGE) > 10
        assert "Proceed" in NUDGE_MESSAGE
