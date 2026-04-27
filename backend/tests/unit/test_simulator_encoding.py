import struct

from dj_lights.engine.frame import BarFrame, LedFrame
from dj_lights.outputs.simulator import encode_frame


def test_encode_frame_header_and_pixels() -> None:
    frame = LedFrame(
        layout_version=2,
        timestamp_ms=42.0,
        bars=(
            BarFrame(bar_id="a", pixels=((10, 20, 30), (40, 50, 60))),
            BarFrame(bar_id="b", pixels=((1, 2, 3),)),
        ),
    )
    blob = encode_frame(frame)

    version, bar_count, ts = struct.unpack(">HHd", blob[:12])
    assert version == 2
    assert bar_count == 2
    assert ts == 42.0

    # First bar
    cursor = 12
    name_len = blob[cursor]
    cursor += 1
    assert blob[cursor : cursor + name_len].decode() == "a"
    cursor += name_len
    pixel_count = struct.unpack(">H", blob[cursor : cursor + 2])[0]
    assert pixel_count == 2
    cursor += 2
    assert blob[cursor : cursor + 6] == bytes((10, 20, 30, 40, 50, 60))
    cursor += 6

    # Second bar
    name_len = blob[cursor]
    cursor += 1
    assert blob[cursor : cursor + name_len].decode() == "b"
    cursor += name_len
    pixel_count = struct.unpack(">H", blob[cursor : cursor + 2])[0]
    assert pixel_count == 1


def test_encode_frame_long_id_rejected() -> None:
    long_id = "x" * 300
    frame = LedFrame(
        layout_version=0,
        timestamp_ms=0.0,
        bars=(BarFrame(bar_id=long_id, pixels=()),),
    )
    try:
        encode_frame(frame)
    except ValueError:
        return
    raise AssertionError("expected ValueError for over-long bar id")
