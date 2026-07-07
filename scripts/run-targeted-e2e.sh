#!/usr/bin/env bash
set -euo pipefail

cd /workspace
export SPENT_DATABASE_URL="sqlite:////tmp/spent-analyzer-e2e-target.db"
export SPENT_TEST_AUTH_ENABLED="true"
rm -f /tmp/spent-analyzer-e2e-target.db

uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 >/tmp/spent-api.log 2>&1 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

until python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
except Exception:
    raise SystemExit(1)
PY
do
  sleep 0.25
done

cd /workspace/frontend
npx playwright test app.spec.ts -g "deselected import lines" --project=chromium-desktop
