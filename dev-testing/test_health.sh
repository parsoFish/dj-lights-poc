#!/usr/bin/env bash
# Hits a small set of endpoints to confirm the backend is alive and serving.
set -euo pipefail
BACKEND="${1:-http://127.0.0.1:8000}"

echo "==> /health"
curl -fsS "$BACKEND/health" | grep -q '"status":"ok"'

echo "==> /api/layouts"
curl -fsS "$BACKEND/api/layouts" | grep -q "sample-5bar"

echo "==> /api/layouts/sample-5bar"
curl -fsS "$BACKEND/api/layouts/sample-5bar" | grep -q '"left-vertical"'

echo "==> /api/presets"
curl -fsS "$BACKEND/api/presets" | grep -q "beat-pulse"

echo "==> arm/disarm beat-pulse"
curl -fsS -X POST "$BACKEND/api/presets/beat-pulse/arm" >/dev/null
curl -fsS -X POST "$BACKEND/api/presets/beat-pulse/disarm" >/dev/null

echo "ok"
