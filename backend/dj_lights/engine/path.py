"""Spatial ordering of LED segments around a stage perimeter.

The :class:`Chase` effect can walk LEDs in any order. By default it walks them
in bar-declaration order, which is fine for a "bus" of bars but wrong for a
horseshoe arrangement: a clockwise spin should run from the top of the right
vertical, down to the floor, across the front bars right-to-left, and up to
the top of the left vertical.

This module computes that perimeter path once per layout. It is generic — for
any reasonable arrangement of bars it produces a continuous walk that follows
polar angle around the stage centre, choosing the within-bar segment direction
that minimises the angular jump between bars.
"""

from __future__ import annotations

import math
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal

from .frame import Bar, StageLayout

PathStep = tuple[str, int]  # (bar_id, segment_index)


def _segment_xy(bar: Bar, idx: int) -> tuple[float, float]:
    if bar.segments == 1:
        local = 0.0
    else:
        local = -bar.length_m / 2 + (idx / (bar.segments - 1)) * bar.length_m
    cos = math.cos(bar.pose.rotation_rad)
    sin = math.sin(bar.pose.rotation_rad)
    return (bar.pose.x_m + local * cos, bar.pose.y_m + local * sin)


def _polar(x: float, y: float) -> float:
    return math.atan2(y, x)


@dataclass(frozen=True)
class PerimeterPath:
    """An ordered list of (bar_id, segment_index) walking around the stage."""

    layout_version: int
    direction: Literal["cw", "ccw"]
    steps: tuple[PathStep, ...]

    def __len__(self) -> int:
        return len(self.steps)

    def __iter__(self) -> Iterator[PathStep]:
        return iter(self.steps)


def compute_perimeter_path(
    layout: StageLayout,
    *,
    direction: Literal["cw", "ccw"] = "cw",
    layout_version: int = 0,
) -> PerimeterPath:
    """Order every segment in the layout by stage-perimeter sweep.

    Algorithm:

    1. Sort bars by polar angle of their centre (ascending = CCW).
    2. For ``cw``, reverse the list.
    3. Rotate the list so the path starts at the "12 o'clock" corner of the
       stage — top-right for ``cw``, top-left for ``ccw``. This matches the
       intuition that a clockwise spin on a horseshoe should start at the top
       of the right vertical bar.
    4. For each bar, choose forward or reversed segment order so that the
       first segment is closest to the previous bar's exit position, keeping
       the walk continuous.
    """

    bars = list(layout.bars)
    if not bars:
        return PerimeterPath(layout_version=layout_version, direction=direction, steps=())

    bars_sorted = sorted(bars, key=lambda b: _polar(b.pose.x_m, b.pose.y_m))
    if direction == "cw":
        bars_sorted.reverse()

    if direction == "cw":
        start_idx = max(
            range(len(bars_sorted)),
            key=lambda i: (bars_sorted[i].pose.y_m, bars_sorted[i].pose.x_m),
        )
    else:
        start_idx = max(
            range(len(bars_sorted)),
            key=lambda i: (bars_sorted[i].pose.y_m, -bars_sorted[i].pose.x_m),
        )
    bars_sorted = bars_sorted[start_idx:] + bars_sorted[:start_idx]

    seed_x = layout.width_m / 2 if direction == "cw" else -layout.width_m / 2
    seed_y = layout.depth_m / 2
    last_xy: tuple[float, float] = (seed_x, seed_y)

    steps: list[PathStep] = []
    for bar in bars_sorted:
        forward = list(range(bar.segments))
        backward = list(reversed(forward))
        f_first = _segment_xy(bar, forward[0])
        b_first = _segment_xy(bar, backward[0])
        f_dist = math.hypot(f_first[0] - last_xy[0], f_first[1] - last_xy[1])
        b_dist = math.hypot(b_first[0] - last_xy[0], b_first[1] - last_xy[1])
        chosen = forward if f_dist <= b_dist else backward
        for i in chosen:
            steps.append((bar.id, i))
        last_xy = _segment_xy(bar, chosen[-1])

    return PerimeterPath(layout_version=layout_version, direction=direction, steps=tuple(steps))
