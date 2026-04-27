"""WLED -> stage mirror task.

Reads frames off one or more `WledLiveSubscriber`s, looks up the active
`WledCalibration`, and emits assembled `LedFrame`s for the engine to
broadcast. The engine's compositing path is bypassed in mirror mode — what
WLED renders is the source of truth.

Multi-device support is included for completeness but Phase 6 only exercises
the single-device case (the friend's setup is one ESP-32). Each device's
most-recent pixels are kept in a small map so the next frame in from any
single device produces a fresh layout-shaped frame.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field

from ..engine.frame import RGB, LedFrame, StageLayout
from .calibration import WledCalibration, apply_bindings
from .live_ws import WledLiveFrame, WledLiveSubscriber

logger = logging.getLogger(__name__)


@dataclass
class WledMirror:
    """One mirror = one layout + one calibration + one or more device subscriptions."""

    layout: StageLayout
    calibration: WledCalibration
    on_frame: Callable[[LedFrame], Awaitable[None]]
    layout_version: int = 0
    _device_pixels: dict[str, tuple[RGB, ...]] = field(default_factory=dict)
    _subscribers: dict[str, WledLiveSubscriber] = field(default_factory=dict)
    _tasks: dict[str, asyncio.Task[None]] = field(default_factory=dict)

    def add_subscriber(self, sub: WledLiveSubscriber, device_id: str) -> None:
        if device_id in self._subscribers:
            return
        self._subscribers[device_id] = sub
        self._tasks[device_id] = asyncio.create_task(self._consume(sub, device_id))

    async def stop(self) -> None:
        for sub in self._subscribers.values():
            sub.stop()
        for task in self._tasks.values():
            task.cancel()
        for task in self._tasks.values():
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._subscribers.clear()
        self._tasks.clear()

    async def ingest(self, frame: WledLiveFrame) -> None:
        """Update internal pixel state from one device's live frame, then emit a layout frame."""

        self._device_pixels[frame.device_id] = frame.pixels
        layout_frame = apply_bindings(
            self.layout,
            self._device_pixels,
            self.calibration.bindings,
            layout_version=self.layout_version,
        )
        await self.on_frame(layout_frame)

    async def _consume(self, sub: WledLiveSubscriber, device_id: str) -> None:
        try:
            async for frame in sub.stream():
                await self.ingest(frame)
        except Exception:
            logger.exception("WLED mirror consumer for %s crashed", device_id)
