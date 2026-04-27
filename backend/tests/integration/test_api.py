"""Integration: spin up the FastAPI app over the sample data dir."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from dj_lights.server.app import create_app


@pytest.fixture
def app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Copy the sample layout into an isolated data dir so tests don't mutate the repo.
    src = Path(__file__).resolve().parents[2] / "data" / "layouts"
    dst = tmp_path / "layouts"
    dst.mkdir(parents=True)
    for f in src.glob("*.json"):
        shutil.copy(f, dst / f.name)
    monkeypatch.setenv("DJ_LIGHTS_DATA_DIR", str(tmp_path))

    return TestClient(create_app())


def test_health(app: TestClient) -> None:
    with app:
        r = app.get("/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_list_layouts(app: TestClient) -> None:
    with app:
        r = app.get("/api/layouts")
    assert r.status_code == 200
    assert "sample-5bar" in r.json()["layouts"]


def test_get_layout(app: TestClient) -> None:
    with app:
        r = app.get("/api/layouts/sample-5bar")
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "sample-5bar"
    assert len(body["bars"]) == 5


def test_get_layout_404(app: TestClient) -> None:
    with app:
        r = app.get("/api/layouts/doesnotexist")
    assert r.status_code == 404


def test_put_layout_then_round_trip(app: TestClient) -> None:
    with app:
        body = {
            "width_m": 4.0,
            "depth_m": 2.0,
            "bars": [
                {
                    "id": "x",
                    "length_m": 1.0,
                    "segments": 8,
                    "pose": {"x_m": 0.0, "y_m": 0.0, "rotation_rad": 0.0},
                }
            ],
        }
        r = app.put("/api/layouts/test", json=body)
        assert r.status_code == 200
        r2 = app.get("/api/layouts/test")
    assert r2.status_code == 200
    assert r2.json()["bars"][0]["id"] == "x"


def test_put_layout_rejects_bad_body(app: TestClient) -> None:
    with app:
        r = app.put("/api/layouts/bad", json={"width_m": "no", "depth_m": 1.0, "bars": []})
    assert r.status_code == 400


def test_arm_and_disarm_preset(app: TestClient) -> None:
    with app:
        r = app.post("/api/presets/beat-pulse/arm")
        assert r.status_code == 200
        listing = app.get("/api/presets").json()
        assert any(p["name"] == "beat-pulse" and p["armed"] for p in listing["presets"])
        r = app.post("/api/presets/beat-pulse/disarm")
        assert r.status_code == 200


def test_arm_unknown_preset(app: TestClient) -> None:
    with app:
        r = app.post("/api/presets/nope/arm")
    assert r.status_code == 404


def test_wled_devices_list_starts_empty(app: TestClient) -> None:
    with app:
        r = app.get("/api/wled/devices")
    assert r.status_code == 200
    assert r.json() == {"devices": []}


def test_wled_add_manual_device(app: TestClient) -> None:
    with app:
        r = app.post("/api/wled/devices", json={"host": "10.0.0.42", "name": "Front Bars"})
    assert r.status_code == 200
    body = r.json()
    assert body["host"] == "10.0.0.42"
    assert body["name"] == "Front Bars"
    assert body["source"] == "manual"


def test_wled_add_manual_requires_host(app: TestClient) -> None:
    with app:
        r = app.post("/api/wled/devices", json={})
    assert r.status_code == 400


def test_wled_get_calibration_returns_empty_for_unknown_layout(app: TestClient) -> None:
    with app:
        r = app.get("/api/wled/calibration/sample-5bar")
    assert r.status_code == 200
    assert r.json() == {"layout_name": "sample-5bar", "bindings": []}


def test_wled_put_and_get_calibration_round_trip(app: TestClient) -> None:
    payload = {
        "bindings": [
            {"device_id": "d1", "pixel_start": 0, "pixel_end": 24, "bar_id": "right-vertical"},
            {"device_id": "d1", "pixel_start": 24, "pixel_end": 44, "bar_id": "front-right", "reverse": True},
        ]
    }
    with app:
        r = app.put("/api/wled/calibration/sample-5bar", json=payload)
        assert r.status_code == 200
        r2 = app.get("/api/wled/calibration/sample-5bar")
    body = r2.json()
    assert len(body["bindings"]) == 2
    assert body["bindings"][1]["reverse"] is True


def test_wled_put_calibration_rejects_bad_body(app: TestClient) -> None:
    with app:
        r = app.put("/api/wled/calibration/sample-5bar", json={"bindings": "no"})
    assert r.status_code == 400


def test_wled_mirror_start_unknown_device(app: TestClient) -> None:
    with app:
        r = app.post("/api/wled/mirror/start", json={"device_id": "ghost"})
    assert r.status_code == 404


def test_wled_mirror_stop_when_not_running(app: TestClient) -> None:
    with app:
        r = app.post("/api/wled/mirror/stop")
    assert r.status_code == 200
    assert r.json() == {"mirroring": False}


def test_ws_bridge_streams_frames_and_accepts_events(app: TestClient) -> None:
    with app, app.websocket_connect("/ws/bridge") as ws:
        app.post("/api/presets/beat-pulse/arm")
        ws.send_text(
            json.dumps(
                {
                    "kind": "manual",
                    "timestamp_ms": 0.0,
                    "payload": {"action": "trigger"},
                }
            )
        )
        # Receive at least one binary frame within a short window.
        data = ws.receive_bytes()
        assert isinstance(data, bytes)
        assert len(data) >= 12  # header
