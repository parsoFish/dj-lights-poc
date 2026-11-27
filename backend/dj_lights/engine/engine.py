"""Frame loop: events in, frames out.

The engine runs a fixed-rate loop (default 60 Hz). On every tick it drains
queued events, dispatches them to the active presets, then renders. Multiple
active presets are composited by layering: later presets overlay earlier ones,
with a simple ``screen``-style max blend per channel — POC-quality but lets
two presets coexist (e.g. background pulse + foreground spotlight) without
either zeroing the other out.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import Iterable
from dataclasses import dataclass, field

from .events import Event, EventBus
from .frame import RGB, BarFrame, LedFrame, StageLayout
from .presets import Preset


def _blend_max(a: RGB, b: RGB) -> RGB:
    return (max(a[0], b[0]), max(a[1], b[1]), max(a[2], b[2]))


def _scale_frame(frame: LedFrame, factor: float) -> LedFrame:
    f = max(0.0, min(1.0, factor))
    return LedFrame(
        layout_version=frame.layout_version,
        timestamp_ms=frame.timestamp_ms,
        bars=tuple(
            BarFrame(
                bar_id=bf.bar_id,
                pixels=tuple((int(r * f), int(g * f), int(b * f)) for r, g, b in bf.pixels),
            )
            for bf in frame.bars
        ),
    )


def _composite(layout: StageLayout, frames: Iterable[LedFrame], t_ms: float, version: int) -> LedFrame:
    blended: dict[str, list[RGB]] = {b.id: [(0, 0, 0)] * b.segments for b in layout.bars}
    for f in frames:
        for bf in f.bars:
            tgt = blended.get(bf.bar_id)
            if tgt is None:
                continue
            for i, px in enumerate(bf.pixels):
                if i < len(tgt):
                    tgt[i] = _blend_max(tgt[i], px)
    return LedFrame(
        layout_version=version,
        timestamp_ms=t_ms,
        bars=tuple(BarFrame(bar_id=bid, pixels=tuple(pixels)) for bid, pixels in blended.items()),
    )


@dataclass
class Engine:
    layout: StageLayout
    bus: EventBus = field(default_factory=EventBus)
    fps: int = 60
    layout_version: int = 0
    active_presets: dict[str, Preset] = field(default_factory=dict)
    _frame_listeners: list[asyncio.Queue[LedFrame]] = field(default_factory=list)
    _running: bool = False
    # When True, the run loop suppresses local preset compositing and only
    # forwards frames pushed in via `push_external_frame()` (the WLED mirror
    # path). Lets the same engine serve as standalone simulator OR as a
    # passthrough for whatever the real lights are showing.
    mirror_mode: bool = False

    @property
    def tick_seconds(self) -> float:
        return 1.0 / self.fps

    def arm(self, preset: Preset) -> None:
        self.active_presets[preset.name] = preset
        preset.state["layout_version"] = self.layout_version

    def disarm(self, preset_name: str) -> None:
        self.active_presets.pop(preset_name, None)

    def replace_layout(self, layout: StageLayout) -> None:
        self.layout = layout
        self.layout_version += 1
        for p in self.active_presets.values():
            p.state["layout_version"] = self.layout_version

    def subscribe_frames(self) -> asyncio.Queue[LedFrame]:
        q: asyncio.Queue[LedFrame] = asyncio.Queue(maxsize=4)
        self._frame_listeners.append(q)
        return q

    def unsubscribe_frames(self, q: asyncio.Queue[LedFrame]) -> None:
        with contextlib.suppress(ValueError):
            self._frame_listeners.remove(q)

    def push_external_frame(self, frame: LedFrame) -> None:
        """Inject a frame from outside the engine's preset path (e.g. WLED mirror).

        Goes straight to the broadcast queues; no compositing, no presets.
        Caller is responsible for rate-limiting if frames arrive faster than
        consumers can drain.
        """

        self._broadcast_frame(frame)

    def dispatch(self, event: Event) -> None:
        for preset in self.active_presets.values():
            if event.kind in preset.triggers:
                preset.on_event(event)

    DOMINANCE_DIM_FACTOR: float = 0.8

    def render_once(self, t_ms: float) -> LedFrame:
        if not self.active_presets:
            return LedFrame.black(self.layout, timestamp_ms=t_ms, layout_version=self.layout_version)

        rendered: list[tuple[str, LedFrame, float]] = []
        for name, p in self.active_presets.items():
            dominance_fn = getattr(p, "dominance", None)
            dominance = float(dominance_fn(t_ms)) if callable(dominance_fn) else 0.0
            dominance = max(0.0, min(1.0, dominance))
            rendered.append((name, p.render(self.layout, t_ms), dominance))

        if any(d > 0 for _, _, d in rendered):
            scaled = [
                _scale_frame(
                    frame,
                    max(
                        0.0,
                        1.0
                        - self.DOMINANCE_DIM_FACTOR
                        * max((d2 for n2, _, d2 in rendered if n2 != name), default=0.0),
                    ),
                )
                for name, frame, _ in rendered
            ]
            return _composite(self.layout, scaled, t_ms, self.layout_version)

        return _composite(self.layout, [f for _, f, _ in rendered], t_ms, self.layout_version)

    async def run(self) -> None:
        """Run the loop until cancelled. Drains the event bus + emits frames.

        In mirror mode the loop only drains events (so presets keep their
        clocks fresh for when mirroring stops) and otherwise idles — frames
        come in via :meth:`push_external_frame` from the WLED mirror.
        """

        self._running = True
        events_q = self.bus.subscribe()
        start = time.monotonic()
        try:
            while self._running:
                now = time.monotonic()
                t_ms = (now - start) * 1000.0

                while True:
                    try:
                        ev = events_q.get_nowait()
                    except asyncio.QueueEmpty:
                        break
                    self.dispatch(ev)

                if not self.mirror_mode:
                    frame = self.render_once(t_ms)
                    self._broadcast_frame(frame)

                await asyncio.sleep(self.tick_seconds)
        finally:
            self.bus.unsubscribe(events_q)

    def stop(self) -> None:
        self._running = False

    def _broadcast_frame(self, frame: LedFrame) -> None:
        for q in self._frame_listeners:
            if q.full():
                with contextlib.suppress(asyncio.QueueEmpty):
                    q.get_nowait()
            with contextlib.suppress(asyncio.QueueFull):
                q.put_nowait(frame)
