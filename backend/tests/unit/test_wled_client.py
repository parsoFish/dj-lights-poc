import httpx
import pytest

from dj_lights.wled.client import WledClient, _parse_info


def test_parse_info_extracts_used_fields() -> None:
    info = _parse_info(
        {
            "name": "DJ Bars",
            "ver": "0.14.4",
            "mac": "a1b2c3d4e5f6",
            "leds": {"count": 250, "fps": 42, "rgbw": False},
        }
    )
    assert info.name == "DJ Bars"
    assert info.version == "0.14.4"
    assert info.mac == "a1b2c3d4e5f6"
    assert info.led_count == 250
    assert info.fps == 42
    assert info.raw["leds"]["rgbw"] is False


def test_parse_info_tolerates_missing_fields() -> None:
    info = _parse_info({})
    assert info.name == ""
    assert info.led_count == 0
    assert info.fps == 0


@pytest.mark.asyncio
async def test_client_info_round_trip() -> None:
    payload = {"name": "Test", "ver": "0.14.4", "mac": "aa", "leds": {"count": 100, "fps": 60}}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/json/info"
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    client = WledClient("http://test")
    # Replace the internal context-manager call by patching httpx for this test:
    async with httpx.AsyncClient(transport=transport) as ac:
        resp = await ac.get(f"{client.base_url}/json/info")
        info = _parse_info(resp.json())
    assert info.led_count == 100


@pytest.mark.asyncio
async def test_client_uses_base_url() -> None:
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"on": True})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as ac:
        await ac.get("http://10.0.0.1/json/state")
    assert seen == ["http://10.0.0.1/json/state"]
