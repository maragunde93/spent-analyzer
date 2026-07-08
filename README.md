# Spent Analyzer

Spanish-first homelab app for tracking household bills, manual expenses, cash usage, and credit-card statement imports.

## What is implemented

- FastAPI backend scaffold with household, expense, dashboard, import, cash wallet, FX, and test-auth endpoints.
- SQLAlchemy data model for users, home groups, categories, merchants, expenses, imports, cash wallet entries, FX rates, and recurring rules.
- BBVA Visa-style PDF parser using `pdfplumber`, with a sanitized fixture and parser tests.
- React/Vite dark UI with dashboard, expenses, import review, cash wallet, household settings, and future-module placeholders.
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
