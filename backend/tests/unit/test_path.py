from dj_lights.engine.frame import Bar, Pose2D, StageLayout
from dj_lights.engine.path import compute_perimeter_path
from dj_lights.storage.layout_store import layout_from_json


def _horseshoe() -> StageLayout:
    """Same arrangement as backend/data/layouts/sample-5bar.json (downsized)."""
    return StageLayout(
        name="horseshoe",
        width_m=6.0,
        depth_m=2.5,
        bars=(
            Bar(id="left-vertical", length_m=1.8, segments=3, pose=Pose2D(-2.8, 0.4, 1.5708)),
            Bar(id="right-vertical", length_m=1.8, segments=3, pose=Pose2D(2.8, 0.4, 1.5708)),
            Bar(id="front-left", length_m=1.6, segments=3, pose=Pose2D(-1.7, -0.9, 0.0)),
            Bar(id="front-center", length_m=1.6, segments=3, pose=Pose2D(0.0, -0.9, 0.0)),
            Bar(id="front-right", length_m=1.6, segments=3, pose=Pose2D(1.7, -0.9, 0.0)),
        ),
    )


def test_perimeter_path_covers_all_segments_once() -> None:
    layout = _horseshoe()
    path = compute_perimeter_path(layout)
    assert len(path.steps) == layout.total_segments
    assert len(set(path.steps)) == layout.total_segments


def test_perimeter_path_bar_order_clockwise_for_horseshoe() -> None:
    """CW around a horseshoe: right vertical -> front bars (R->L) -> left vertical.

    The order of *bars first appearing* in the path should follow that sweep.
    """
    layout = _horseshoe()
    path = compute_perimeter_path(layout, direction="cw")
    seen: list[str] = []
    for bar_id, _ in path.steps:
        if bar_id not in seen:
            seen.append(bar_id)
    assert seen == [
        "right-vertical",
        "front-right",
        "front-center",
        "front-left",
        "left-vertical",
    ]


def test_perimeter_path_ccw_reverses_order() -> None:
    layout = _horseshoe()
    cw = compute_perimeter_path(layout, direction="cw")
    ccw = compute_perimeter_path(layout, direction="ccw")
    assert cw.steps == tuple(reversed(ccw.steps))


def test_perimeter_path_segments_walk_continuously_along_each_bar() -> None:
    """Within a bar, consecutive steps should be at adjacent segment indices."""
    layout = _horseshoe()
    path = compute_perimeter_path(layout, direction="cw")
    # Group steps by bar id contiguous run.
    runs: list[list[int]] = []
    current_bar: str | None = None
    for bar_id, idx in path.steps:
        if bar_id != current_bar:
            runs.append([idx])
            current_bar = bar_id
        else:
            runs[-1].append(idx)
    for run in runs:
        diffs = {run[i + 1] - run[i] for i in range(len(run) - 1)}
        assert diffs == {1} or diffs == {-1}, run


def test_perimeter_path_for_real_sample_layout(tmp_path) -> None:  # type: ignore[no-untyped-def]
    sample = (
        '{"name":"sample-5bar","width_m":6.0,"depth_m":2.5,"bars":['
        '{"id":"left-vertical","length_m":1.8,"segments":24,"pose":{"x_m":-2.8,"y_m":0.4,"rotation_rad":1.5708}},'
        '{"id":"right-vertical","length_m":1.8,"segments":24,"pose":{"x_m":2.8,"y_m":0.4,"rotation_rad":1.5708}},'
        '{"id":"front-left","length_m":1.6,"segments":20,"pose":{"x_m":-1.7,"y_m":-0.9,"rotation_rad":0.0}},'
        '{"id":"front-center","length_m":1.6,"segments":20,"pose":{"x_m":0.0,"y_m":-0.9,"rotation_rad":0.0}},'
        '{"id":"front-right","length_m":1.6,"segments":20,"pose":{"x_m":1.7,"y_m":-0.9,"rotation_rad":0.0}}'
        "]}"
    )
    layout = layout_from_json(sample)
    path = compute_perimeter_path(layout, direction="cw")
    assert len(path) == 24 + 24 + 20 + 20 + 20


def test_perimeter_empty_layout() -> None:
    empty = StageLayout(name="empty", width_m=1, depth_m=1)
    assert compute_perimeter_path(empty).steps == ()
