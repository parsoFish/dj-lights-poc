# External Tools & References

## Frontend

- **Vite** — dev server and bundler. <https://vitejs.dev/>
- **Vitest** — Jest-compatible unit tests. <https://vitest.dev/>
- **Playwright** — E2E tests. <https://playwright.dev/>
- **MediaPipe Tasks Vision** — browser hand tracking via WASM. Hand
  Landmarker model + Fileset resolver:
  <https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/web_js>

## Backend

- **FastAPI** — server framework. <https://fastapi.tiangolo.com/>
- **uvicorn** — ASGI runner. <https://www.uvicorn.org/>
- **websockets** — used by FastAPI for the WS bridge.
- **Click** — CLI. <https://click.palletsprojects.com/>
- **pytest / pytest-asyncio / pytest-cov** — tests + coverage.
- **ruff / mypy** — lint + type check.

## WLED + LedFx (Phase 6 integration target)

- **WLED firmware** — <https://kno.wled.ge/>
- **WLED JSON API** — <https://kno.wled.ge/interfaces/json-api/>
- **WLED WebSocket** — <https://kno.wled.ge/interfaces/websocket/> (Phase 6
  uses `{"lv":true}` for the live LED stream; binary frame format is `b'L' +
  version + RGB triples`, see `wled/live_ws.py`.)
- **zeroconf** — Python mDNS browser. <https://pypi.org/project/zeroconf/>
- **LedFx** — audio-reactive engine the friend already runs.
  <https://github.com/ledfx/ledfx>
- **LedFx HTTP API** — <https://docs.ledfx.app/en/stable/apis/api.html>
  (no auth on LAN; control flows through *virtuals*, not devices). Phase 7
  will hit `/api/scenes` and `/api/virtuals/*/effects`.

## Lighting protocols (Phase 7+ override path)

- **WLED realtime WS** — write side counterpart of the live read; same
  socket. Used by the Phase 7 override path.
- **sACN / E1.31** — multicast alternative to Art-Net. Library:
  <https://github.com/Hundemeier/sacn>. Out of scope for the friend's
  setup but relevant for other rigs.
- **DMX-USB-Pro / Open DMX** — for direct USB→DMX dongles via PySerial.

## Hand & gesture inference (for the future Orin Nano source)

- **MediaPipe Hands** model card — same model as the browser version.
  <https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker>
- **TensorRT** — Orin Nano's inference engine. Convert the MediaPipe model
  via ONNX → TRT.
- **Jetson MultiMedia API / GStreamer** — capture pipeline on the Orin.

## Beat detection (alternatives to the energy-onset detector)

- **aubio** — robust onset/beat detection in Python.
  <https://aubio.org/>
- **Ableton Link** — clock sync to a DJ rig, no audio analysis required.
  <https://github.com/Ableton/link>
- **Web Audio worklets** — for tighter sub-frame timing in the browser.
