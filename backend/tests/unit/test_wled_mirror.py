import pytest

from dj_lights.engine.frame import Bar, LedFrame, Pose2D, StageLayout
from dj_lights.wled.calibration import WledBinding, WledCalibration
from dj_lights.wled.live_ws import WledLiveFrame
from dj_lights.wled.mirror import WledMirror


def _layout() -> StageLayout:
    return StageLayout(
        name="t",
        width_m=4.0,
        depth_m=2.0,
        bars=(
            Bar(id="a", length_m=1.0, segments=4, pose=Pose2D(-1.0, 0.0)),
            Bar(id="b", length_m=1.0, segments=4, pose=Pose2D(1.0, 0.0)),
        ),
    )


def _calibration() -> WledCalibration:
    return WledCalibration(
        layout_name="t",
        bindings=(
            WledBinding(device_id="d1", pixel_start=0, pixel_end=4, bar_id="a"),
            WledBinding(device_id="d1", pixel_start=4, pixel_end=8, bar_id="b"),
        ),
    )


@pytest.mark.asyncio
async def test_mirror_ingests_frame_and_invokes_callback() -> None:
    captured: list[LedFrame] = []

    async def on_frame(f: LedFrame) -> None:
        captured.append(f)

    mirror = WledMirror(layout=_layout(), calibration=_calibration(), on_frame=on_frame)
    pixels = tuple([(i, i, i) for i in range(8)])
    await mirror.ingest(WledLiveFrame(device_id="d1", version=1, width=8, height=1, pixels=pixels, downsample_n=1))
    assert len(captured) == 1
    f = captured[0]
    # Bar 'a' got pixels 0..3 verbatim, bar 'b' got pixels 4..7.
    assert f.bars[0].pixels == ((0, 0, 0), (1, 1, 1), (2, 2, 2), (3, 3, 3))
    assert f.bars[1].pixels == ((4, 4, 4), (5, 5, 5), (6, 6, 6), (7, 7, 7))


@pytest.mark.asyncio
async def test_mirror_remembers_per_device_pixels() -> None:
    """A frame from device A should not zero out device B's most-recent pixels."""

    layout = StageLayout(
        name="multi",
        width_m=4.0,
        depth_m=2.0,
        bars=(
            Bar(id="a", length_m=1.0, segments=2, pose=Pose2D(-1.0, 0.0)),
            Bar(id="b", length_m=1.0, segments=2, pose=Pose2D(1.0, 0.0)),
        ),
    )
    calibration = WledCalibration(
        layout_name="multi",
        bindings=(
            WledBinding("dev-a", 0, 2, "a"),
            WledBinding("dev-b", 0, 2, "b"),
        ),
    )

    captured: list[LedFrame] = []

    async def on_frame(f: LedFrame) -> None:
        captured.append(f)

    mirror = WledMirror(layout=layout, calibration=calibration, on_frame=on_frame)
    await mirror.ingest(
        WledLiveFrame(device_id="dev-a", version=1, width=2, height=1,
                      pixels=((100, 0, 0), (100, 0, 0)), downsample_n=1)
    )
    # Now device B reports — bar 'a' should still be red because we held
    # its last frame.
    await mirror.ingest(
        WledLiveFrame(device_id="dev-b", version=1, width=2, height=1,
                      pixels=((0, 0, 200), (0, 0, 200)), downsample_n=1)
    )
    f = captured[-1]
    assert f.bars[0].pixels == ((100, 0, 0), (100, 0, 0))
    assert f.bars[1].pixels == ((0, 0, 200), (0, 0, 200))
