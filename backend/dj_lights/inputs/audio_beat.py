"""Beat events bridge.

The frontend Web Audio detector produces beat events; this source forwards
them onto the bus. A future Python-side detector (e.g. ``aubio`` or
``librosa.onset.onset_detect``) can implement :class:`InputSource` directly
and call :meth:`publish` with the same payload contract.
"""

from __future__ import annotations

from .base import PushSource


class AudioBeatSource(PushSource):
    """Receives beat events from the WebSocket bridge."""
