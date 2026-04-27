import pytest

from dj_lights.engine.frame import Bar, BarFrame, LedFrame, Pose2D, StageLayout


def _bar(bid: str = "b", segments: int = 3) -> Bar:
    return Bar(id=bid, length_m=1.0, segments=segments, pose=Pose2D(0.0, 0.0))


def test_bar_validates_segments() -> None:
    with pytest.raises(ValueError):
        Bar(id="x", length_m=1.0, segments=0, pose=Pose2D(0, 0))


def test_bar_validates_length() -> None:
    with pytest.raises(ValueError):
        Bar(id="x", length_m=0.0, segments=1, pose=Pose2D(0, 0))


def test_layout_total_segments() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1, bars=(_bar("a", 2), _bar("b", 5)))
    assert layout.total_segments == 7


def test_layout_with_bar_returns_new() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1)
    new = layout.with_bar(_bar("a"))
    assert layout.bars == ()
    assert len(new.bars) == 1


def test_layout_with_bar_rejects_dupe() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1, bars=(_bar("a"),))
    with pytest.raises(ValueError):
        layout.with_bar(_bar("a"))


def test_layout_without_bar_rejects_missing() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1, bars=(_bar("a"),))
    with pytest.raises(ValueError):
        layout.without_bar("missing")


def test_layout_without_bar_returns_new() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1, bars=(_bar("a"), _bar("b")))
    new = layout.without_bar("a")
    assert {b.id for b in new.bars} == {"b"}
    assert {b.id for b in layout.bars} == {"a", "b"}


def test_ledframe_black_matches_layout() -> None:
    layout = StageLayout(name="t", width_m=1, depth_m=1, bars=(_bar("a", 2), _bar("b", 5)))
    f = LedFrame.black(layout, timestamp_ms=12.5, layout_version=3)
    assert f.layout_version == 3
    assert f.timestamp_ms == 12.5
    assert {bf.bar_id: len(bf.pixels) for bf in f.bars} == {"a": 2, "b": 5}
    assert all(px == (0, 0, 0) for bf in f.bars for px in bf.pixels)
    assert f.total_pixels() == 7


def test_barframe_is_frozen() -> None:
    bf = BarFrame(bar_id="a", pixels=((0, 0, 0),))
    with pytest.raises(AttributeError):
        bf.bar_id = "x"  # type: ignore[misc]
