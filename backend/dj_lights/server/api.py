"""REST endpoints: layouts, presets."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Request

from ..engine.frame import Bar, Pose2D, StageLayout
from ..engine.presets import Preset
from ..storage.layout_store import layout_to_dict
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
