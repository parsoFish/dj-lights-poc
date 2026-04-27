"""Stub for an on-device Orin Nano CV worker.

Same event contract as :mod:`cv_hands`, so when this is implemented it can be
swapped in without engine or preset changes. Future agent: read the camera
(e.g. via ``cv2.VideoCapture`` or GStreamer), run a hand/gesture model
(MediaPipe -> TFLite, or a fine-tuned MobileNet on TensorRT), and publish
events into the bus.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from ..engine.events import Event, EventBus


class OrinHandsSource:
    """Not yet implemented. Same shape as a pull-style :class:`InputSource`."""

    name = "cv-orin"

    def __init__(self, bus: EventBus) -> None:
        self._bus = bus

    async def stream(self) -> AsyncIterator[Event]:
        # `yield` makes this an async generator so `async for` matches the
        # protocol shape; the body itself raises before yielding anything.
        if False:  # pragma: no cover
            yield  # type: ignore[unreachable]
        raise NotImplementedError(
            "OrinHandsSource is scaffolded but not implemented; "
            "see docs/decisions.md for the upgrade path from browser MediaPipe."
        )
