"""WebSocket bridge between browser and engine.

* ``/ws/frames`` — server pushes binary :class:`LedFrame` packets to clients.
* ``/ws/events`` — clients push JSON events; the matching :class:`PushSource`
  forwards them onto the bus.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from ..engine.events import KNOWN_KINDS, Event
from ..inputs.base import PushSource
from ..outputs.simulator import encode_frame
from .state import AppState

logger = logging.getLogger(__name__)
router = APIRouter()


def _state(req: Request | WebSocket) -> AppState:
    state: AppState = req.app.state.dj_lights
    return state


@router.websocket("/ws/frames")
async def frames_ws(ws: WebSocket) -> None:
    await ws.accept()
    s = _state(ws)
    q = s.engine.subscribe_frames()
    try:
        while True:
            frame = await q.get()
            await ws.send_bytes(encode_frame(frame))
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ConnectionError) as exc:
        logger.info("frames_ws closed: %s", exc)
    finally:
        s.engine.unsubscribe_frames(q)


def _coerce_payload(kind: str, raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError("payload must be an object")
    if kind not in KNOWN_KINDS:
        raise ValueError(f"unknown event kind: {kind!r}")
    return raw


def _route_for_kind(s: AppState, kind: str) -> PushSource:
    if kind == "beat":
        return s.sources["audio"]
    if kind == "hand_position":
        return s.sources["cv-hands"]
    return s.sources["manual"]


@router.websocket("/ws/events")
async def events_ws(ws: WebSocket) -> None:
    await ws.accept()
    s = _state(ws)
    try:
        while True:
            text = await ws.receive_text()
            try:
                msg = json.loads(text)
                kind = str(msg.get("kind"))
                payload = _coerce_payload(kind, msg.get("payload", {}))
                ts = float(msg.get("timestamp_ms") or time.monotonic() * 1000.0)
                event = Event(kind=kind, timestamp_ms=ts, payload=payload)  # type: ignore[arg-type]
            except (ValueError, TypeError, json.JSONDecodeError) as exc:
                await ws.send_text(json.dumps({"error": str(exc)}))
                continue
            await _route_for_kind(s, kind).publish(event)
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ConnectionError) as exc:
        logger.info("events_ws closed: %s", exc)


@router.websocket("/ws/bridge")
async def bridge_ws(ws: WebSocket) -> None:
    """Combined frames-out / events-in connection for the simple frontend.

    Frontend sends JSON event messages; server interleaves outbound binary
    frames. Useful so the SPA only needs one socket.
    """

    await ws.accept()
    s = _state(ws)
    q = s.engine.subscribe_frames()

    async def pump_frames() -> None:
        try:
            while True:
                frame = await q.get()
                await ws.send_bytes(encode_frame(frame))
        except (RuntimeError, ConnectionError, WebSocketDisconnect):
            pass

    async def read_events() -> None:
        try:
            while True:
                text = await ws.receive_text()
                try:
                    msg = json.loads(text)
                    kind = str(msg.get("kind"))
                    payload = _coerce_payload(kind, msg.get("payload", {}))
                    ts = float(msg.get("timestamp_ms") or time.monotonic() * 1000.0)
                    event = Event(kind=kind, timestamp_ms=ts, payload=payload)  # type: ignore[arg-type]
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    await ws.send_text(json.dumps({"error": str(exc)}))
                    continue
                await _route_for_kind(s, kind).publish(event)
        except (RuntimeError, ConnectionError, WebSocketDisconnect):
            pass

    sender = asyncio.create_task(pump_frames())
    reader = asyncio.create_task(read_events())
    try:
        _done, pending = await asyncio.wait(
            {sender, reader}, return_when=asyncio.FIRST_COMPLETED
        )
        for t in pending:
            t.cancel()
    finally:
        s.engine.unsubscribe_frames(q)
