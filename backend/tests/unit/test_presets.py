from dj_lights.engine.events import Event
from dj_lights.engine.frame import Bar, Pose2D, StageLayout
from dj_lights.engine.presets import (
    BeatPulse,
    BeatPulseRadial,
    HandFollow,
    SpinChase,
    default_preset_registry,
)


def _layout() -> StageLayout:
    return StageLayout(
        name="t",
        width_m=4.0,
        depth_m=2.0,
        bars=(
            Bar(id="a", length_m=1.0, segments=4, pose=Pose2D(-1.5, 0.0)),
            Bar(id="b", length_m=1.0, segments=4, pose=Pose2D(1.5, 0.0)),
        ),
    )


def test_default_registry_has_all_presets() -> None:
    reg = default_preset_registry()
    assert set(reg.keys()) == {
        "beat-pulse",
        "beat-pulse-radial",
        "hand-follow",
        "spin-chase",
    }


def test_beat_pulse_radial_fires_on_manual_trigger() -> None:
    p = BeatPulseRadial(color=(200, 0, 0), decay_ms=300, wave_speed_m_per_s=6.0)
    p.on_event(Event(kind="manual", timestamp_ms=0.0, payload={"action": "trigger"}))
    # Wave needs time to reach bars; near-trigger frame is dark.
    p.render(_layout(), 0.0)
    later = p.render(_layout(), 600.0)
    assert any(px != (0, 0, 0) for bf in later.bars for px in bf.pixels)


def test_beat_pulse_radial_queues_overlapping_waves() -> None:
    """Each beat appends a new wave; older waves should still be in flight."""
    p = BeatPulseRadial()
    p.on_event(Event(kind="beat", timestamp_ms=0.0, payload={"bpm": 30}))
    p.render(_layout(), 0.0)
    p.on_event(Event(kind="beat", timestamp_ms=2000.0, payload={"bpm": 30}))
    p.render(_layout(), 2000.0)
    starts = list(p.state.get("wave_starts", []))
    assert starts == [0.0, 2000.0]


def test_spin_chase_at_rest_is_dark() -> None:
    """Armed but never spun -> no glow at the path's start pixel."""
    p = SpinChase()
    f = p.render(_layout(), 0.0)
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_spin_chase_dark_after_full_decay() -> None:
    p = SpinChase(decay_seconds=1.0, rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    f = p.render(_layout(), 5_000.0)         # well past decay
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_spin_chase_caps_rpm_at_max() -> None:
    p = SpinChase(rpm_multiplier=4.0, max_rpm=300.0)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 1000.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    assert abs(p.state["target_rpm"]) <= 300.0


def test_spin_chase_decay_easein_quad_tail() -> None:
    """easeInQuad: speed drops fast initially then asymptotes near zero.

    At half the decay window we expect ~25% of target (curve = (1 - 0.5)^2);
    at 90% of the window we still expect a small but non-zero coast.
    """
    p = SpinChase(decay_seconds=4.0, rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    p.render(_layout(), 2_000.0)
    half = float(p.state["rpm"])
    p.render(_layout(), 3_600.0)
    near_end = float(p.state["rpm"])
    assert 14.0 <= half <= 16.0           # 60 * 0.25 = 15
    assert 0.0 < near_end < half          # still coasting before zero


def test_spin_chase_dominance_tracks_rpm() -> None:
    p = SpinChase(rpm_multiplier=1.0, max_rpm=120.0)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 120.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    assert p.dominance(0.0) == 1.0
    p.render(_layout(), 100_000.0)        # well past decay
    assert p.dominance(100_000.0) == 0.0


def test_beat_pulse_listens_to_beat_and_manual() -> None:
    p = BeatPulse(color=(100, 0, 0), decay_ms=100)
    p.on_event(Event(kind="beat", timestamp_ms=1000.0, payload={"bpm": 120}))
    f = p.render(_layout(), 1000.0)
    assert f.bars[0].pixels[0] == (100, 0, 0)


def test_beat_pulse_manual_trigger() -> None:
    p = BeatPulse(decay_ms=10)
    p.on_event(Event(kind="manual", timestamp_ms=10.0, payload={"action": "trigger"}))
    f = p.render(_layout(), 10.0)
    assert f.bars[0].pixels[0] != (0, 0, 0)


def test_beat_pulse_ignores_other_manual_actions() -> None:
    p = BeatPulse()
    p.on_event(Event(kind="manual", timestamp_ms=0.0, payload={"action": "noise"}))
    f = p.render(_layout(), 100.0)
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_hand_follow_updates_state() -> None:
    p = HandFollow(radius_m=2.0)
    p.on_event(Event(kind="hand_position", timestamp_ms=0.0, payload={"x": 0.9, "y": 0.5}))
    assert p.state["spot_x"] == 0.9
    assert p.state["spot_y"] == 0.5


def test_hand_follow_dominance_zero_until_first_event() -> None:
    p = HandFollow()
    assert p.dominance(0.0) == 0.0


def test_hand_follow_dominance_constant_when_active() -> None:
    """Constant moderate dominance keeps the pulse readable under the hand."""
    p = HandFollow()
    p.on_event(Event(kind="hand_position", timestamp_ms=0.0, payload={"x": 0.5, "y": 0.1}))
    low_y = p.dominance(0.0)
    p.on_event(Event(kind="hand_position", timestamp_ms=0.0, payload={"x": 0.5, "y": 0.9}))
    high_y = p.dominance(0.0)
    assert 0 < low_y < 1
    assert low_y == high_y           # no longer pad_y-coupled


def test_spin_chase_progress_advances_on_engine_clock() -> None:
    # 60 RPM * 4x multiplier = 4 rev/sec on the lights, lightly decayed by the
    # easeInQuad curve over the first 250 ms.
    p = SpinChase(decay_seconds=10.0, rpm_multiplier=4.0, max_rpm=10_000)
    # Event timestamp uses an unrelated browser-clock value to confirm the preset
    # ignores it for time deltas (regression test for the old drift bug).
    p.on_event(Event(kind="spin", timestamp_ms=999_999.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)              # syncs clocks
    p.render(_layout(), 250.0)            # quarter second later
    progress = p.state["progress"]
    # ~0.95 of a full revolution after 0.25 s with a touch of decay applied.
    assert 0.9 <= progress <= 1.0


def test_spin_chase_partial_progress() -> None:
    p = SpinChase(decay_seconds=10.0, rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    p.render(_layout(), 250.0)            # quarter rev
    assert 0.2 < p.state["progress"] < 0.3


def test_spin_chase_direction_negates_rpm() -> None:
    p = SpinChase(rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 30.0, "direction": "ccw"}))
    p.render(_layout(), 0.0)
    assert p.state["rpm"] == -30.0


def test_spin_chase_decays_to_zero_rpm() -> None:
    p = SpinChase(decay_seconds=1.0, rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    p.render(_layout(), 1500.0)           # past decay window
    assert p.state["rpm"] == 0.0


def test_spin_chase_uses_perimeter_path() -> None:
    p = SpinChase(rpm_multiplier=1.0, max_rpm=10_000)
    p.on_event(Event(kind="spin", timestamp_ms=0.0, payload={"rpm": 60.0, "direction": "cw"}))
    p.render(_layout(), 0.0)
    path = p.state.get("path")
    assert path is not None
    # Path should cover every segment exactly once.
    assert len(path) == _layout().total_segments
    bar_ids = {step[0] for step in path}
    assert bar_ids == {"a", "b"}
