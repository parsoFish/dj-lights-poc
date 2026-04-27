"""Hand-tracking bridge.

POC ships browser-side MediaPipe Hands; events arrive on the WebSocket and
are forwarded to the bus by this source.

To swap in an Orin Nano CNN later: implement :class:`InputSource` directly,
read frames from the camera, run inference, and publish events with the same
``hand_position`` payload shape (see ``Event`` docstring).
"""

from __future__ import annotations

from .base import PushSource


class CvHandsSource(PushSource):
    """Receives ``hand_position`` events from the WebSocket bridge."""
