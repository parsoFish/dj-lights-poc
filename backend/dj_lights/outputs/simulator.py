"""Simulator output: encodes frames for the WebSocket bridge.

Wire format (binary, big-endian):

::

    u16   layout_version
    u16   bar_count
    f64   timestamp_ms
    repeat bar_count times:
        u8    bar_id_len
        bytes bar_id (utf-8)
        u16   pixel_count
        bytes pixels (3 * pixel_count, R G B)

Future agents adding a new sink (Art-Net, recording, OSC) implement
:class:`OutputSink` and register it through the server. The encoder below is
also reused by the WS handler for fan-out to multiple browsers.
"""

from __future__ import annotations

import struct
from collections.abc import Awaitable, Callable

from ..engine.frame import LedFrame
from .base import OutputSink


def encode_frame(frame: LedFrame) -> bytes:
    chunks: list[bytes] = [
        struct.pack(">HHd", frame.layout_version, len(frame.bars), frame.timestamp_ms),
    ]
    for bar in frame.bars:
        bar_id_bytes = bar.bar_id.encode("utf-8")
        if len(bar_id_bytes) > 255:
            raise ValueError(f"bar id too long for wire format: {bar.bar_id!r}")
        chunks.append(struct.pack(">B", len(bar_id_bytes)))
        chunks.append(bar_id_bytes)
        chunks.append(struct.pack(">H", len(bar.pixels)))
        for r, g, b in bar.pixels:
            chunks.append(bytes((r & 0xFF, g & 0xFF, b & 0xFF)))
    return b"".join(chunks)


class SimulatorSink:
    """Calls a user-supplied async sender for every frame."""

    name = "simulator"

    def __init__(self, send: Callable[[bytes], Awaitable[None]]) -> None:
        self._send = send

    async def write(self, frame: LedFrame) -> None:
        await self._send(encode_frame(frame))


__all__ = ["OutputSink", "SimulatorSink", "encode_frame"]
