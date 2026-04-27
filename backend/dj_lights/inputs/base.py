"""Input source contract.

An input source produces :class:`Event`s and pushes them onto the bus. Sources
are pluggable: the engine never has to know whether a beat came from the
browser's Web Audio detector, a backend audio worker, or a future MIDI clock.

Two flavours are supported:

* **Pull-style** sources implement :meth:`stream` to yield events; the runner
  pumps them onto the bus.
* **Push-style** sources accept events from elsewhere (e.g. an HTTP/WS
  endpoint) and push them on directly via :meth:`InputSource.publish`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from ..engine.events import Event, EventBus


@runtime_checkable
class InputSource(Protocol):
    """Anything that turns external signals into engine :class:`Event`s."""

    name: str

    async def stream(self) -> AsyncIterator[Event]:  # pragma: no cover - protocol
        ...


class PushSource:
    """Base for push-style sources (e.g. WS handlers).

    Future-agent guidance: subclass this for any source that *receives* events
    rather than polling for them, and call :meth:`publish` from your handler.
    """

    def __init__(self, name: str, bus: EventBus) -> None:
        self.name = name
        self._bus = bus

    async def publish(self, event: Event) -> None:
        await self._bus.publish(event)
