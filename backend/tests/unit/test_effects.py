from dj_lights.engine.effects import Chase, Pulse, RadialPulse, Spotlight
from dj_lights.engine.frame import Bar, Pose2D, StageLayout


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


def test_pulse_full_at_trigger() -> None:
    p = Pulse(color=(200, 0, 0), decay_ms=100)
    layout = _layout()
    state = {"last_trigger_ms": 1000.0}
    f = p.render(layout, 1000.0, state)
    assert all(px == (200, 0, 0) for bf in f.bars for px in bf.pixels)


def test_pulse_decays_over_time() -> None:
    p = Pulse(color=(200, 0, 0), decay_ms=100)
    layout = _layout()
    f1 = p.render(layout, 1100.0, {"last_trigger_ms": 1000.0})  # one half-life later
    assert f1.bars[0].pixels[0][0] == int(200 * 0.5)


def test_pulse_silent_without_trigger() -> None:
    p = Pulse(color=(255, 255, 255))
    layout = _layout()
    f = p.render(layout, 0.0, {})
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_spotlight_pad_position_drives_focus() -> None:
    """Position alone determines which bar is bright (no intensity coupling).

    Pad-bottom-right: bar 'b' (positive x) bright, bar 'a' near-dark.
    Pad-bottom-left: mirror image. Confirms position is the only knob.
    """
    s = Spotlight(color=(0, 255, 0))
    layout = _layout()
    right = s.render(layout, 0.0, {"spot_x": 1.0, "spot_y": 1.0})
    left = s.render(layout, 0.0, {"spot_x": 0.0, "spot_y": 1.0})
    r_a = max(px[1] for px in right.bars[0].pixels)
    r_b = max(px[1] for px in right.bars[1].pixels)
    l_a = max(px[1] for px in left.bars[0].pixels)
    l_b = max(px[1] for px in left.bars[1].pixels)
    assert r_b > 100 and r_a < r_b // 3
    assert l_a > 100 and l_b < l_a // 3


def test_spotlight_reaches_back_of_stage() -> None:
    """Pad-top must light up bars at the stage back (regression: top-of-vertical)."""
    s = Spotlight(color=(0, 255, 0))
    # Bar at the stage back (positive y).
    bar = Bar(id="back", length_m=1.0, segments=4, pose=Pose2D(0.0, 0.9))
    layout = StageLayout(name="t", width_m=4.0, depth_m=2.0, bars=(bar,))
    # Pad-top maps to stage-back -> spot lands ON the bar.
    f = s.render(layout, 0.0, {"spot_x": 0.5, "spot_y": 0.0})
    brightest = max(px[1] for px in f.bars[0].pixels)
    assert brightest > 200, f"top-of-stage bar should light up brightly, got {brightest}"


def test_spotlight_pad_centre_is_diffuse() -> None:
    """Pad-centre should give similar brightness to both bars (symmetric)."""
    s = Spotlight(color=(0, 255, 0))
    layout = _layout()
    f = s.render(layout, 0.0, {"spot_x": 0.5, "spot_y": 0.5})
    a_brightest = max(px[1] for px in f.bars[0].pixels)
    b_brightest = max(px[1] for px in f.bars[1].pixels)
    assert a_brightest > 30 and b_brightest > 30
    assert abs(a_brightest - b_brightest) < max(a_brightest, b_brightest)


def test_radial_pulse_wave_advances_outward() -> None:
    rp = RadialPulse(color=(200, 0, 0), decay_ms=200, wave_speed_m_per_s=6.0)
    layout = _layout()
    state: dict[str, object] = {"wave_starts": [0.0]}
    # Bar 'a' centre at (-1.5, 0): distance from origin = 1.5 m -> wave arrives at 250 ms.
    early = rp.render(layout, 50.0, state)
    later = rp.render(layout, 260.0, state)
    early_max = max(px[0] for px in early.bars[0].pixels)
    later_max = max(px[0] for px in later.bars[0].pixels)
    assert early_max == 0
    assert later_max > 0


def test_radial_pulse_no_trigger_is_dark() -> None:
    rp = RadialPulse()
    layout = _layout()
    f = rp.render(layout, 100.0, {})
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)


def test_radial_pulse_holds_old_wave_alive_during_new_pulse() -> None:
    """A second pulse fired while the first is still travelling must not
    cancel the in-flight wave (regression for the low-BPM flicker)."""
    rp = RadialPulse(color=(200, 0, 0), decay_ms=500, wave_speed_m_per_s=2.0)
    # Bar 'a' centre at (-1.5, 0): wave arrives at t = 1500 / 2 = 750 ms.
    # Bar 'b' centre at (+1.5, 0): same.
    layout = _layout()
    state: dict[str, object] = {"wave_starts": [0.0, 600.0]}
    # At t = 800 ms the first wave (age 50 ms past arrival) is bright;
    # the second wave's wavefront has only travelled 0.4 m, so it hasn't
    # reached the bars yet -- but it must not have killed the first.
    f = rp.render(layout, 800.0, state)
    a_max = max(px[0] for px in f.bars[0].pixels)
    assert a_max > 100, f"first wave killed by second pulse: a_max={a_max}"


def test_radial_pulse_culls_decayed_waves() -> None:
    rp = RadialPulse(decay_ms=100, wave_speed_m_per_s=10.0, cull_after_half_lives=4.0)
    # Stage diagonal/2 = ~1.12 m; max useful age ~ 112 + 4*100 = ~512 ms.
    # An old wave at t=0 + a recent wave at t=9_950 -> only the recent kept.
    state: dict[str, object] = {"wave_starts": [0.0, 9_950.0]}
    rp.render(_layout(), 10_000.0, state)
    remaining = state["wave_starts"]
    assert remaining == [9_950.0]


def test_chase_lights_tail() -> None:
    c = Chase(color=(255, 64, 0), tail_segments=3)
    layout = _layout()
    f = c.render(layout, 0.0, {"progress": 0.0})
    # head pixel = global index 0, in bar "a" segment 0
    assert f.bars[0].pixels[0] == (255, 64, 0)
    # global index 3 is far from head and outside the wrap-around tail -> dark
    assert f.bars[0].pixels[3] == (0, 0, 0)
    # tail wraps: global index 7 is one step behind the head, fully bright
    assert f.bars[1].pixels[3][0] > 0


def test_chase_handles_empty_layout() -> None:
    c = Chase()
    empty = StageLayout(name="empty", width_m=1, depth_m=1)
    f = c.render(empty, 0.0, {"progress": 0.0})
    assert f.total_pixels() == 0
