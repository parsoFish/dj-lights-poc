"""Composable lighting effects.

Effects are pure functions of (layout, time, state). They are reusable across
presets — a ``Pulse`` can be triggered by a beat, a manual button, or any
future event source. Future agents add new effects here without touching the
engine.

Each effect owns a small ``state`` dict given to it by its preset; presets are
responsible for instantiating and updating that state in response to events.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .frame import RGB, Bar, BarFrame, LedFrame, StageLayout


class Effect(Protocol):
    """A function-shaped object that produces a frame from layout + time + state."""

    def render(
        self,
        layout: StageLayout,
        t_ms: float,
        state: dict[str, Any],
    ) -> LedFrame:  # pragma: no cover - protocol
        ...


# --- helpers -----------------------------------------------------------------


def _scale(rgb: RGB, k: float) -> RGB:
    k = max(0.0, min(1.0, k))
    return (int(rgb[0] * k), int(rgb[1] * k), int(rgb[2] * k))


def _frame_from_per_bar(
    layout: StageLayout,
    t_ms: float,
    *,
    layout_version: int,
    pixels_for: dict[str, tuple[RGB, ...]],
) -> LedFrame:
    return LedFrame(
        layout_version=layout_version,
        timestamp_ms=t_ms,
        bars=tuple(
            BarFrame(
                bar_id=b.id,
                pixels=pixels_for.get(b.id, tuple((0, 0, 0) for _ in range(b.segments))),
            )
            for b in layout.bars
        ),
    )


# --- effects ----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Pulse:
    """Whole-bar pulse: instant on at trigger, exponential decay over ``decay_ms``."""

    color: RGB = (255, 255, 255)
    decay_ms: float = 250.0

    def render(self, layout: StageLayout, t_ms: float, state: dict[str, Any]) -> LedFrame:
        last_trigger = state.get("last_trigger_ms")
        version = int(state.get("layout_version", 0))
        if last_trigger is None:
            return LedFrame.black(layout, timestamp_ms=t_ms, layout_version=version)
        dt = max(0.0, t_ms - float(last_trigger))
        k = pow(0.5, dt / self.decay_ms) if self.decay_ms > 0 else 0.0
        col = _scale(self.color, k)
        return _frame_from_per_bar(
            layout,
            t_ms,
            layout_version=version,
            pixels_for={b.id: tuple(col for _ in range(b.segments)) for b in layout.bars},
        )


def _default_spot_radius(layout: StageLayout) -> float:
    """Half the longer stage edge.

    Tightens the falloff so a hand pointed at one bar leaves the others
    visibly dark, not dimly glowing. We tried the full diagonal first (every
    bar half-lit) and then half the diagonal (verticals still picked up too
    much spillover for a 6m by 2.5m stage); ``max(w, d) * 0.5`` keeps the
    spot focused on roughly one bar's worth of stage at any time.
    """

    return max(max(layout.width_m, layout.depth_m) * 0.5, 1.0)


def _segment_xy(bar: Bar, idx: int) -> tuple[float, float]:
    import math

    if bar.segments == 1:
        local = 0.0
    else:
        local = -bar.length_m / 2 + (idx / (bar.segments - 1)) * bar.length_m
    return (
        bar.pose.x_m + local * math.cos(bar.pose.rotation_rad),
        bar.pose.y_m + local * math.sin(bar.pose.rotation_rad),
    )


@dataclass(frozen=True, slots=True)
class Spotlight:
    """Soft circular spotlight, focal point given in normalised pad coords.

    The "pad" is a top-down map of the stage:

    - ``state["spot_x"]`` in [0,1] across the stage width (0 = stage-left,
      1 = stage-right).
    - ``state["spot_y"]`` in [0,1] from stage-back (0) to audience side (1).

    Intensity is uniform — position determines which bars are lit, falloff
    around ``radius_m`` does the rest. We previously coupled ``pad_y`` to a
    global brightness so pad-top read as "off", but that made it impossible
    to fully light the top of vertical bars (which physically *are* at the
    stage back). Disarming the preset is the correct way to turn it off.
    """

    color: RGB = (255, 255, 255)
    radius_m: float | None = None

    def render(self, layout: StageLayout, t_ms: float, state: dict[str, Any]) -> LedFrame:
        import math

        pad_x = max(0.0, min(1.0, float(state.get("spot_x", 0.5))))
        pad_y = max(0.0, min(1.0, float(state.get("spot_y", 0.5))))
        sx = (pad_x - 0.5) * layout.width_m
        sy = (0.5 - pad_y) * layout.depth_m
        radius = self.radius_m if self.radius_m is not None else _default_spot_radius(layout)
        version = int(state.get("layout_version", 0))
        per_bar: dict[str, tuple[RGB, ...]] = {}
        for bar in layout.bars:
            pixels: list[RGB] = []
            for i in range(bar.segments):
                cx, cy = _segment_xy(bar, i)
                d = math.hypot(cx - sx, cy - sy)
                falloff = max(0.0, 1.0 - d / radius) if radius > 0 else 0.0
                pixels.append(_scale(self.color, falloff))
            per_bar[bar.id] = tuple(pixels)
        return _frame_from_per_bar(layout, t_ms, layout_version=version, pixels_for=per_bar)


@dataclass(frozen=True, slots=True)
class RadialPulse:
    """Pulse that propagates outward from stage centre.

    Multiple pulses can be in flight at once: the preset that drives this
    effect appends a fresh trigger time to ``state["wave_starts"]`` per beat,
    and this effect renders the brightest contribution from any wave at each
    segment. That keeps an earlier wave climbing the verticals visible even
    when a fresh wave fires from the centre — the previous behaviour clobbered
    the in-flight wave and read as a flicker at low BPMs.

    Each segment lights up when its wave's wavefront reaches it (``distance /
    speed``) and decays with a ``decay_ms`` half-life thereafter. Old waves
    that have decayed past visibility are culled in-place to keep the state
    list bounded.
    """

    color: RGB = (255, 120, 0)
    decay_ms: float = 700.0
    wave_speed_m_per_s: float = 3.0
    cull_after_half_lives: float = 6.0

    def render(self, layout: StageLayout, t_ms: float, state: dict[str, Any]) -> LedFrame:
        import math

        version = int(state.get("layout_version", 0))
        wave_starts_raw = state.get("wave_starts")
        if not wave_starts_raw:
            return LedFrame.black(layout, timestamp_ms=t_ms, layout_version=version)

        max_radius_m = math.hypot(layout.width_m, layout.depth_m) / 2.0
        max_arrival_ms = (max_radius_m / self.wave_speed_m_per_s) * 1000.0
        max_age_ms = max_arrival_ms + self.decay_ms * self.cull_after_half_lives
        wave_starts = [float(t) for t in wave_starts_raw if (t_ms - float(t)) <= max_age_ms]
        state["wave_starts"] = wave_starts
        if not wave_starts:
            return LedFrame.black(layout, timestamp_ms=t_ms, layout_version=version)

        per_bar: dict[str, tuple[RGB, ...]] = {}
        for bar in layout.bars:
            pixels: list[RGB] = []
            for i in range(bar.segments):
                cx, cy = _segment_xy(bar, i)
                d_m = math.hypot(cx, cy)
                arrival_ms = (d_m / self.wave_speed_m_per_s) * 1000.0
                best_k = 0.0
                for trigger in wave_starts:
                    age_ms = (t_ms - trigger) - arrival_ms
                    if age_ms < 0:
                        continue
                    k = pow(0.5, age_ms / self.decay_ms) if self.decay_ms > 0 else 0.0
                    if k > best_k:
                        best_k = k
                pixels.append(_scale(self.color, best_k))
            per_bar[bar.id] = tuple(pixels)
        return _frame_from_per_bar(layout, t_ms, layout_version=version, pixels_for=per_bar)


@dataclass(frozen=True, slots=True)
class Chase:
    """A travelling pixel that walks LEDs along a configurable path.

    The path is taken from ``state["path"]`` as a sequence of ``(bar_id,
    segment_index)`` tuples; if absent, segments are visited in
    bar-declaration order. Presets that need spatial awareness (e.g. a
    clockwise sweep around a horseshoe) pass a path computed via
    :mod:`dj_lights.engine.path`.

    ``state["progress"]`` is a 0..1 fraction along the path.
    """

    color: RGB = (255, 64, 0)
    tail_segments: int = 6

    def render(self, layout: StageLayout, t_ms: float, state: dict[str, Any]) -> LedFrame:
        version = int(state.get("layout_version", 0))
        path = state.get("path")
        path_steps: tuple[tuple[str, int], ...]
        if path is None:
            path_steps = tuple(
                (bar.id, i) for bar in layout.bars for i in range(bar.segments)
            )
        else:
            path_steps = tuple(path)

        total = len(path_steps)
        if total == 0:
            return LedFrame.black(layout, timestamp_ms=t_ms, layout_version=version)

        progress = float(state.get("progress", 0.0)) % 1.0
        head = int(progress * total) % total

        per_bar: dict[str, list[RGB]] = {b.id: [(0, 0, 0)] * b.segments for b in layout.bars}
        for offset_back in range(self.tail_segments):
            step_idx = (head - offset_back) % total
            bar_id, seg_idx = path_steps[step_idx]
            target = per_bar.get(bar_id)
            if target is None or seg_idx >= len(target):
                continue
            k = 1.0 - offset_back / self.tail_segments
            target[seg_idx] = _scale(self.color, k)

        return _frame_from_per_bar(
            layout,
            t_ms,
            layout_version=version,
            pixels_for={bid: tuple(pixels) for bid, pixels in per_bar.items()},
        )
