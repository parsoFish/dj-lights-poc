#!/usr/bin/env bash
# End-to-end smoke: builds nothing, just exercises a running stack.
# Usage: dev-testing/test.sh [BACKEND_URL]
set -euo pipefail

BACKEND="${1:-http://127.0.0.1:8000}"

bash "$(dirname "$0")/test_health.sh" "$BACKEND"

echo "All smoke tests passed."
