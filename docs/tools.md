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

## Lighting protocols (for the future Art-Net sink)

- **pyartnet** — Python Art-Net 4 client. <https://github.com/spacemanspiff2007/PyArtNet>
- **sACN / E1.31** — alternative streaming protocol. Library:
  <https://github.com/Hundemeier/sacn>
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
