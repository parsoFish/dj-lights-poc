"""Core scene & frame types.

These dataclasses are immutable (frozen) so frames can be safely passed across
async tasks and serialised to wire formats without copy hazards. The hot path
allocates a new ``LedFrame`` per tick rather than mutating in place — clarity
over micro-perf for the POC. If profiling shows this matters later, swap to a
preallocated numpy buffer behind the same public surface.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Self


@dataclass(frozen=True, slots=True)
class Pose2D:
    """Top-down stage placement: metres + radians, origin at stage centre."""

    x_m: float
    y_m: float
    rotation_rad: float = 0.0


RGB = tuple[int, int, int]
BLACK: RGB = (0, 0, 0)


@dataclass(frozen=True, slots=True)
class Bar:
    """A single RGB bar with N evenly-spaced LED segments along its length.

    ``length_m`` is the physical length; ``segments`` is the number of
    addressable cells. The bar's local x-axis runs along its length; ``pose``
    places its centre on the stage.
    """

    id: str
    length_m: float
    segments: int
    pose: Pose2D

    def __post_init__(self) -> None:
        if self.segments < 1:
            raise ValueError(f"bar {self.id!r}: segments must be >= 1, got {self.segments}")
        if self.length_m <= 0:
            raise ValueError(f"bar {self.id!r}: length_m must be > 0, got {self.length_m}")


@dataclass(frozen=True, slots=True)
class StageLayout:
    """A named arrangement of bars within a rectangular stage."""

    name: str
    width_m: float
    depth_m: float
    bars: tuple[Bar, ...] = field(default_factory=tuple)

    @property
    def total_segments(self) -> int:
        return sum(b.segments for b in self.bars)

    def with_bar(self, bar: Bar) -> Self:
        if any(b.id == bar.id for b in self.bars):
            raise ValueError(f"bar id {bar.id!r} already present in layout {self.name!r}")
        return type(self)(
            name=self.name,
            width_m=self.width_m,
            depth_m=self.depth_m,
            bars=(*self.bars, bar),
        )

    def without_bar(self, bar_id: str) -> Self:
        if not any(b.id == bar_id for b in self.bars):
            raise ValueError(f"bar id {bar_id!r} not in layout {self.name!r}")
        return type(self)(
            name=self.name,
            width_m=self.width_m,
            depth_m=self.depth_m,
            bars=tuple(b for b in self.bars if b.id != bar_id),
        )


@dataclass(frozen=True, slots=True)
class BarFrame:
    """RGB values for every segment in one bar at one tick."""

    bar_id: str
    pixels: tuple[RGB, ...]


@dataclass(frozen=True, slots=True)
class LedFrame:
    """Snapshot of every bar's segments at one tick of the engine loop."""

    layout_version: int
    timestamp_ms: float
    bars: tuple[BarFrame, ...]

    @classmethod
    def black(cls, layout: StageLayout, *, timestamp_ms: float = 0.0, layout_version: int = 0) -> LedFrame:
        return cls(
            layout_version=layout_version,
            timestamp_ms=timestamp_ms,
            bars=tuple(
                BarFrame(bar_id=b.id, pixels=tuple(BLACK for _ in range(b.segments))) for b in layout.bars
            ),
        )

    def total_pixels(self) -> int:
        return sum(len(b.pixels) for b in self.bars)
