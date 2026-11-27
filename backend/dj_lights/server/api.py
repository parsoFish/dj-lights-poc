"""REST endpoints: layouts, presets, WLED."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from ..engine.frame import Bar, Pose2D, StageLayout
from ..engine.presets import Preset
from ..storage.layout_store import layout_to_dict
from ..wled.calibration import WledBinding, WledCalibration
from ..wled.client import WledClient
from ..wled.discovery import WledNode, manual_node
from ..wled.live_ws import WledLiveSubscriber
from ..wled.mirror import WledMirror
from .state import AppState

router = APIRouter(prefix="/api")


def _state(req: Request) -> AppState:
    state: AppState = req.app.state.dj_lights
    return state


def _preset_meta(p: Preset) -> dict[str, Any]:
    return {
        "name": p.name,
        "triggers": list(p.triggers),
        "armed": False,
    }


@router.get("/layouts")
def list_layouts(req: Request) -> dict[str, list[str]]:
    return {"layouts": _state(req).store.list()}


@router.get("/layouts/{name}")
def get_layout(name: str, req: Request) -> dict[str, Any]:
    s = _state(req)
    try:
        layout = s.store.load(name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"layout {name!r} not found") from exc
    return layout_to_dict(layout)


@router.put("/layouts/{name}")
async def put_layout(name: str, body: dict[str, Any], req: Request) -> dict[str, Any]:
    s = _state(req)
    try:
        layout = StageLayout(
            name=name,
            width_m=float(body["width_m"]),
            depth_m=float(body["depth_m"]),
            bars=tuple(
                Bar(
                    id=str(b["id"]),
                    length_m=float(b["length_m"]),
                    segments=int(b["segments"]),
                    pose=Pose2D(
                        x_m=float(b["pose"]["x_m"]),
                        y_m=float(b["pose"]["y_m"]),
                        rotation_rad=float(b["pose"].get("rotation_rad", 0.0)),
                    ),
                )
                for b in body.get("bars", [])
            ),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid layout: {exc}") from exc
    s.store.save(layout)
    s.engine.replace_layout(layout)
    return layout_to_dict(layout)


@router.get("/presets")
def list_presets(req: Request) -> dict[str, list[dict[str, Any]]]:
    s = _state(req)
    armed = set(s.engine.active_presets.keys())
    items = []
    for p in s.presets.values():
        meta = _preset_meta(p)
        meta["armed"] = p.name in armed
        items.append(meta)
    return {"presets": items}


@router.post("/presets/{name}/arm")
def arm_preset(name: str, req: Request) -> dict[str, Any]:
    s = _state(req)
    preset = s.presets.get(name)
    if preset is None:
        raise HTTPException(status_code=404, detail=f"unknown preset {name!r}")
    s.engine.arm(preset)
    return {"name": name, "armed": True}


@router.post("/presets/{name}/disarm")
def disarm_preset(name: str, req: Request) -> dict[str, Any]:
    s = _state(req)
    s.engine.disarm(name)
    return {"name": name, "armed": False}


# --- WLED -------------------------------------------------------------------


def _node_to_dict(n: WledNode) -> dict[str, Any]:
    return {
        "id": n.id,
        "name": n.name,
        "host": n.host,
        "port": n.port,
        "source": n.source,
    }


@router.get("/wled/devices")
def list_wled_devices(req: Request) -> dict[str, list[dict[str, Any]]]:
    return {"devices": [_node_to_dict(n) for n in _state(req).wled_registry.all()]}


@router.post("/wled/devices")
def add_wled_device(body: dict[str, Any], req: Request) -> dict[str, Any]:
    s = _state(req)
    host = str(body.get("host", "")).strip()
    if not host:
        raise HTTPException(status_code=400, detail="host required")
    port = int(body.get("port", 80))
    name = body.get("name")
    node = manual_node(host, name=name if isinstance(name, str) else None, port=port)
    s.wled_registry.add(node)
    return _node_to_dict(node)


@router.get("/wled/devices/{device_id}")
async def get_wled_device(device_id: str, req: Request) -> dict[str, Any]:
    s = _state(req)
    node = s.wled_registry.get(device_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown WLED device {device_id!r}")
    client = WledClient(node.http_base)
    try:
        info = await client.info()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"WLED unreachable: {exc}") from exc
    return {
        **_node_to_dict(node),
        "info": {
            "name": info.name,
            "version": info.version,
            "mac": info.mac,
            "led_count": info.led_count,
            "fps": info.fps,
        },
    }


@router.get("/wled/calibration/{layout_name}")
def get_calibration(layout_name: str, req: Request) -> dict[str, Any]:
    s = _state(req)
    cal = s.calibration_store.load(layout_name)
    return cal.to_dict()


@router.put("/wled/calibration/{layout_name}")
def put_calibration(layout_name: str, body: dict[str, Any], req: Request) -> dict[str, Any]:
    s = _state(req)
    raw_bindings = body.get("bindings", [])
    if not isinstance(raw_bindings, list):
        raise HTTPException(status_code=400, detail="bindings must be a list")
    try:
        cal = WledCalibration(
            layout_name=layout_name,
            bindings=tuple(WledBinding.from_dict(b) for b in raw_bindings),
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=400, detail=f"invalid binding: {exc}") from exc
    s.calibration_store.save(cal)
    # If the mirror is active for this layout, refresh its calibration.
    if s.wled_mirror is not None and s.wled_mirror.calibration.layout_name == layout_name:
        s.wled_mirror.calibration = cal
    return cal.to_dict()


@router.post("/wled/mirror/start")
async def start_mirror(body: dict[str, Any], req: Request) -> dict[str, Any]:
    s = _state(req)
    if s.wled_mirror is not None:
        raise HTTPException(status_code=409, detail="mirror already running; stop it first")
    device_id = str(body.get("device_id", ""))
    node = s.wled_registry.get(device_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown WLED device {device_id!r}")
    client = WledClient(node.http_base)
    try:
        info = await client.info()
    except (httpx.HTTPError, OSError) as exc:
        raise HTTPException(status_code=502, detail=f"WLED unreachable: {exc}") from exc

    cal = s.calibration_store.load(s.layout_name)
    mirror = WledMirror(
        layout=s.engine.layout,
        calibration=cal,
        on_frame=_engine_frame_pusher(s),
        layout_version=s.engine.layout_version,
    )
    sub = WledLiveSubscriber(
        node.ws_url, device_id=device_id, total_leds=info.led_count or None,
    )
    mirror.add_subscriber(sub, device_id)
    s.wled_mirror = mirror
    s.engine.mirror_mode = True
    return {"mirroring": True, "device_id": device_id, "led_count": info.led_count}


@router.post("/wled/mirror/stop")
async def stop_mirror(req: Request) -> dict[str, Any]:
    s = _state(req)
    if s.wled_mirror is not None:
        await s.wled_mirror.stop()
        s.wled_mirror = None
    s.engine.mirror_mode = False
    return {"mirroring": False}


def _engine_frame_pusher(s: AppState) -> Any:
    async def _push(frame: Any) -> None:
        s.engine.push_external_frame(frame)
        # Yield control so backpressure on consumers can take effect.
        await asyncio.sleep(0)

    return _push
