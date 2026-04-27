"""WS bridge smoke: arms a preset, sends a manual trigger, checks frames flow."""

from __future__ import annotations

import asyncio
import json
import struct
import sys
import urllib.request

import websockets


async def run(backend: str) -> None:
    arm = urllib.request.Request(
        f"{backend.replace('ws://', 'http://').replace('wss://', 'https://')}/api/presets/beat-pulse/arm",
        method="POST",
    )
    urllib.request.urlopen(arm).read()  # noqa: S310 - local smoke test
    ws_url = backend.replace("http://", "ws://").replace("https://", "wss://") + "/ws/bridge"
    async with websockets.connect(ws_url) as ws:
        await ws.send(
            json.dumps({"kind": "manual", "timestamp_ms": 0, "payload": {"action": "trigger"}})
        )
        for _ in range(3):
            data = await ws.recv()
            assert isinstance(data, (bytes, bytearray)), f"unexpected text: {data!r}"
            v, n, t = struct.unpack(">HHd", data[:12])
            assert n == 5, f"expected 5 bars in sample-5bar, got {n}"
            print(f"frame v={v} bars={n} t={t:.1f}ms bytes={len(data)}")


if __name__ == "__main__":
    backend = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    asyncio.run(run(backend))
