"""JSON load/save for :class:`StageLayout`.

Schema (matches the type, intentionally trivial):

::

    {
      "name": "sample-5bar",
      "width_m": 6.0,
      "depth_m": 2.5,
      "bars": [
        {
          "id": "left-vertical",
          "length_m": 1.8,
          "segments": 24,
          "pose": {"x_m": -2.8, "y_m": 0.0, "rotation_rad": 1.5708}
        },
        ...
      ]
    }
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..engine.frame import Bar, Pose2D, StageLayout


def bar_from_dict(d: dict[str, Any]) -> Bar:
    pose = d["pose"]
    return Bar(
        id=str(d["id"]),
        length_m=float(d["length_m"]),
        segments=int(d["segments"]),
        pose=Pose2D(
            x_m=float(pose["x_m"]),
            y_m=float(pose["y_m"]),
            rotation_rad=float(pose.get("rotation_rad", 0.0)),
        ),
    )


def bar_to_dict(b: Bar) -> dict[str, Any]:
    return {
        "id": b.id,
        "length_m": b.length_m,
        "segments": b.segments,
        "pose": {
            "x_m": b.pose.x_m,
            "y_m": b.pose.y_m,
            "rotation_rad": b.pose.rotation_rad,
        },
    }


def layout_to_dict(layout: StageLayout) -> dict[str, Any]:
    return {
        "name": layout.name,
        "width_m": layout.width_m,
        "depth_m": layout.depth_m,
        "bars": [bar_to_dict(b) for b in layout.bars],
    }


def layout_from_json(text: str) -> StageLayout:
    data = json.loads(text)
    return StageLayout(
        name=str(data["name"]),
        width_m=float(data["width_m"]),
        depth_m=float(data["depth_m"]),
        bars=tuple(bar_from_dict(b) for b in data.get("bars", [])),
    )


def layout_to_json(layout: StageLayout) -> str:
    return json.dumps(layout_to_dict(layout), indent=2)


class LayoutStore:
    """Per-name JSON files in a directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, name: str) -> Path:
        if "/" in name or ".." in name:
            raise ValueError(f"invalid layout name: {name!r}")
        return self.root / f"{name}.json"

    def list(self) -> list[str]:
        return sorted(p.stem for p in self.root.glob("*.json"))

    def load(self, name: str) -> StageLayout:
        return layout_from_json(self._path(name).read_text(encoding="utf-8"))

    def save(self, layout: StageLayout) -> None:
        self._path(layout.name).write_text(layout_to_json(layout), encoding="utf-8")
