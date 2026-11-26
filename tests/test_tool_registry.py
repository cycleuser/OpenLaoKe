"""Tests for the Tool base class, the registry and history truncation.

The registry is what every dispatch path goes through, so the interesting
behaviours are lazy (deferred) loading, the frozen-schema cache that keeps the
prompt cache warm, and the read-only classification used to decide parallel
dispatch.
"""

from __future__ import annotations

import asyncio

import pytest
from pydantic import BaseModel

from openlaoke.core.state import create_app_state
from openlaoke.core.tool import (
    DeferredToolInfo,
    PreviewResult,
    Tool,
    ToolContext,
    ToolRegistry,
    ValidationResult,
    truncate_tool_history,
    with_common_fields,
)
from openlaoke.types.core_types import ToolResultBlock

# --------------------------------------------------------------------------- #
# Test tools
# --------------------------------------------------------------------------- #


class EmptyInput(BaseModel):
    pass


class EchoInput(BaseModel):
    text: str
    count: int = 1


class EchoTool(Tool):
    name = "Echo"
    description = "Echo text back"
    input_schema = EchoInput

    async def call(self, ctx, **kwargs):
        return ToolResultBlock(tool_use_id=ctx.tool_use_id, content=kwargs.get("text", ""))


class BoomTool(Tool):
    name = "Boom"
    description = "Always raises"
    input_schema = EmptyInput

    async def call(self, ctx, **kwargs):
        raise RuntimeError("kaboom")


class DictSchemaTool(Tool):
    name = "DictTool"
    description = "Uses a raw dict schema"
    input_schema = {
        "type": "object",
        "properties": {"path": {"type": "string"}, "n": {"type": "integer"}},
        "required": ["path"],
    }

    async def call(self, ctx, **kwargs):  # pragma: no cover - not exercised
        return ToolResultBlock(tool_use_id=ctx.tool_use_id)


class NoSchemaTool(Tool):
    name = "NoSchema"
    description = "No schema at all"
    input_schema = None

    async def call(self, ctx, **kwargs):  # pragma: no cover - not exercised
        return ToolResultBlock(tool_use_id=ctx.tool_use_id)


@pytest.fixture()
def ctx(tmp_path):
    return ToolContext(app_state=create_app_state(cwd=str(tmp_path)), tool_use_id="t1")


# --------------------------------------------------------------------------- #
# PreviewResult
# --------------------------------------------------------------------------- #


def test_preview_one_line_for_each_action() -> None:
    assert PreviewResult(path="a.py", action="create", lines_after=10).one_line() == "Create a.py (10 lines)"
    assert (
        PreviewResult(path="a.py", action="update", lines_before=10, lines_after=13).one_line()
        == "Update a.py (+3 lines)"
    )
    assert (
        PreviewResult(path="a.py", action="update", lines_before=10, lines_after=8).one_line()
        == "Update a.py (-2 lines)"
    )
    assert PreviewResult(path="a.py", action="delete", lines_before=4).one_line() == "Delete a.py (4 lines)"
    assert PreviewResult().one_line() == "No effect"
    assert PreviewResult(summary="Dry run only").one_line() == "Dry run only"


# --------------------------------------------------------------------------- #
# Tool.safe_call
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
async def test_safe_call_returns_the_tool_result(ctx) -> None:
    result = await EchoTool().safe_call(ctx, text="hi")
    assert result.content == "hi"
    assert result.is_error is False


@pytest.mark.asyncio
async def test_safe_call_converts_exceptions_into_error_results(ctx) -> None:
    result = await BoomTool().safe_call(ctx)
    assert result.is_error is True
    assert result.tool_use_id == "t1"
    assert result.content == "Error in Boom: kaboom"


# --------------------------------------------------------------------------- #
# Schemas and common fields
# --------------------------------------------------------------------------- #


def test_with_common_fields_adds_intent_and_accept() -> None:
    schema = with_common_fields({"type": "object", "properties": {"a": {"type": "string"}}})
    assert "intent" in schema["properties"]
    assert "accept_large_output" in schema["properties"]
    assert schema["required"][0] == "intent"
    # Existing required entries are preserved after intent.
    schema2 = with_common_fields({"type": "object", "properties": {}, "required": ["a"]})
    assert schema2["required"] == ["intent", "a"]


def test_with_common_fields_is_idempotent() -> None:
    schema = with_common_fields({"type": "object", "properties": {}})
    again = with_common_fields(schema)
    assert again["required"].count("intent") == 1


def test_get_input_schema_from_a_pydantic_model() -> None:
    schema = EchoTool().get_input_schema()
    assert schema["type"] == "object"
    assert "text" in schema["properties"]
    assert "intent" in schema["properties"]


def test_get_input_schema_from_a_raw_dict() -> None:
    schema = DictSchemaTool().get_input_schema()
    assert schema["properties"]["path"] == {"type": "string"}
    assert "intent" in schema["properties"]


def test_get_input_schema_normalises_a_missing_schema() -> None:
    schema = NoSchemaTool().get_input_schema()
    assert schema["type"] == "object"
    assert set(schema["properties"]) >= {"intent", "accept_large_output"}


def test_get_description_defaults_to_the_class_description() -> None:
    assert EchoTool().get_description() == "Echo text back"


# --------------------------------------------------------------------------- #
# validate_input
# --------------------------------------------------------------------------- #


def test_validate_pydantic_input_accepts_valid_and_rejects_invalid() -> None:
    tool = EchoTool()
    assert tool.validate_input({"text": "hi", "count": 2}).result is True

    missing = tool.validate_input({})
    assert missing.result is False
    assert missing.message == "Missing required field: text"
    assert missing.error_code == 400

    wrong_type = tool.validate_input({"text": "hi", "count": "two"})
    assert wrong_type.result is False
    assert wrong_type.message == "Field 'count' must be integer, got str"


def test_validate_rejects_bools_where_an_int_is_expected() -> None:
    tool = EchoTool()
    result = tool.validate_input({"text": "hi", "count": True})
    # bool is a subclass of int in Python but not valid JSON integer input here.
    assert result.result is False


def test_validate_treats_none_as_missing_for_required_fields() -> None:
    result = DictSchemaTool().validate_input({"path": None})
    assert result.result is False
    assert "path" in result.message


def test_validate_skips_unknown_fields_and_none_values() -> None:
    assert DictSchemaTool().validate_input({"path": "a", "extra": 1, "n": None}).result is True


def test_validate_without_a_schema_always_passes() -> None:
    assert NoSchemaTool().validate_input({"anything": object()}).result is True


def test_validate_ignores_string_type_fields() -> None:
    schema = {"type": "object", "properties": {"free": {"type": "whatever"}}}
    assert Tool._validate_schema_dict({"free": 1}, schema) == ValidationResult(result=True)


# --------------------------------------------------------------------------- #
# Defaults on the base class
# --------------------------------------------------------------------------- #


def test_default_preview_progress_and_deny_message() -> None:
    tool = EchoTool()
    assert tool.preview() == PreviewResult()
    assert tool.get_progress(None) is None
    assert "denied by the user" in tool.get_deny_message({})


def test_render_result_handles_text_and_structures() -> None:
    tool = EchoTool()
    assert tool.render_result(ToolResultBlock(tool_use_id="t", content="plain")) == "plain"
    rendered = tool.render_result(ToolResultBlock(tool_use_id="t", content={"a": 1}))
    assert rendered == '{\n  "a": 1\n}'


# --------------------------------------------------------------------------- #
# Registry: registration and deferred loading
# --------------------------------------------------------------------------- #


def test_register_unregister_and_get() -> None:
    registry = ToolRegistry()
    tool = EchoTool()
    registry.register(tool)
    assert registry.get("Echo") is tool
    assert registry.get("Missing") is None
    assert registry.unregister("Echo") is True
    assert registry.unregister("Echo") is False


def test_deferred_sync_loader_is_resolved_by_get() -> None:
    registry = ToolRegistry()
    registry.register_deferred("Lazy", EchoTool)
    assert registry.is_deferred("Lazy") is True
    assert registry.is_loaded("Lazy") is False

    tool = registry.get("Lazy")
    assert isinstance(tool, EchoTool)
    assert registry.is_loaded("Lazy") is True
    assert registry.is_deferred("Lazy") is False


def test_deferred_async_loader_is_not_resolved_by_get() -> None:
    registry = ToolRegistry()

    async def loader() -> Tool:
        return EchoTool()

    registry.register_deferred("AsyncLazy", loader)
    assert registry.get("AsyncLazy") is None


@pytest.mark.asyncio
async def test_deferred_async_loader_resolves_through_get_async() -> None:
    registry = ToolRegistry()

    async def loader() -> Tool:
        return EchoTool()

    registry.register_deferred_with_info("AsyncLazy", loader, description="d")
    tool = await registry.get_async("AsyncLazy")
    assert isinstance(tool, EchoTool)
    assert registry.is_loaded("AsyncLazy") is True
    # The deferred info is dropped once the tool is live.
    assert registry.get_deferred_info("AsyncLazy") is None


@pytest.mark.asyncio
async def test_get_async_returns_loaded_and_missing_tools() -> None:
    registry = ToolRegistry()
    tool = EchoTool()
    registry.register(tool)
    assert await registry.get_async("Echo") is tool
    assert await registry.get_async("Nope") is None


@pytest.mark.asyncio
async def test_get_all_resolves_sync_loaders_and_get_all_async_the_rest() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register_deferred("SyncLazy", DictSchemaTool)

    async def async_loader() -> Tool:
        return NoSchemaTool()

    registry.register_deferred("AsyncLazy", async_loader)

    names = {tool.name for tool in registry.get_all()}
    assert names == {"Echo", "DictTool"}  # the async one cannot be resolved here

    all_names = {tool.name for tool in await registry.get_all_async()}
    assert all_names == {"Echo", "DictTool", "NoSchema"}


def test_get_loaded_only_lists_resolved_tools() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register_deferred("Lazy", DictSchemaTool)
    assert [t.name for t in registry.get_loaded()] == ["Echo"]


def test_deferred_info_accessors() -> None:
    registry = ToolRegistry()
    registry.register_deferred_with_info(
        "Lazy", EchoTool, description="lazy echo", search_hint="echo things", aliases=["ec"]
    )
    info = registry.get_deferred_info("Lazy")
    assert isinstance(info, DeferredToolInfo)
    assert info.description == "lazy echo"
    assert info.aliases == ["ec"]
    assert [i.name for i in registry.get_all_deferred_info()] == ["Lazy"]


def test_deferred_info_defaults() -> None:
    info = DeferredToolInfo("x")
    assert info.description == ""
    assert info.search_hint == ""
    assert info.aliases == []


# --------------------------------------------------------------------------- #
# Registry: prompt schemas and freezing
# --------------------------------------------------------------------------- #


def test_prompt_schemas_include_name_description_and_schema() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    schemas = registry.get_all_for_prompt()
    assert len(schemas) == 1
    assert schemas[0]["name"] == "Echo"
    assert schemas[0]["description"] == "Echo text back"
    assert "text" in schemas[0]["input_schema"]["properties"]


def test_freeze_caches_schemas_until_thawed() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    assert registry.is_frozen is False

    registry.freeze()
    assert registry.is_frozen is True
    frozen = registry.get_all_for_prompt()

    # A late registration does not disturb the frozen prompt schemas.
    registry.register(DictSchemaTool())
    assert registry.get_all_for_prompt() is frozen

    registry.thaw()
    assert registry.is_frozen is False
    rebuilt = registry.get_all_for_prompt()
    assert {schema["name"] for schema in rebuilt} == {"Echo", "DictTool"}


def test_freeze_twice_keeps_the_first_snapshot() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.freeze()
    snapshot = registry.get_all_for_prompt()
    registry.freeze()
    assert registry.get_all_for_prompt() is snapshot


def test_deferred_prompt_listing_marks_defer_loading() -> None:
    registry = ToolRegistry()
    registry.register_deferred_with_info("Lazy", EchoTool, description="d", search_hint="s", aliases=["l"])
    listed = registry.get_deferred_for_prompt()
    assert listed == [
        {"name": "Lazy", "description": "d", "search_hint": "s", "aliases": ["l"], "defer_loading": True}
    ]


# --------------------------------------------------------------------------- #
# Registry: search and read-only classification
# --------------------------------------------------------------------------- #


def test_search_matches_name_and_description_case_insensitively() -> None:
    registry = ToolRegistry()
    registry.register(EchoTool())
    registry.register(DictSchemaTool())
    assert [t.name for t in registry.search("echo")] == ["Echo"]
    assert [t.name for t in registry.search("RAW DICT")] == ["DictTool"]
    assert registry.search("nothing") == []


def test_search_deferred_covers_name_description_hint_and_aliases() -> None:
    registry = ToolRegistry()
    registry.register_deferred_with_info(
        "Searcher", EchoTool, description="find files", search_hint="locate", aliases=["src"]
    )
    assert [i.name for i in registry.search_deferred("searcher")] == ["Searcher"]
    assert [i.name for i in registry.search_deferred("find")] == ["Searcher"]
    assert [i.name for i in registry.search_deferred("locate")] == ["Searcher"]
    assert [i.name for i in registry.search_deferred("src")] == ["Searcher"]
    assert registry.search_deferred("zzz") == []


def test_is_readonly_prefers_the_registered_tool_flag() -> None:
    registry = ToolRegistry()

    class ReadOnlyTool(Tool):
        name = "Custom"
        is_read_only = True

        async def call(self, ctx, **kwargs):  # pragma: no cover
            return ToolResultBlock(tool_use_id=ctx.tool_use_id)

    registry.register(ReadOnlyTool())
    assert registry.is_readonly("Custom") is True
    assert registry.is_readonly("Echo") is False  # unregistered name


def test_is_readonly_falls_back_to_the_builtin_tool_sets() -> None:
    registry = ToolRegistry()
    assert registry.is_readonly("Read") is True
    assert registry.is_readonly("Grep") is True
    assert registry.is_readonly("Write") is False
    assert registry.is_readonly("Bash") is False
    assert registry.is_readonly("Unknown") is False


# --------------------------------------------------------------------------- #
# truncate_tool_history
# --------------------------------------------------------------------------- #


def test_short_output_is_untouched() -> None:
    assert truncate_tool_history("short", max_bytes=100) == "short"


def test_output_exactly_at_the_limit_is_untouched() -> None:
    text = "a" * 100
    assert truncate_tool_history(text, max_bytes=100) == text


def test_long_output_keeps_head_and_tail_with_a_header() -> None:
    body = "".join(str(i % 10) for i in range(1000))
    out = truncate_tool_history(body, max_bytes=100)
    assert out.startswith("[tool output compacted: original_bytes=1000")
    assert "...[middle omitted]..." in out
    assert body[:10] in out
    assert body[-10:] in out


def test_truncation_respects_the_byte_budget_roughly() -> None:
    body = "x" * 5000
    out = truncate_tool_history(body, max_bytes=200)
    # Header plus head/tail and the marker; still far below the original size.
    assert len(out.encode("utf-8")) < 400


def test_truncation_splits_multibyte_characters_safely() -> None:
    body = "中文内容" * 500  # 3 bytes per character
    out = truncate_tool_history(body, max_bytes=61)
    assert "...[middle omitted]..." in out
    # Replacement characters are allowed, but decoding must not raise.
    assert isinstance(out, str)


def test_default_limit_is_four_kilobytes() -> None:
    body = "y" * 10_000
    out = truncate_tool_history(body)
    assert "original_bytes=10000" in out


def test_get_input_schema_does_not_mutate_a_shared_dict_schema() -> None:
    # input_schema is a class attribute, so mutation would leak across tools and
    # into validate_input(); the returned schema must be a copy.
    tool = DictSchemaTool()
    tool.get_input_schema()
    assert set(tool.input_schema["properties"]) == {"path", "n"}
    assert tool.input_schema["required"] == ["path"]


def test_intent_is_advertised_but_never_enforced() -> None:
    tool = DictSchemaTool()
    schema = tool.get_input_schema()
    assert "intent" in schema["required"]

    # A call without intent must still validate: the label is a soft field.
    assert tool.validate_input({"path": "a.py"}).result is True
    assert tool.validate_input({"path": "a.py", "intent": "read it"}).result is True


def test_soft_required_fields_can_still_fail_type_checks() -> None:
    schema = {
        "type": "object",
        "properties": {"intent": {"type": "string"}},
        "required": ["intent"],
    }
    assert Tool._validate_schema_dict({"intent": 5}, schema).result is False


# --------------------------------------------------------------------------- #
# Defensive paths
# --------------------------------------------------------------------------- #


def test_validate_survives_a_schema_object_that_raises() -> None:
    class BrokenSchema:
        @staticmethod
        def model_json_schema() -> dict:
            raise RuntimeError("cannot build schema")

    class BrokenTool(Tool):
        name = "Broken"
        input_schema = BrokenSchema

        async def call(self, ctx, **kwargs):  # pragma: no cover
            return ToolResultBlock(tool_use_id=ctx.tool_use_id)

    # Unable to validate is treated as valid rather than blocking the call.
    assert BrokenTool().validate_input({"x": 1}).result is True


@pytest.mark.asyncio
async def test_get_async_waits_for_a_concurrent_load() -> None:
    registry = ToolRegistry()
    started = asyncio.Event()
    release = asyncio.Event()

    async def slow_loader() -> Tool:
        started.set()
        await release.wait()
        return EchoTool()

    registry.register_deferred("Slow", slow_loader)

    first = asyncio.create_task(registry.get_async("Slow"))
    await started.wait()
    second = asyncio.create_task(registry.get_async("Slow"))
    release.set()
    loaded = await asyncio.gather(first, second)

    # Both waiters receive the same instance; the loader runs once.
    assert loaded[0] is loaded[1]
    assert registry.is_loaded("Slow") is True


@pytest.mark.asyncio
async def test_get_async_returns_none_when_the_loader_vanishes() -> None:
    registry = ToolRegistry()
    registry._load_locks["Ghost"] = asyncio.Lock()
    assert await registry.get_async("Ghost") is None
