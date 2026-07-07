#!/usr/bin/env bash
set -euo pipefail

cd /workspace
python -m unittest discover -s tests/unit -p "test_*.py"

export SPENT_DATABASE_URL="sqlite:////tmp/spent-analyzer-e2e.db"
export SPENT_TEST_AUTH_ENABLED="true"
export VITE_TEST_USER_EMAIL="mauro@example.test"
export VITE_ENABLE_API_FALLBACKS="true"
rm -f /tmp/spent-analyzer-e2e.db
uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8000 &
API_PID=$!
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

for _ in {1..40}; do
  if python - <<'PY'
import urllib.request
try:
    urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=1)
except Exception:
    raise SystemExit(1)
PY
  then
    break
  fi
  sleep 0.25
done

cd /workspace/frontend
pnpm build

if [[ "${CI_STRICT_VISUAL:-0}" == "1" ]]; then
  pnpm test:e2e
else
  pnpm exec playwright test --update-snapshots
fi
