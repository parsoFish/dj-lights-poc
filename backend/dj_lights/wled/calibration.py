"""Calibration: which slice of WLED pixels maps to which bar in the layout.

A WLED node is one long strip from the firmware's perspective even when
physically wired as several segments. Calibration lets the user say "pixels
0..23 of this device are the right-vertical bar; pixels 24..43 are the front-
right bar" and so on. The mapping is stored as JSON next to the layout file.

The mapping is intentionally a list of bindings (not a dict by bar id) so a
single bar could in principle be fed from two devices, or a binding could be
disabled without removing it. Phase 6 only exercises one binding per bar, but
the shape doesn't paint us into a corner.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ..engine.frame import RGB, BarFrame, LedFrame, StageLayout


@dataclass(frozen=True, slots=True)
class WledBinding:
    """One slice of a WLED device's pixel string mapped onto a bar.

    ``pixel_start`` is inclusive, ``pixel_end`` is exclusive — the same
    half-open interval Python uses for slices. ``reverse`` flips the order
    along the bar (handy when the strip was wired tail-first).
    """

    device_id: str
    pixel_start: int
    pixel_end: int
    bar_id: str
    reverse: bool = False

    @property
    def pixel_count(self) -> int:
        return max(0, self.pixel_end - self.pixel_start)

    def to_dict(self) -> dict[str, object]:
        return {
            "device_id": self.device_id,
            "pixel_start": self.pixel_start,
            "pixel_end": self.pixel_end,
            "bar_id": self.bar_id,
            "reverse": self.reverse,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WledBinding:
        start = data["pixel_start"]
        end = data["pixel_end"]
        if not isinstance(start, int | float) or not isinstance(end, int | float):
            raise ValueError("pixel_start and pixel_end must be numbers")
        return cls(
            device_id=str(data["device_id"]),
            pixel_start=int(start),
            pixel_end=int(end),
            bar_id=str(data["bar_id"]),
            reverse=bool(data.get("reverse", False)),
        )


@dataclass(frozen=True, slots=True)
class WledCalibration:
    """A named bundle of bindings — one per layout."""

    layout_name: str
    bindings: tuple[WledBinding, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "layout_name": self.layout_name,
            "bindings": [b.to_dict() for b in self.bindings],
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> WledCalibration:
        raw = data.get("bindings", [])
        if not isinstance(raw, list):
            raise ValueError("bindings must be a list")
        return cls(
            layout_name=str(data["layout_name"]),
            bindings=tuple(WledBinding.from_dict(b) for b in raw),
        )


def apply_bindings(
    layout: StageLayout,
    device_pixels: dict[str, tuple[RGB, ...]],
    bindings: tuple[WledBinding, ...],
    *,
    layout_version: int = 0,
    timestamp_ms: float = 0.0,
) -> LedFrame:
    """Translate per-device WLED pixel arrays into a layout-shaped LedFrame.

    Pixels not covered by any binding default to black. Bindings whose
    pixel_count doesn't match their bar's segment count are stretched or
    truncated cleanly — we map by index, not by interpolation.
    """

    by_bar: dict[str, list[RGB]] = {b.id: [(0, 0, 0)] * b.segments for b in layout.bars}

    for binding in bindings:
        pixels = device_pixels.get(binding.device_id)
        if pixels is None:
            continue
        target = by_bar.get(binding.bar_id)
        if target is None:
            continue
        slice_ = pixels[binding.pixel_start : binding.pixel_end]
        if binding.reverse:
            slice_ = slice_[::-1]
        n_seg = len(target)
        n_src = len(slice_)
        if n_src == 0 or n_seg == 0:
            continue
        for i in range(n_seg):
            src_idx = min(n_src - 1, (i * n_src) // n_seg)
            target[i] = slice_[src_idx]

    return LedFrame(
        layout_version=layout_version,
        timestamp_ms=timestamp_ms,
        bars=tuple(BarFrame(bar_id=bid, pixels=tuple(p)) for bid, p in by_bar.items()),
    )


class CalibrationStore:
    """JSON-on-disk persistence for `WledCalibration` (one file per layout)."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, layout_name: str) -> Path:
        if "/" in layout_name or ".." in layout_name:
            raise ValueError(f"invalid layout name: {layout_name!r}")
        return self.root / f"{layout_name}.calibration.json"

    def load(self, layout_name: str) -> WledCalibration:
        path = self._path(layout_name)
        if not path.exists():
            return WledCalibration(layout_name=layout_name, bindings=())
        return WledCalibration.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def save(self, calibration: WledCalibration) -> None:
        self._path(calibration.layout_name).write_text(
            json.dumps(calibration.to_dict(), indent=2), encoding="utf-8"
        )
