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

### WLED live mirror (Phase 6)

1. Power on a WLED node on the same LAN as the laptop running this app.
2. After a few seconds the **WLED** panel populates the discovered devices
   list. If it doesn't, paste the device's IP into the manual-add field.
3. Click **Info** on the device to fetch its LED count.
4. In **Calibration**, click **+ Binding** for each segment of the WLED strip
   that maps to a bar in your layout. Set the pixel range and pick the bar
   from the dropdown; tick **reverse** if the strip is wired tail-first.
   Click **Save calibration**.
5. Click **Mirror** on the device. The stage designer now reflects whatever
   WLED is rendering pixel-for-pixel — drive it from WLED's phone app or
   point LedFx at it and play music; the virtual stage tracks instantly.
6. **Stop mirror** to return to the standalone simulator path; armed presets
   (BeatPulse, SpinChase, etc.) take over again.

Notes:

- WLED only supports one live subscriber at a time. If LedFx's frontend or
  another tool already had the live stream, our subscription will kick them
  off.
- Mirror mode is read-only — nothing this app does can affect WLED. If our
  app crashes mid-show, his lights keep running.

## Known limitations (POC)

- Phase 6 is **read-only**: the live mirror reflects WLED's state but
  cannot drive it. Phase 7 adds a write-side override path so our custom
  presets (spin-chase, hand-follow, beat-pulse) can briefly take over
  WLED's output via its realtime WS protocol; LedFx auto-resumes after.
- Beat detection is energy-onset only. Anything below the low-pass cutoff or
  with sustained energy fools it. Replace with `aubio` / Ableton Link for a
  production setup.
- Hand tracking runs in the browser via MediaPipe WASM. For the on-Orin
  deployment, fill in `inputs/cv_orin_stub.py`.
