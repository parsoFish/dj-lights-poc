"""Presets bind events to effects.

A preset is the authoring unit a DJ thinks in: "when X happens, do Y to Z".
For the POC each preset is a hand-written Python class. Future work can move
this to a JSON/YAML DSL so presets can be authored in-app.

Future agents add a new preset by subclassing :class:`Preset`, declaring which
event kinds it listens for, mutating its own ``state`` dict in ``on_event``,
and delegating rendering to one of the composable :mod:`effects`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from .effects import Chase, Effect, Pulse, RadialPulse, Spotlight
from .events import Event, EventKind
from .frame import RGB, LedFrame, StageLayout
from .path import PerimeterPath, compute_perimeter_path


class Preset(Protocol):
    """A trigger -> effect binding with private state."""

    name: str
    triggers: tuple[EventKind, ...]
    state: dict[str, Any]

    def on_event(self, event: Event) -> None:  # pragma: no cover - protocol
        ...

    def render(self, layout: StageLayout, t_ms: float) -> LedFrame:  # pragma: no cover - protocol
        ...


@dataclass
class BeatPulse:
    """Pulse all bars on every beat event.

    Triggers: ``beat`` events from the audio detector, or ``manual`` events
    with payload ``{"action": "trigger"}`` so the demo is reachable without a
    microphone (a "Trigger" button in the UI is enough).

    Same clock discipline as :class:`SpinChase`: ``on_event`` only flags that a
    trigger has arrived; ``render`` syncs to engine time so visual decay isn't
    distorted by the producer's clock.
    """

    name: str = "beat-pulse"
    triggers: tuple[EventKind, ...] = ("beat", "manual")
    color: RGB = (60, 200, 255)
    decay_ms: float = 350.0
    state: dict[str, Any] = field(default_factory=dict)
    _effect: Effect = field(init=False)

    def __post_init__(self) -> None:
        self._effect = Pulse(color=self.color, decay_ms=self.decay_ms)

    def on_event(self, event: Event) -> None:
        is_beat = event.kind == "beat"
        is_manual_trigger = (
            event.kind == "manual" and event.payload.get("action") == "trigger"
        )
        if is_beat or is_manual_trigger:
            self.state["pulse_pending"] = True

    def render(self, layout: StageLayout, t_ms: float) -> LedFrame:
        if self.state.pop("pulse_pending", False):
            self.state["last_trigger_ms"] = t_ms
        return self._effect.render(layout, t_ms, self.state)


@dataclass
class BeatPulseRadial:
    """Pulse that propagates outward from stage centre on each beat.

    Same trigger as :class:`BeatPulse` but uses a wave-propagation effect
    instead of a uniform pulse. Demonstrates that the modular preset system
    lets future agents bind any (trigger, effect) pair without changes to
    the engine — same beats, different visuals.
    """

    name: str = "beat-pulse-radial"
    triggers: tuple[EventKind, ...] = ("beat", "manual")
    color: RGB = (255, 80, 0)
    # Slow wave so the climb up the verticals reads as motion. We previously
    # sped this up trying to "fix" the verticals not lighting; the real bug
    # was that new triggers killed in-flight waves. Now that overlapping waves
    # are supported, the wave can take its time travelling outward.
    decay_ms: float = 800.0
    wave_speed_m_per_s: float = 2.0
    state: dict[str, Any] = field(default_factory=dict)
    _effect: Effect = field(init=False)

    def __post_init__(self) -> None:
        self._effect = RadialPulse(
            color=self.color,
            decay_ms=self.decay_ms,
            wave_speed_m_per_s=self.wave_speed_m_per_s,
        )

    def on_event(self, event: Event) -> None:
        is_beat = event.kind == "beat"
        is_manual_trigger = (
            event.kind == "manual" and event.payload.get("action") == "trigger"
        )
        if is_beat or is_manual_trigger:
            self.state["pulse_pending"] = True

    def render(self, layout: StageLayout, t_ms: float) -> LedFrame:
        if self.state.pop("pulse_pending", False):
            starts = list(self.state.get("wave_starts", []))
            starts.append(t_ms)
            self.state["wave_starts"] = starts
        return self._effect.render(layout, t_ms, self.state)


@dataclass
class HandFollow:
    """Spotlight that follows the most-recent ``hand_position`` event.

    Pad-coords convention (set in :class:`Spotlight`):

    - ``x`` ∈ [0,1]: stage-left to stage-right.
    - ``y`` ∈ [0,1]: stage-back (0, all-off) to audience-front (1, full).

    A ``None`` ``radius_m`` lets the spotlight pick the stage diagonal so the
    "half everywhere at pad-centre" behaviour holds for any layout.
    """

    name: str = "hand-follow"
    triggers: tuple[EventKind, ...] = ("hand_position",)
    color: RGB = (255, 255, 255)
    radius_m: float | None = None
    state: dict[str, Any] = field(default_factory=dict)
    _effect: Effect = field(init=False)

    def __post_init__(self) -> None:
        self._effect = Spotlight(color=self.color, radius_m=self.radius_m)

    def on_event(self, event: Event) -> None:
        if event.kind == "hand_position":
            self.state["spot_x"] = float(event.payload.get("x", 0.5))
            self.state["spot_y"] = float(event.payload.get("y", 0.5))

    HAND_DOMINANCE: float = 0.45

    def dominance(self, _t_ms: float) -> float:
        """Moderate constant dominance while the hand is tracking.

        Earlier we tied this to ``pad_y`` (so dimming faded with the hand
        rising), but combined with ``DOMINANCE_DIM_FACTOR=0.8`` that meant a
        full-strength hand cut the pulse to ~20% — basically invisible. A
        constant ``0.45`` keeps the pulse at ~64% under the hand: dimmer, not
        gone. Dominance only kicks in once a hand event has actually arrived.
        """

        if "spot_x" not in self.state:
            return 0.0
        return self.HAND_DOMINANCE

    def render(self, layout: StageLayout, t_ms: float) -> LedFrame:
        return self._effect.render(layout, t_ms, self.state)


@dataclass
class SpinChase:
    """Circular chase whose RPM/direction tracks the most-recent ``spin`` event.

    The chase walks a perimeter path computed from the layout (so a horseshoe
    arrangement traces top-of-right-vertical → floor → left-vertical-top for a
    clockwise spin, not bar-declaration order).

    Clock discipline: ``on_event`` must not write engine times, because event
    timestamps come from the producer's clock (e.g. a browser's
    ``performance.now()``) which is not synchronised with the engine. ``on_event``
    only records the *target* RPM/direction; ``render`` runs entirely on engine
    time.

    ``rpm_multiplier`` amplifies the input so a slow gesture on the wheel
    drives several light circuits per wheel-revolution.
    """

    name: str = "spin-chase"
    triggers: tuple[EventKind, ...] = ("spin",)
    color: RGB = (255, 64, 0)
    tail_segments: int = 18
    decay_seconds: float = 9.0
    rpm_multiplier: float = 4.0
    max_rpm: float = 300.0
    state: dict[str, Any] = field(default_factory=dict)
    _effect: Effect = field(init=False)

    def __post_init__(self) -> None:
        self._effect = Chase(color=self.color, tail_segments=self.tail_segments)

    def on_event(self, event: Event) -> None:
        if event.kind != "spin":
            return
        rpm = float(event.payload.get("rpm", 60.0)) * self.rpm_multiplier
        rpm = max(-self.max_rpm, min(self.max_rpm, rpm))
        direction = event.payload.get("direction", "cw")
        signed = rpm if direction == "cw" else -rpm
        self.state["target_rpm"] = signed
        self.state["spin_pending"] = True
        self.state["pending_direction"] = direction

    def _ensure_path(
        self,
        layout: StageLayout,
        direction: str,
    ) -> PerimeterPath:
        cached: PerimeterPath | None = self.state.get("path_obj")
        version = int(self.state.get("layout_version", 0))
        if cached is not None and cached.layout_version == version and cached.direction == direction:
            return cached
        path = compute_perimeter_path(
            layout,
            direction="cw" if direction == "cw" else "ccw",
            layout_version=version,
        )
        self.state["path_obj"] = path
        return path

    def dominance(self, _t_ms: float) -> float:
        """Reported to the engine compositor so an active spin dims other presets.

        Scales linearly with current absolute RPM (clamped at ``max_rpm``); when
        the chase decays back toward zero, the dimming on other presets fades
        out smoothly with it.
        """

        rpm = abs(float(self.state.get("rpm", 0.0)))
        if self.max_rpm <= 0:
            return 0.0
        return max(0.0, min(1.0, rpm / self.max_rpm))

    REST_RPM_THRESHOLD: float = 0.5

    def render(self, layout: StageLayout, t_ms: float) -> LedFrame:
        # Sync our internal clock to engine time the first render after each event.
        if self.state.pop("spin_pending", False):
            self.state["last_advance_engine_ms"] = t_ms
            self.state["last_spin_engine_ms"] = t_ms
            self.state["rpm"] = float(self.state.get("target_rpm", 0.0))
            self.state.setdefault("progress", 0.0)

        # Apply decay first so the rest-threshold check below sees the current
        # speed. easeInQuad: drops fast initially, then tapers — the complement
        # easeOutQuad gave a "hold then slam" feel that read as an abrupt stop.
        last_spin = float(self.state.get("last_spin_engine_ms", t_ms))
        age_s = max(0.0, (t_ms - last_spin) / 1000.0)
        if self.decay_seconds > 0 and "target_rpm" in self.state:
            target = float(self.state["target_rpm"])
            t_norm = min(1.0, age_s / self.decay_seconds)
            decay = (1.0 - t_norm) ** 2
            self.state["rpm"] = target * decay

        rpm = float(self.state.get("rpm", 0.0))
        # Idle / decayed-out: do not paint anything. Without this, an armed but
        # never-spun (or fully-decayed) chase would leave the head pixel of the
        # path glowing because Chase always lights `tail_segments` around its
        # current progress.
        if abs(rpm) < self.REST_RPM_THRESHOLD:
            return LedFrame.black(
                layout, timestamp_ms=t_ms, layout_version=int(self.state.get("layout_version", 0))
            )

        last_advance = float(self.state.get("last_advance_engine_ms", t_ms))
        dt_s = max(0.0, (t_ms - last_advance) / 1000.0)
        revolutions = (rpm / 60.0) * dt_s
        progress = (float(self.state.get("progress", 0.0)) + revolutions) % 1.0
        self.state["progress"] = progress
        self.state["last_advance_engine_ms"] = t_ms

        # Plug the right perimeter path into the Chase effect.
        direction = "cw" if rpm >= 0 else "ccw"
        path = self._ensure_path(layout, direction)
        self.state["path"] = path.steps

        return self._effect.render(layout, t_ms, self.state)


def default_preset_registry() -> dict[str, Preset]:
    """The presets shipped with the POC. Future presets register themselves here."""

    presets: list[Preset] = [BeatPulse(), BeatPulseRadial(), HandFollow(), SpinChase()]
    return {p.name: p for p in presets}


__all__ = [
    "BeatPulse",
    "BeatPulseRadial",
    "HandFollow",
    "Preset",
    "SpinChase",
    "default_preset_registry",
]
