# Runbook & Demo Script

## Run locally

```bash
# Backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/dj-lights serve --reload

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Or via Docker Compose from the repo root:

```bash
docker compose up
```

Open <http://localhost:5173>.

## Quality gates

```bash
# Backend
cd backend
.venv/bin/ruff check .
.venv/bin/mypy dj_lights
.venv/bin/pytest

# Frontend
cd frontend
npm run typecheck
npm test
npm run test:e2e   # Playwright (requires browsers installed)
```

## Demo script

### Stage Designer

1. Page loads with the sample 5-bar layout — two vertical bars flanking a
   wide central deck area, three horizontal bars across the front.
2. Click any bar; the right pane shows length, segments, and pose fields you
   can edit.
3. Drag a bar to move it. Hold **Shift** while dragging to rotate around its
   centre.
4. Click **+ Add bar** for a new bar at the origin; **Remove selected** to
   delete the current selection.
5. Click **Save layout** to persist via REST. Reload the page; the layout
   you saved comes back.

### Beat-reactive (Beat Pulse)

1. In the Presets panel, click **Arm** next to `beat-pulse`.
2. Click **Start mic / beat detect**, allow microphone access.
3. Play music with a clear kick (or just clap rhythmically near the mic).
   The bars pulse on each detected beat; BPM readout updates.
4. Click **Disarm** to stop visuals; click **Stop mic** to release the
   microphone.

### Hand-follow (Hand Follow)

1. Arm `hand-follow` in the Presets panel.
2. Click **Start webcam / hand follow**, allow camera access.
3. Move your hand left-to-right; a soft spotlight tracks across the bars.
4. Disarm and click **Stop webcam**.

### Spin trigger (Spin Chase)

1. Arm `spin-chase` in the Presets panel.
2. Drag clockwise or counter-clockwise on the spin wheel. A chase walks
   around the bar set in the matching direction; the chase RPM tracks the
   drag speed.
3. Stop dragging — the chase decays over a few seconds and goes dark.

## Known limitations (POC)

- No real DMX/Art-Net hardware is exercised; the `ArtNetSink` is a logging
  stub. See [decisions.md](./decisions.md#adr-002) for the upgrade path.
- Beat detection is energy-onset only. Anything below the low-pass cutoff or
  with sustained energy fools it. Replace with `aubio` / Ableton Link for a
  production setup.
- Hand tracking runs in the browser via MediaPipe WASM. For the on-Orin
  deployment, fill in `inputs/cv_orin_stub.py`.
