"""Tests for swarm lanes, the shared board and touch attribution (P15)."""

from __future__ import annotations

import asyncio
import os

from openlaoke.core.state import create_app_state
from openlaoke.core.swarm import CURRENT_MEMBER, MAX_MEMBERS, Swarm, SwarmMember, get_swarm
from openlaoke.core.tool import ToolContext
from openlaoke.tools.swarm_tool import SwarmTool


def _ctx(tmp_path):
    state = create_app_state(cwd=str(tmp_path))
    return ToolContext(app_state=state, tool_use_id="sw1"), state


def test_board_posts_and_renders() -> None:
    swarm = Swarm(create_app_state(cwd="."))
    swarm.board.post("first note")
    swarm.board.post("second note", member="w1")
    text = swarm.board.render_messages()
    assert "first note" in text and "w1: second note" in text


def test_touch_attributes_paths_to_a_lane() -> None:
    swarm = Swarm(create_app_state(cwd="."))
    swarm.board.members["w1"] = SwarmMember(id="w1", name="a", prompt="p")
    swarm.board.touch("src/app.py", "w1")
    swarm.board.touch("README.md", "")
    assert swarm.board.touched["src/app.py"] == "w1"
    assert swarm.board.touched["README.md"] == "parent"
    assert "src/app.py" in swarm.render() or "src/app.py" in swarm.board.render_touched()
    assert "src/app.py" in swarm.board.members["w1"].touched


def test_start_returns_immediately_and_await_collects(tmp_path, monkeypatch) -> None:
    async def fake_subagent(prompt, description, app_state, task_state, resume_from=None):
        await asyncio.sleep(0.05)
        return f"done: {prompt}"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_subagent)

    async def scenario():
        ctx, state = _ctx(tmp_path)
        swarm = get_swarm(state)
        members = swarm.start(
            [{"name": "alpha", "prompt": "task a"}, {"name": "beta", "prompt": "task b"}]
        )
        assert all(member.status == "running" for member in members)
        finished, all_done = await swarm.await_members(timeout=5)
        return members, finished, all_done

    members, finished, all_done = asyncio.run(scenario())
    assert all_done
    assert {member.result for member in members} == {"done: task a", "done: task b"}
    assert all(member.status == "done" for member in members)


def test_failure_is_recorded_not_raised(tmp_path, monkeypatch) -> None:
    async def failing(prompt, description, app_state, task_state, resume_from=None):
        raise RuntimeError("worker blew up")

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", failing)

    async def scenario():
        _ctx_obj, state = _ctx(tmp_path)
        swarm = get_swarm(state)
        swarm.start([{"name": "bad", "prompt": "x"}])
        await swarm.await_members(timeout=5)
        return swarm.members()[0]

    member = asyncio.run(scenario())
    assert member.status == "failed"
    assert "blew up" in member.error


def test_report_bounds_each_lane(tmp_path) -> None:
    _ctx_obj, state = _ctx(tmp_path)
    swarm = get_swarm(state)
    for index, body in enumerate(["a" * 5000, "b" * 10]):
        member = SwarmMember(id=f"w{index}", name=f"lane{index}", prompt="p", status="done")
        member.result = body
        swarm.board.members[member.id] = member
    text = swarm.report(max_chars=1000)
    assert len(text) <= 1200
    assert "lane0" in text and "lane1" in text
    assert "truncated" in text
    assert "b" * 10 in text


def test_member_limit_and_empty_prompt(tmp_path) -> None:
    _ctx_obj, state = _ctx(tmp_path)
    swarm = get_swarm(state)
    too_many = [{"name": f"w{i}", "prompt": "p"} for i in range(MAX_MEMBERS + 1)]
    try:
        swarm.start(too_many)
    except ValueError as exc:
        assert "at most" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a rejection")

    try:
        swarm.start([{"name": "x", "prompt": "   "}])
    except ValueError as exc:
        assert "no prompt" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected a rejection")


def test_cancel_stops_running_workers(tmp_path, monkeypatch) -> None:
    started = asyncio.Event()

    async def slow(prompt, description, app_state, task_state, resume_from=None):
        started.set()
        await asyncio.sleep(30)
        return "never"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", slow)

    async def scenario():
        _ctx_obj, state = _ctx(tmp_path)
        swarm = get_swarm(state)
        swarm.start([{"name": "sleepy", "prompt": "y"}])
        await asyncio.wait_for(started.wait(), timeout=2)
        count = await swarm.cancel()
        return count, swarm.members()[0].status

    count, status = asyncio.run(scenario())
    assert count == 1
    assert status == "cancelled"


def test_tool_start_status_and_note(tmp_path, monkeypatch) -> None:
    async def fake_subagent(prompt, description, app_state, task_state, resume_from=None):
        return "ok"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_subagent)

    async def scenario():
        ctx, _state = _ctx(tmp_path)
        tool = SwarmTool()
        started = await tool.call(
            ctx, action="start", tasks=[{"name": "lane", "prompt": "do the thing"}]
        )
        waited = await tool.call(ctx, action="await", timeout=5)
        status = await tool.call(ctx, action="status")
        noted = await tool.call(ctx, action="note", text="remember the walrus")
        messages = await tool.call(ctx, action="messages")
        return started, waited, status, noted, messages

    started, waited, status, noted, messages = asyncio.run(scenario())
    assert "Started 1 worker" in started.content
    assert "All workers finished" in waited.content
    assert "lane" in status.content
    assert "Posted" in noted.content
    assert "walrus" in messages.content


def test_tool_rejects_bad_input(tmp_path) -> None:
    ctx, _state = _ctx(tmp_path)
    tool = SwarmTool()
    assert asyncio.run(tool.call(ctx, action="explode")).is_error
    assert asyncio.run(tool.call(ctx, action="note", text=" ")).is_error


def test_edit_attribution_uses_the_lane_context(tmp_path) -> None:
    from openlaoke.core.edit_stats import record_edit

    ctx, state = _ctx(tmp_path)
    swarm = get_swarm(state)
    token = CURRENT_MEMBER.set("w3")
    try:
        record_edit(state, str(tmp_path / "file.py"), "", "x = 1\n", True)
    finally:
        CURRENT_MEMBER.reset(token)

    assert swarm.board.touched[str(tmp_path / "file.py")] == "w3"


def test_worker_edits_are_attributed_in_the_ledger(tmp_path, monkeypatch) -> None:
    """A write performed inside a worker lands under that worker's id."""

    async def fake_subagent(prompt, description, app_state, task_state, resume_from=None):
        from openlaoke.core.edit_stats import record_edit

        record_edit(app_state, os.path.join(app_state.get_cwd(), "made.py"), "", "x = 1\n", True)
        return "wrote it"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", fake_subagent)

    async def scenario():
        _ctx_obj, state = _ctx(tmp_path)
        swarm = get_swarm(state)
        members = swarm.start([{"name": "writer", "prompt": "write a file"}])
        await swarm.await_members(timeout=5)
        return members[0], swarm

    member, swarm = asyncio.run(scenario())
    assert member.status == "done"
    assert str(tmp_path / "made.py") in swarm.board.touched
    assert swarm.board.touched[str(tmp_path / "made.py")] == member.id


# --------------------------------------------------------------------------- #
# rendering, lookup and waiting edges
# --------------------------------------------------------------------------- #
def test_a_member_with_an_error_describes_it() -> None:
    member = SwarmMember(id="w1", name="alpha", prompt="p", status="failed")
    member.error = "worker blew up"

    text = member.describe()

    assert "error: worker blew up" in text


def test_an_empty_board_says_so() -> None:
    swarm = Swarm(create_app_state(cwd="."))

    assert swarm.board.render_messages() == "No board messages."
    assert swarm.board.render_touched() == "No files touched yet."
    assert swarm.render() == "No workers in this swarm."
    assert swarm.report() == "No worker output yet."


def test_touch_ignores_a_blank_path() -> None:
    swarm = Swarm(create_app_state(cwd="."))

    swarm.board.touch("")

    assert swarm.board.touched == {}


def test_touched_paths_render_with_their_owner() -> None:
    swarm = Swarm(create_app_state(cwd="."))
    swarm.board.touch("b.py", "w1")
    swarm.board.touch("a.py", "")

    rendered = swarm.board.render_touched()

    assert rendered.splitlines() == ["a.py  <-  parent", "b.py  <-  w1"]


def test_starting_nothing_is_rejected() -> None:
    swarm = Swarm(create_app_state(cwd="."))

    try:
        swarm.start([])
    except ValueError as exc:
        assert "nothing to start" in exc.args[0]
    else:  # pragma: no cover
        raise AssertionError("expected a rejection")


def test_members_are_found_by_id_or_name() -> None:
    swarm = Swarm(create_app_state(cwd="."))
    member = SwarmMember(id="w1", name="alpha", prompt="p", status="running")
    swarm.board.members["w1"] = member

    assert swarm.get("w1") is member
    assert swarm.get("alpha") is member
    assert swarm.get("ghost") is None
    assert swarm.running() == [member]


def test_await_times_out_without_marking_everything_done(tmp_path, monkeypatch) -> None:
    async def slow(prompt, description, app_state, task_state, resume_from=None):
        await asyncio.sleep(30)
        return "never"

    monkeypatch.setattr("openlaoke.core.agent_runner.run_subagent", slow)

    async def scenario():
        _ctx_obj, state = _ctx(tmp_path)
        swarm = get_swarm(state)
        swarm.start([{"name": "sleepy", "prompt": "y"}])
        result = await swarm.await_members(timeout=0.05)
        await swarm.cancel()
        return result

    finished, all_done = asyncio.run(scenario())

    assert finished and all_done is False


def test_a_report_over_the_budget_is_cut(tmp_path) -> None:
    _ctx_obj, state = _ctx(tmp_path)
    swarm = get_swarm(state)
    member = SwarmMember(id="w1", name="lane", prompt="p", status="done")
    member.result = "x" * 500
    swarm.board.members["w1"] = member

    text = swarm.report(max_chars=100)

    assert "swarm report truncated" in text
    assert len(text) <= 140
