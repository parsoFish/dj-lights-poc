"""HTTP client for WLED's JSON API.

Phase 6 only needs ``GET /json/info`` (LED count + capability flags) so we
can drive calibration. ``GET /json/state`` is included so callers can read
the current state without a second tool. No auth — WLED has none, and we
treat the LAN as the trust boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(frozen=True, slots=True)
class WledInfo:
    """Subset of ``/json/info`` we actually use.

    ``led_count`` is the number of physical LEDs, used by the live-WS decoder
    to compute the downsampling factor (WLED caps the live stream at 1024
    LEDs and serves every nth pixel above that).
    """

    name: str
    version: str
    mac: str
    led_count: int
    fps: int
    raw: dict[str, Any]


class WledClient:
    """Tiny async HTTP wrapper. Holds no connection state; one per call."""

    def __init__(self, base_url: str, *, timeout_s: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self._timeout = timeout_s

    async def info(self) -> WledInfo:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self.base_url}/json/info")
            resp.raise_for_status()
            data = resp.json()
        return _parse_info(data)

    async def state(self) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(f"{self.base_url}/json/state")
            resp.raise_for_status()
        data: dict[str, Any] = resp.json()
        return data


def _parse_info(data: dict[str, Any]) -> WledInfo:
    leds = data.get("leds", {})
    return WledInfo(
        name=str(data.get("name", "")),
        version=str(data.get("ver", "")),
        mac=str(data.get("mac", "")),
        led_count=int(leds.get("count", 0)),
        fps=int(leds.get("fps", 0)),
        raw=data,
    )
