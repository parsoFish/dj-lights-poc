import asyncio

import pytest

from dj_lights.engine.events import Event, EventBus


def test_event_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError):
        Event(kind="nonsense", timestamp_ms=0.0)  # type: ignore[arg-type]


def test_event_known_kinds_construct() -> None:
    for kind in ("beat", "hand_position", "spin", "manual", "heartbeat"):
        Event(kind=kind, timestamp_ms=0.0)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_bus_delivers_to_each_subscriber() -> None:
    bus = EventBus()
    a = bus.subscribe()
    b = bus.subscribe()
    e = Event(kind="manual", timestamp_ms=1.0, payload={"action": "x"})
    await bus.publish(e)
    assert (await a.get()).payload["action"] == "x"
    assert (await b.get()).payload["action"] == "x"


@pytest.mark.asyncio
async def test_bus_drops_oldest_when_full() -> None:
    bus = EventBus(queue_max=2)
    q = bus.subscribe()
    for i in range(5):
        await bus.publish(Event(kind="heartbeat", timestamp_ms=float(i)))
    # Only the last 2 should remain.
    received = []
    while not q.empty():
        received.append(q.get_nowait())
    assert [e.timestamp_ms for e in received] == [3.0, 4.0]


@pytest.mark.asyncio
async def test_bus_unsubscribe_stops_delivery() -> None:
    bus = EventBus()
    q = bus.subscribe()
    bus.unsubscribe(q)
    bus.unsubscribe(q)  # idempotent
    await bus.publish(Event(kind="heartbeat", timestamp_ms=0.0))
    assert q.empty()


@pytest.mark.asyncio
async def test_bus_stream_yields_events() -> None:
    bus = EventBus()

    async def producer() -> None:
        await asyncio.sleep(0)
        await bus.publish(Event(kind="heartbeat", timestamp_ms=1.0))

    task = asyncio.create_task(producer())
    received: list[float] = []
    async for ev in bus.stream():
        received.append(ev.timestamp_ms)
        break
    await task
    assert received == [1.0]
