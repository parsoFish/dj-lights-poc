from pathlib import Path

import pytest

from dj_lights.engine.frame import Bar, Pose2D, StageLayout
from dj_lights.storage.layout_store import (
    LayoutStore,
    layout_from_json,
    layout_to_dict,
    layout_to_json,
)


def _layout() -> StageLayout:
    return StageLayout(
        name="round-trip",
        width_m=3.0,
        depth_m=2.0,
        bars=(
            Bar(id="a", length_m=1.0, segments=2, pose=Pose2D(0.0, 0.0)),
            Bar(id="b", length_m=1.5, segments=4, pose=Pose2D(1.0, 1.0, 1.5708)),
        ),
    )


def test_layout_round_trip() -> None:
    layout = _layout()
    text = layout_to_json(layout)
    back = layout_from_json(text)
    assert back == layout


def test_layout_to_dict_shape() -> None:
    d = layout_to_dict(_layout())
    assert set(d.keys()) == {"name", "width_m", "depth_m", "bars"}
    assert d["bars"][0]["pose"]["rotation_rad"] == 0.0


def test_store_save_and_load(tmp_path: Path) -> None:
    store = LayoutStore(tmp_path)
    layout = _layout()
    store.save(layout)
    assert "round-trip" in store.list()
    assert store.load("round-trip") == layout


def test_store_rejects_path_traversal(tmp_path: Path) -> None:
    store = LayoutStore(tmp_path)
    with pytest.raises(ValueError):
        store.load("../etc/passwd")
