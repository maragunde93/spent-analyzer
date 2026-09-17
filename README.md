# Spent Analyzer

Spanish-first homelab app for tracking household bills, manual expenses, cash usage, bank and credit-card imports, and Mercado Pago account movements.

## What is implemented

- FastAPI backend with household, expense, dashboard, import, cash wallet, FX, Mercado Pago, and auth endpoints.
- SQLAlchemy data model for users, home groups, categories, merchants, expenses, imports, Mercado Pago integrations, cash wallet entries, FX rates, and recurring rules.
- BBVA Visa-style PDF parser using `pdfplumber`, with a sanitized fixture and parser tests.
- React/Vite dark UI with dashboard analytics, expenses, import review, cash wallet, household settings, and per-user Mercado Pago controls.
- Dashboard graphs for monthly consumption, category totals split by payer, recurring projections, accumulated consumption, category averages, and monthly variation.
- Mercado Pago settlement-report synchronization with background manual jobs, persisted status, manual ranges, daily automatic sync, duplicate protection, merchant-name enrichment, and stable merchant learning.
- Playwright E2E and visual snapshot tests for the main UI screens.
- Docker Compose for Postgres, API, and web services.

## Local backend tests

```powershell
& "C:\Users\marag\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" -m unittest discover -s tests/unit -p "test_*.py"
```

## Local development

Install backend dependencies in a virtual environment:

```powershell
cd backend
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Install frontend dependencies:

```powershell
cd frontend
pnpm install
pnpm dev
```

Open `http://localhost:5173`.

For the seeded Docker demo, use:

```powershell
.\scripts\start-demo-compose.ps1 -Detached
```

This exposes the demo at `http://localhost:8081/finance/`. Mercado Pago HTTP debugging is enabled by default for this local demo and can be disabled with `-NoMercadoPagoHttpDebug`.

## Docker

```powershell
docker compose up --build
```

The web UI is exposed at `http://localhost:8080/finance/` and proxies `/finance/api/` to the FastAPI service.
The local Docker stack uses the same local username/password auth flow as production:

```text
usuario: mauro
contrasena: local-password-123
```

The direct API port remains available at `http://localhost:8000` for debugging.

## Mercado Pago

Each household member manages their own Mercado Pago access token from their user profile. Tokens are validated before storage and are never returned by the API.

Synchronization supports an incremental "Sincronizar ahora" flow and an explicit historical date range. Both start and end dates default to today and are required for a range. Manual sync returns `202 Accepted` immediately and continues in an in-process background task; the UI polls the persisted integration status, so navigation and normal reverse-proxy timeouts do not interrupt report generation. A background task also synchronizes connected accounts daily; its behavior is controlled by:

```text
SPENT_MERCADOPAGO_AUTO_SYNC_ENABLED=true
SPENT_MERCADOPAGO_SYNC_HOUR_ARGENTINA=4
SPENT_MERCADOPAGO_SYNC_OVERLAP_DAYS=3
SPENT_MERCADOPAGO_DEBUG_HTTP_ENABLED=false
SPENT_MERCADOPAGO_DEBUG_HTTP_MAX_CHARS=12000
```

Local Compose enables redacted Mercado Pago request/response logging to help diagnose the settlement-report API. Production forces this logging off because response bodies may contain personal financial data. See `docs/mercadopago_poc.md` for the API flow and standalone diagnostic command.

Only the integration owner can connect, replace, synchronize, or disconnect their token. A second sync, token replacement, or disconnect request is rejected while a job is running. On startup, an abandoned `running` job is marked as interrupted. New Mercado Pago expenses have empty notes. Editing an imported expense can teach a household-wide future-import rule keyed by `collector.id`, with `store_id` as the fallback; payment/order/external-reference IDs are never learning keys.

## Containerized tests

Run backend unit tests, frontend build, and Playwright UI tests inside a container:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner
```

By default, the container updates Playwright snapshots inside the container so a fresh checkout can complete the first visual run. To enforce existing visual baselines in CI:

```powershell
$env:CI_STRICT_VISUAL="1"
docker compose -f docker-compose.test.yml run --rm test-runner
```

## Statement privacy

`Statements.pdf` is ignored by git and should stay as a local development reference only. Permanent tests use `tests/fixtures/bbva_visa_sanitized.txt`.

Mercado Pago access tokens, downloaded reports, raw API responses, and other real account data must also remain local and must not be committed as fixtures or documentation.
