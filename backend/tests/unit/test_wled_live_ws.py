import pytest

from dj_lights.wled.live_ws import LIVE_MAGIC, decode_live_frame


def _v1_frame(rgb_bytes: bytes) -> bytes:
    return bytes([LIVE_MAGIC, 1]) + rgb_bytes


def test_decode_v1_strip_basic() -> None:
    payload = _v1_frame(bytes([10, 20, 30, 40, 50, 60]))
    f = decode_live_frame(payload, device_id="wled-test", total_leds=2)
    assert f.version == 1
    assert f.width == 2
    assert f.height == 1
    assert f.pixels == ((10, 20, 30), (40, 50, 60))
    assert f.downsample_n == 1


def test_decode_v1_infers_downsample_factor() -> None:
    # WLED: total=2048 -> n=2, delivers 1024 pixels.
    pixels = bytes([0] * (1024 * 3))
    f = decode_live_frame(_v1_frame(pixels), device_id="big", total_leds=2048)
    assert f.downsample_n == 2

    # Awkward case: total=2050 -> n=3, delivers 683 pixels (last LED skipped).
    pixels = bytes([0] * (683 * 3))
    f = decode_live_frame(_v1_frame(pixels), device_id="big", total_leds=2050)
    assert f.downsample_n == 3


def test_decode_v2_matrix() -> None:
    # 2x2 matrix
    payload = bytes([LIVE_MAGIC, 2, 2, 2]) + bytes([1, 1, 1, 2, 2, 2, 3, 3, 3, 4, 4, 4])
    f = decode_live_frame(payload, device_id="matrix")
    assert f.version == 2
    assert (f.width, f.height) == (2, 2)
    assert len(f.pixels) == 4


def test_decode_rejects_missing_magic() -> None:
    with pytest.raises(ValueError, match="missing 'L' magic"):
        decode_live_frame(b"\x00\x01\x10\x20\x30", device_id="x")


def test_decode_rejects_unknown_version() -> None:
    with pytest.raises(ValueError, match="unsupported WLED live frame version"):
        decode_live_frame(bytes([LIVE_MAGIC, 9]), device_id="x")


def test_decode_rejects_truncated_2d_header() -> None:
    with pytest.raises(ValueError, match="2D live frame truncated"):
        decode_live_frame(bytes([LIVE_MAGIC, 2, 5]), device_id="x")


def test_decode_rejects_bad_body_length() -> None:
    with pytest.raises(ValueError, match="not a multiple of 3"):
        decode_live_frame(_v1_frame(b"\x10\x20"), device_id="x")


def test_decode_handles_zero_total_leds() -> None:
    f = decode_live_frame(_v1_frame(bytes([1, 2, 3])), device_id="x", total_leds=None)
    assert f.downsample_n == 1
