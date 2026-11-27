"""Tests for tiered prompt assembly: required blocks survive a tight budget."""

from __future__ import annotations

from openlaoke.core.prompt_budget import (
    OPTIONAL,
    REQUIRED,
    AssemblyReport,
    PromptBlock,
    assemble,
    budget_for_window,
)
from openlaoke.core.state import create_app_state
from openlaoke.core.system_prompt import assemble_system_prompt, build_system_prompt


def test_everything_fits_when_no_budget_is_given():
    blocks = [PromptBlock("a", "alpha", REQUIRED), PromptBlock("b", "beta", OPTIONAL)]

    text, report = assemble(blocks)

    assert text == "alpha\n\nbeta"
    assert report.included == ["a", "b"]
    assert report.dropped == []
    assert report.budget is None
    assert report.used_tokens > 0


def test_an_optional_block_is_dropped_before_a_required_one():
    blocks = [
        PromptBlock("rules", "r" * 400, REQUIRED),
        PromptBlock("context", "c" * 4000, OPTIONAL),
    ]

    text, report = assemble(blocks, max_tokens=200)

    assert text.startswith("r" * 400)
    assert "c" not in text
    assert report.dropped == ["context"]
    assert report.included == ["rules"]
    assert report.over_budget is False


def test_required_blocks_are_kept_even_when_they_alone_blow_the_budget():
    blocks = [PromptBlock("rules", "r" * 4000, REQUIRED)]

    text, report = assemble(blocks, max_tokens=50)

    assert "r" * 4000 in text
    assert report.over_budget is True
    assert report.dropped == []


def test_a_single_oversized_optional_block_does_not_evict_the_next_one():
    blocks = [
        PromptBlock("rules", "rules", REQUIRED),
        PromptBlock("huge", "h" * 40_000, OPTIONAL),
        PromptBlock("small", "keep me", OPTIONAL),
    ]

    text, report = assemble(blocks, max_tokens=200)

    assert "keep me" in text
    assert report.included == ["rules", "small"]
    assert report.dropped == ["huge"]


def test_empty_blocks_are_skipped_entirely():
    blocks = [PromptBlock("a", "", REQUIRED), PromptBlock("b", "text", OPTIONAL)]

    text, report = assemble(blocks)

    assert text == "text"
    assert report.included == ["b"]


def test_a_report_can_be_reused_by_the_caller():
    report = AssemblyReport(budget=10)
    assemble([PromptBlock("a", "alpha", REQUIRED)], max_tokens=10, report=report)

    assert report.budget == 10
    assert report.included == ["a"]
    assert report.dropped_required is False
    assert "Included: a" in report.render()


def test_budget_for_window_ignores_unknown_windows():
    assert budget_for_window(None) is None
    assert budget_for_window(0) is None
    assert budget_for_window(8192) == 2048
    assert budget_for_window(100, floor=512) == 512


def test_the_system_prompt_keeps_its_rules_under_a_tight_budget(tmp_path):
    state = create_app_state(cwd=str(tmp_path))
    state.session_config.system_prompt_suffix = "Always answer in haiku."

    # The static rules alone cost ~550 tokens, so this is a genuinely tight
    # budget: the optional context block cannot fit, the rules must.
    text, report = assemble_system_prompt(state, "x" * 5000, max_tokens=700)

    from openlaoke.core.cache_guard import SYSTEM_PROMPT_STATIC

    assert text.startswith(SYSTEM_PROMPT_STATIC[:80])
    assert "Always answer in haiku." in text
    assert "context" in report.dropped
    assert report.over_budget is False


def test_the_system_prompt_is_unchanged_without_a_budget(tmp_path):
    state = create_app_state(cwd=str(tmp_path))

    unbudgeted = build_system_prompt(state, [])
    budgeted, report = assemble_system_prompt(state, max_tokens=None)

    assert unbudgeted == budgeted
    assert report.dropped == []
    assert "## Environment" in budgeted


def test_world_context_is_optional_so_it_goes_first(tmp_path):
    state = create_app_state(cwd=str(tmp_path))

    text, report = assemble_system_prompt(state, "world" * 2000, max_tokens=700)

    assert "## Current Context" not in text
    assert report.dropped == ["context"]


def test_the_report_names_the_dropped_blocks_and_warns_when_over_budget():
    _text, report = assemble(
        [
            PromptBlock("rules", "r" * 4000, REQUIRED),
            PromptBlock("context", "c" * 100, OPTIONAL),
        ],
        max_tokens=10,
    )

    rendered = report.render()

    assert "Dropped (optional, out of budget): context" in rendered
    assert "WARNING: required blocks alone exceed the budget" in rendered
