# DJ Lights POC — Claude Instructions

A preset-driven RGB lighting engine: a Python backend (`backend/dj_lights`: engine, FastAPI WebSocket bridge, JSON layout store) and a vanilla TypeScript + Vite canvas UI (`frontend/`). README.md has the four scenarios and the demo script; `docs/` holds the architecture, the decisions and the runbook. Read those before changing the engine or a preset.

## Run

- Backend: `cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]" && .venv/bin/dj-lights serve --reload`
- Frontend: `cd frontend && npm install && npm run dev`, then open http://localhost:5173
- Both at once: `docker compose up`
- A dev server runs in its own terminal or in the background, never in the command you wait on.

## Test

The CI workflow (`.github/workflows/ci.yml`) runs exactly this; run it before a commit.

- Backend, from `backend/`: `ruff check .`, `mypy dj_lights`, `pytest`
- Frontend, from `frontend/`: `npm run typecheck`, `npm test` (`npm run test:e2e` runs Playwright and is not in CI)
- Tests sit beside the code they test (`backend/tests`, `frontend/tests`) and assert values; a change that is not trivial gets one.

## Commits and branches

- Conventional commits: `<type>(<scope>): <description>` with feat, fix, refactor, docs, test, chore, perf or ci; the scopes in use are api, ui, engine and wled.
- Commit on a working branch and open a pull request; never commit on or push `main`. `main` moves only by a merged pull request with CI green.
- No AI attribution lines in a commit or a pull request.
- Nothing personal in a committed file: emails, addresses, home paths, account names and keys live in runtime config or the environment.

## Code

- Small, focused files organised by feature (aim under 400 lines).
- Return new objects rather than mutating an input; handle errors explicitly at every level and never swallow one; validate external input at the boundary.
- No hardcoded values: constants, config or environment.
