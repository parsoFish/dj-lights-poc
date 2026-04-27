from pathlib import Path

import pytest

from dj_lights.engine.frame import Bar, Pose2D, StageLayout
from dj_lights.wled.calibration import (
    CalibrationStore,
    WledBinding,
    WledCalibration,
    apply_bindings,
)


def _layout() -> StageLayout:
    return StageLayout(
        name="test",
        width_m=4.0,
        depth_m=2.0,
        bars=(
            Bar(id="a", length_m=1.0, segments=4, pose=Pose2D(-1.0, 0.0)),
            Bar(id="b", length_m=1.0, segments=4, pose=Pose2D(1.0, 0.0)),
        ),
    )


def test_binding_pixel_count() -> None:
    b = WledBinding(device_id="x", pixel_start=0, pixel_end=10, bar_id="a")
    assert b.pixel_count == 10
    empty = WledBinding(device_id="x", pixel_start=5, pixel_end=5, bar_id="a")
    assert empty.pixel_count == 0


def test_binding_round_trip_dict() -> None:
    b = WledBinding(device_id="d1", pixel_start=24, pixel_end=44, bar_id="front-right", reverse=True)
    assert WledBinding.from_dict(b.to_dict()) == b


def test_calibration_round_trip_dict() -> None:
    c = WledCalibration(
        layout_name="sample-5bar",
        bindings=(
            WledBinding("d1", 0, 24, "right-vertical"),
            WledBinding("d1", 24, 44, "front-right", reverse=True),
        ),
    )
    assert WledCalibration.from_dict(c.to_dict()) == c


def test_apply_bindings_maps_pixels_onto_bars() -> None:
    bindings = (
        WledBinding("d1", 0, 4, "a"),
        WledBinding("d1", 4, 8, "b"),
    )
    pixels = {"d1": tuple([(10 + i, 20 + i, 30 + i) for i in range(8)])}
    f = apply_bindings(_layout(), pixels, bindings)
    assert f.bars[0].pixels == ((10, 20, 30), (11, 21, 31), (12, 22, 32), (13, 23, 33))
    assert f.bars[1].pixels == ((14, 24, 34), (15, 25, 35), (16, 26, 36), (17, 27, 37))


def test_apply_bindings_reverse_flips_order() -> None:
    bindings = (WledBinding("d1", 0, 4, "a", reverse=True),)
    pixels = {"d1": tuple([(i, 0, 0) for i in range(4)])}
    f = apply_bindings(_layout(), pixels, bindings)
    assert f.bars[0].pixels == ((3, 0, 0), (2, 0, 0), (1, 0, 0), (0, 0, 0))


def test_apply_bindings_stretches_shorter_source() -> None:
    """Two source pixels onto a 4-segment bar → first 2 segments take pixel 0, last 2 take pixel 1."""
    bindings = (WledBinding("d1", 0, 2, "a"),)
    pixels = {"d1": ((100, 0, 0), (0, 200, 0))}
    f = apply_bindings(_layout(), pixels, bindings)
    pix = f.bars[0].pixels
    assert pix[0] == (100, 0, 0)
    assert pix[3] == (0, 200, 0)


def test_apply_bindings_unknown_device_or_bar_is_skipped() -> None:
    bindings = (
        WledBinding("missing-device", 0, 4, "a"),
        WledBinding("d1", 0, 4, "missing-bar"),
    )
    pixels = {"d1": tuple([(255, 0, 0)] * 4)}
    f = apply_bindings(_layout(), pixels, bindings)
    # Both bars stay black.
    assert all(p == (0, 0, 0) for bf in f.bars for p in bf.pixels)


def test_calibration_store_round_trip(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    c = WledCalibration(
        layout_name="sample-5bar",
        bindings=(WledBinding("d1", 0, 24, "right-vertical"),),
    )
    store.save(c)
    loaded = store.load("sample-5bar")
    assert loaded == c


def test_calibration_store_returns_empty_when_missing(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    c = store.load("never-saved")
    assert c.bindings == ()
    assert c.layout_name == "never-saved"


def test_calibration_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = CalibrationStore(tmp_path)
    with pytest.raises(ValueError):
        store.load("../etc/passwd")
