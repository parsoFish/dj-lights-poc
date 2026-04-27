"""Event types and a typed pub/sub bus.

The bus is the only path inputs use to talk to the engine, and the only path
the engine has to learn that something happened. A new event source therefore
only needs to implement :class:`InputSource` and emit :class:`Event` objects;
the engine never has to know which source produced an event.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Literal

EventKind = Literal[
    "beat",
    "hand_position",
    "spin",
    "manual",
    "heartbeat",
]

KNOWN_KINDS: frozenset[str] = frozenset(
    ("beat", "hand_position", "spin", "manual", "heartbeat"),
)


@dataclass(frozen=True, slots=True)
class Event:
    """A single trigger or sample fed into the engine.

    Payloads per kind (POC contract — extend as new presets need data):

    - ``beat``         : ``{"bpm": float, "confidence": float}``
    - ``hand_position``: ``{"hand": "left"|"right", "x": 0..1, "y": 0..1}``
    - ``spin``         : ``{"direction": "cw"|"ccw", "rpm": float}``
    - ``manual``       : ``{"action": str, ...}``
    - ``heartbeat``    : ``{}``
    """

    kind: EventKind
    timestamp_ms: float
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.kind not in KNOWN_KINDS:
            raise ValueError(f"unknown event kind: {self.kind!r}")


class EventBus:
    """In-process pub/sub for :class:`Event`.

    Subscribers receive an :class:`asyncio.Queue` and own draining it. Slow
    subscribers do not block publishers — overflowing queues drop oldest first
    so the engine can always make progress, which matters for a real-time loop.
    """

    DEFAULT_QUEUE_MAX = 256

    def __init__(self, *, queue_max: int = DEFAULT_QUEUE_MAX) -> None:
        self._queue_max = queue_max
        self._subscribers: list[asyncio.Queue[Event]] = []

    def subscribe(self) -> asyncio.Queue[Event]:
        q: asyncio.Queue[Event] = asyncio.Queue(maxsize=self._queue_max)
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[Event]) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(q)

    async def publish(self, event: Event) -> None:
        for q in self._subscribers:
            if q.full():
                # Drop oldest to keep the loop real-time.
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            await q.put(event)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def stream(self) -> AsyncIterator[Event]:
        """Convenience: yield every event the bus broadcasts to a fresh subscriber."""

        q = self.subscribe()
        try:
            while True:
                yield await q.get()
        finally:
            self.unsubscribe(q)
