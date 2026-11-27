# DJ Lights POC

A modular, preset-driven RGB lighting engine that simulates a DJ's hand-built
light bar setup, plays back live preset reactions to audio / hand-tracking /
deck-spin signals, and abstracts hardware output behind a swappable interface.

The aim is to **frame the system out and demonstrate four scenarios**:

1. **Stage designer** — place, rotate, add, and remove RGB bars on a top-down
   floorplan, save and reload layouts.
2. **Beat-reactive preset** — mic in → energy-onset detector → bars pulse with
   a rolling BPM readout.
3. **Hand-follow preset** — webcam + MediaPipe Hands → spotlight follows the
   tracked hand across the bars.
4. **Spin-trigger preset** — drag the on-screen control wheel → circular
   chase synced to the spin's RPM and direction. Showcases the modular
   `trigger + effect + target group + params` recipe.

Output is rendered to a built-in **simulator** sink. Phase 6 adds a live
mirror mode that subscribes to a real WLED node's WebSocket and renders
whatever it's currently displaying — closing the gap of "no stage designer
that previews what LedFx is actually doing on the bars." See
[docs/runbook.md](./docs/runbook.md#wled-live-mirror-phase-6) for the
demo steps.

## Layout

```
backend/        Python engine, FastAPI WS bridge, JSON layout store
frontend/       Vanilla TypeScript + Vite + HTML5 Canvas UI
docs/           architecture / decisions / runbook / tools
dev-testing/    bash smoke scripts
```

## Quickstart

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

Open <http://localhost:5173>. The sample 5-bar layout matches the friend's
real setup (two vertical bars flanking the deck + three horizontal bars
across the floor).

Or run both via Docker Compose:

```bash
docker compose up
```

## Demo script

See [docs/runbook.md](./docs/runbook.md) for step-by-step demos of each
scenario. Architecture overview, ADRs, and external tools are in
[docs/](./docs/).

## CI / quality gates

- Backend: `ruff check`, `mypy dj_lights`, `pytest --cov-fail-under=80`
- Frontend: `tsc --noEmit`, `vitest run`, `playwright test`
