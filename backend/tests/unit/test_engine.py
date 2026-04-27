import asyncio
import contextlib

import pytest

from dj_lights.engine.engine import Engine, _blend_max, _composite, _scale_frame
from dj_lights.engine.events import Event, EventBus
from dj_lights.engine.frame import Bar, BarFrame, LedFrame, Pose2D, StageLayout
from dj_lights.engine.presets import BeatPulse


def _layout() -> StageLayout:
    return StageLayout(
        name="t",
        width_m=4.0,
        depth_m=2.0,
        bars=(Bar(id="a", length_m=1.0, segments=2, pose=Pose2D(0, 0)),),
    )


def test_blend_max_takes_brightest_per_channel() -> None:
    assert _blend_max((10, 200, 5), (50, 0, 80)) == (50, 200, 80)


def test_composite_combines_frames() -> None:
    layout = _layout()
    f1 = LedFrame(layout_version=0, timestamp_ms=0.0, bars=(BarFrame("a", ((100, 0, 0), (100, 0, 0))),))
    f2 = LedFrame(layout_version=0, timestamp_ms=0.0, bars=(BarFrame("a", ((0, 50, 0), (0, 0, 0))),))
    out = _composite(layout, [f1, f2], 0.0, 0)
    assert out.bars[0].pixels == ((100, 50, 0), (100, 0, 0))


def test_composite_ignores_unknown_bars() -> None:
    layout = _layout()
    f = LedFrame(layout_version=0, timestamp_ms=0.0, bars=(BarFrame("nope", ((255, 0, 0),)),))
    out = _composite(layout, [f], 0.0, 0)
    assert out.bars[0].pixels == ((0, 0, 0), (0, 0, 0))


def test_engine_render_once_no_presets_is_black() -> None:
    eng = Engine(layout=_layout())
    f = eng.render_once(0.0)
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_engine_dispatch_routes_by_trigger_kind() -> None:
    eng = Engine(layout=_layout())
    p = BeatPulse(decay_ms=10)
    eng.arm(p)
    eng.dispatch(Event(kind="beat", timestamp_ms=10.0, payload={"bpm": 120}))
    f = eng.render_once(10.0)
    assert f.bars[0].pixels[0] != (0, 0, 0)


def test_engine_replace_layout_bumps_version() -> None:
    eng = Engine(layout=_layout())
    p = BeatPulse()
    eng.arm(p)
    assert p.state["layout_version"] == 0
    eng.replace_layout(_layout())
    assert eng.layout_version == 1
    assert p.state["layout_version"] == 1


def test_engine_disarm_removes_preset() -> None:
    eng = Engine(layout=_layout())
    p = BeatPulse()
    eng.arm(p)
    eng.disarm("beat-pulse")
    assert "beat-pulse" not in eng.active_presets


@pytest.mark.asyncio
async def test_engine_run_emits_frames_and_stops() -> None:
    eng = Engine(layout=_layout(), bus=EventBus(), fps=120)
    q = eng.subscribe_frames()
    task = asyncio.create_task(eng.run())
    try:
        f = await asyncio.wait_for(q.get(), timeout=1.0)
        assert isinstance(f, LedFrame)
    finally:
        eng.stop()
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task


def test_scale_frame_attenuates_pixels() -> None:
    f = LedFrame(layout_version=0, timestamp_ms=0.0, bars=(BarFrame("a", ((200, 100, 0),)),))
    out = _scale_frame(f, 0.5)
    assert out.bars[0].pixels[0] == (100, 50, 0)


def test_scale_frame_clamps_factor() -> None:
    f = LedFrame(layout_version=0, timestamp_ms=0.0, bars=(BarFrame("a", ((200, 100, 0),)),))
    assert _scale_frame(f, -1.0).bars[0].pixels[0] == (0, 0, 0)
    assert _scale_frame(f, 2.0).bars[0].pixels[0] == (200, 100, 0)


class _StaticPreset:
    triggers: tuple[str, ...] = ("manual",)

    def __init__(
        self, name: str, layout: StageLayout, color: tuple[int, int, int], dom: float
    ) -> None:
        self.name = name
        self.state: dict[str, object] = {}
        self._dom = dom
        self._frame = LedFrame(
            layout_version=0,
            timestamp_ms=0.0,
            bars=tuple(BarFrame(b.id, tuple(color for _ in range(b.segments))) for b in layout.bars),
        )

    def on_event(self, _ev: object) -> None:
        return

    def render(self, _layout: StageLayout, _t_ms: float) -> LedFrame:
        return self._frame

    def dominance(self, _t_ms: float) -> float:
        return self._dom


def test_dominance_dims_other_presets() -> None:
    layout = _layout()
    eng = Engine(layout=layout)
    eng.arm(_StaticPreset("red", layout, (255, 0, 0), dom=1.0))   # dominant red
    eng.arm(_StaticPreset("blue", layout, (0, 0, 255), dom=0.0))  # passive blue
    out = eng.render_once(0.0)
    pixel = out.bars[0].pixels[0]
    # Red dominant -> stays at 255 (no other preset has dominance to dim it).
    # Blue passive -> scaled by (1 - 0.8 * 1.0) = 0.2 -> 0.2 * 255 ~= 51.
    assert pixel[0] == 255
    assert 30 <= pixel[2] <= 80


def test_zero_dominance_keeps_normal_compositing() -> None:
    layout = _layout()
    eng = Engine(layout=layout)
    eng.arm(_StaticPreset("red", layout, (255, 0, 0), dom=0.0))
    eng.arm(_StaticPreset("blue", layout, (0, 0, 255), dom=0.0))
    out = eng.render_once(0.0)
    assert out.bars[0].pixels[0] == (255, 0, 255)
