"""Manual UI triggers: spin gesture, generic action buttons.

In the POC the spin gesture is computed in the browser and posted as an
``Event(kind="spin", ...)``. This source's only job is to receive it and put
it on the bus. Same shape will work for future gesture/action triggers.
"""

from __future__ import annotations

from .base import PushSource


class ManualSource(PushSource):
    """Receives manual / spin events from the WebSocket bridge."""
