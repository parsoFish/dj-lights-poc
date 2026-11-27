"""WebSocket subscriber to a WLED node's live LED stream.

Wire format from `WLED/wled00/ws.cpp::sendLiveLedsWs`:

* Magic byte 0: ``b'L'`` (0x4C).
* Byte 1: version. ``1`` = 1D strip, ``2`` = 2D matrix.
* For matrix (v2): bytes 2..3 are width / height (each already divided by ``n``).
* Remainder: RGB triples, one per delivered pixel.

WLED applies brightness before sending and additively folds any white
channel into RGB, so the bytes we receive are display-ready. WLED also
downsamples once total LEDs exceed 1024 (256 on ESP8266) — the message
itself doesn't say what ``n`` is, so we infer it from the device's known
``led_count`` divided by the number of received pixels.

WLED only allows **one** live subscriber at a time. If LedFx's frontend or
another tool is currently the live client, our request kicks them off.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass

import websockets
from websockets.exceptions import ConnectionClosed

logger = logging.getLogger(__name__)

LIVE_MAGIC = 0x4C  # 'L'
SUBSCRIBE_PAYLOAD = '{"lv":true}'


@dataclass(frozen=True, slots=True)
class WledLiveFrame:
    """One decoded live frame from a WLED device."""

    device_id: str
    version: int
    width: int  # 1D strip: same as len(pixels); 2D: matrix width
    height: int  # 1D strip: 1; 2D: matrix height
    pixels: tuple[tuple[int, int, int], ...]
    downsample_n: int  # physical LED step represented by each pixel slot


def decode_live_frame(
    payload: bytes, device_id: str, *, total_leds: int | None = None
) -> WledLiveFrame:
    """Decode a single binary live-stream message from WLED.

    ``total_leds`` is the known LED count from ``/json/info`` and is used to
    compute the downsample factor. If unknown, we assume 1.
    """

    if len(payload) < 2 or payload[0] != LIVE_MAGIC:
        raise ValueError("not a WLED live frame (missing 'L' magic)")
    version = payload[1]
    if version == 1:
        body = payload[2:]
        width = len(body) // 3
        height = 1
    elif version == 2:
        if len(payload) < 4:
            raise ValueError("WLED 2D live frame truncated")
        width = payload[2]
        height = payload[3]
        body = payload[4:]
    else:
        raise ValueError(f"unsupported WLED live frame version: {version}")

    if len(body) % 3 != 0:
        raise ValueError(f"live frame body not a multiple of 3 bytes: {len(body)}")
    pixel_count = len(body) // 3
    pixels = tuple(
        (body[i], body[i + 1], body[i + 2]) for i in range(0, len(body), 3)
    )

    # WLED: n = ceil(total / 1024), delivered = total // n. Recover n from
    # (total, delivered) via rounding — handles not-evenly-divisible cases
    # (e.g. total=2050 -> n=3, delivered=683).
    n = max(1, round(total_leds / pixel_count)) if total_leds and pixel_count > 0 else 1

    return WledLiveFrame(
        device_id=device_id,
        version=version,
        width=width,
        height=height,
        pixels=pixels,
        downsample_n=n,
    )


class WledLiveSubscriber:
    """Maintains a WS connection to one WLED node and yields decoded frames.

    Auto-reconnects with exponential backoff so a brief WiFi blip doesn't
    end the mirror; the consumer just sees a gap in frames.
    """

    def __init__(
        self,
        ws_url: str,
        device_id: str,
        *,
        total_leds: int | None = None,
        ping_interval_s: float = 20.0,
    ) -> None:
        self._url = ws_url
        self._device_id = device_id
        self._total_leds = total_leds
        self._ping_interval_s = ping_interval_s
        self._stopped = False

    async def stream(self) -> AsyncIterator[WledLiveFrame]:
        """Yield decoded live frames until ``stop()`` is called."""

        backoff = 0.5
        while True:
            if self._stopped:
                return
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=self._ping_interval_s,
                    open_timeout=5.0,
                ) as ws:
                    await ws.send(SUBSCRIBE_PAYLOAD)
                    backoff = 0.5
                    async for raw in ws:
                        if isinstance(raw, str):
                            # WLED sends JSON state updates and pong text — ignore for live preview.
                            continue
                        try:
                            yield decode_live_frame(
                                raw, self._device_id, total_leds=self._total_leds
                            )
                        except ValueError as exc:
                            logger.debug("dropping unparseable WLED frame: %s", exc)
            except (OSError, ConnectionClosed, TimeoutError) as exc:
                logger.info(
                    "WLED %s WS disconnected (%s); retrying in %.1fs",
                    self._device_id, exc, backoff,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 10.0)

    async def run(self, on_frame: Callable[[WledLiveFrame], Awaitable[None]]) -> None:
        async for frame in self.stream():
            await on_frame(frame)

    def stop(self) -> None:
        self._stopped = True
