"""Art-Net sink stub.

Once the friend confirms the bars' protocol, replace the no-op write with
``pyartnet`` calls (or an sACN / DMX-USB-Pro implementation if needed). The
mapping from ``LedFrame`` segments -> universe/channel layout is the only
thing that should need bespoke configuration.
"""

from __future__ import annotations

import logging

from ..engine.frame import LedFrame

logger = logging.getLogger(__name__)


class ArtNetSink:
    """Logs frames at TRACE-ish level. Real wire-up TODO."""

    name = "artnet"

    def __init__(self, *, host: str = "127.0.0.1", universe: int = 0) -> None:
        self.host = host
        self.universe = universe

    async def write(self, frame: LedFrame) -> None:
        # TODO: wire up pyartnet once the friend's bars' protocol is known.
        logger.debug(
            "artnet skip: host=%s universe=%d pixels=%d",
            self.host,
            self.universe,
            frame.total_pixels(),
        )
