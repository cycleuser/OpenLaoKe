"""Tests for the bus layer: MessageBus, EventSink, ProgressBus."""

from __future__ import annotations

import asyncio

from openlaoke.bus.events import InboundMessage, OutboundMessage
from openlaoke.bus.progress import ProgressBus, ProgressChunk
from openlaoke.bus.queue import MessageBus, new_session_key
from openlaoke.bus.runtime_events import AgentEvent, EventKind, EventSink, make_event


class TestMessageBus:
    def test_publish_and_consume(self) -> None:
        async def scenario() -> None:
            bus = MessageBus()
            await bus.publish_inbound(InboundMessage(text="hi", session_key="s1"))
            msg = await bus.consume_inbound("s1")
            assert msg.text == "hi"

        asyncio.run(scenario())

    def test_session_serial_dispatch(self) -> None:
        async def scenario() -> None:
            bus = MessageBus()
            await bus.publish_inbound(InboundMessage(text="first", session_key="a"))
            await bus.publish_inbound(InboundMessage(text="second", session_key="a"))
            first = await bus.consume_inbound("a")
            second = await bus.consume_inbound("a")
            assert first.text == "first"
            assert second.text == "second"

        asyncio.run(scenario())

    def test_pending_turn_merges_into_main(self) -> None:
        async def scenario() -> None:
            bus = MessageBus()
            await bus.publish_inbound(InboundMessage(text="main", session_key="a"))
            msg = await bus.consume_inbound("a")
            assert msg.text == "main"
            await bus.publish_inbound(InboundMessage(text="follow", session_key="a"))
            await bus.publish_inbound(InboundMessage(text="up", session_key="a"))
            await bus.release_session("a")
            msg2 = await bus.consume_inbound("a")
            assert msg2.text == "follow"
            msg3 = await bus.consume_inbound("a")
            assert msg3.text == "up"

        asyncio.run(scenario())

    def test_concurrent_sessions(self) -> None:
        async def scenario() -> None:
            bus = MessageBus()
            await bus.publish_inbound(InboundMessage(text="a", session_key="x"))
            await bus.publish_inbound(InboundMessage(text="b", session_key="y"))
            x = await bus.consume_inbound("x")
            y = await bus.consume_inbound("y")
            assert {x.text, y.text} == {"a", "b"}

        asyncio.run(scenario())

    def test_outbound_queue(self) -> None:
        async def scenario() -> None:
            bus = MessageBus()
            await bus.publish_outbound(OutboundMessage(text="ok", session_key="s1"))
            msg = await bus.consume_outbound("s1")
            assert msg.text == "ok"
            assert msg.final

        asyncio.run(scenario())

    def test_new_session_key_unique(self) -> None:
        keys = {new_session_key() for _ in range(50)}
        assert len(keys) == 50

    def test_session_lock(self) -> None:
        bus = MessageBus()
        lock1 = bus.acquire_session_lock("foo")
        lock2 = bus.acquire_session_lock("foo")
        assert lock1 is lock2
        lock3 = bus.acquire_session_lock("bar")
        assert lock3 is not lock1


class TestEventSink:
    def test_subscribe_and_emit(self) -> None:
        async def scenario() -> None:
            sink = EventSink()
            seen: list[EventKind] = []

            async def cb(event: AgentEvent) -> None:
                seen.append(event.kind)

            sink.subscribe(cb)
            await sink.emit(make_event(EventKind.TEXT, "s1", text="hello"))
            assert seen == [EventKind.TEXT]

        asyncio.run(scenario())

    def test_subscriber_error_isolated(self) -> None:
        async def scenario() -> None:
            sink = EventSink()
            seen: list[EventKind] = []

            async def bad(event: AgentEvent) -> None:
                raise RuntimeError("boom")

            async def good(event: AgentEvent) -> None:
                seen.append(event.kind)

            sink.subscribe(bad)
            sink.subscribe(good)
            await sink.emit(make_event(EventKind.NOTICE, "s1"))
            assert seen == [EventKind.NOTICE]

        asyncio.run(scenario())

    def test_buffer_capped(self) -> None:
        sink = EventSink()
        for i in range(600):
            sink.emit_sync(make_event(EventKind.NOTICE, "s1", seq=i))
        assert len(sink.recent(1000)) == sink._max_buffer

    def test_string_kind_coerced(self) -> None:
        ev = AgentEvent(kind="text")
        assert ev.kind is EventKind.TEXT


class TestProgressBus:
    def test_open_publish_close(self) -> None:
        bus = ProgressBus()
        bus.open("c1", "s1")
        bus.publish(ProgressChunk("c1", "s1", "hello\n"))
        bus.publish(ProgressChunk("c1", "s1", "world\n", kind="stderr"))
        assert bus.text("c1") == "hello\n"
        assert len(bus.chunks("c1")) == 2
        assert not bus.is_closed("c1")
        bus.close("c1")
        assert bus.is_closed("c1")
        bus.clear("c1")
        assert bus.chunks("c1") == []
