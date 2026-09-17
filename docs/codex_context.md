# Codex Context - Spent Analyzer

Last updated: 2026-09-17

Use this file as the compact handoff context for future Codex threads. Start new work by reading this file, then inspect only the files relevant to the requested task. Update this file when a feature or fix changes durable product behavior, data contracts, workflow rules, testing expectations, or operational knowledge that future Codex threads should inherit.

## Project Goal

Spent Analyzer is a Spanish-first, dark-theme homelab finance app for household spending. The first release is bills/expenses-first, with manual expenses, BBVA card PDF import, BBVA account XLS import, Mercado Pago account synchronization, receipt/ticket parsing, cash wallet tracking, dashboard analytics, recurring projections, categories/subcategories, and test auth for local use.

The app is meant to run in a mini PC homelab behind an internal reverse proxy. Production auth is local username/password over the homelab HTTPS proxy; test auth remains available only for development and Playwright.

## Architecture

- Monorepo root: `G:\projects\spent-analyzer`
- Backend: FastAPI, SQLAlchemy, Pydantic, Postgres in Docker, SQLite in tests.
- Frontend: React + TypeScript + Vite, TanStack Query, Recharts, CSS in `frontend/src/styles.css`.
- Runtime: Docker Compose services for `postgres`, `api`, `web`.
- UI language: Spanish.
- Theme: dark by default.
- Local app URL: `http://localhost:8080`
- Local API URL: `http://localhost:8000`

Important files:
- Backend models: `backend/app/models.py`
- Backend schemas: `backend/app/schemas.py`
- Backend DB compatibility/migrations-at-startup: `backend/app/database.py`
- Expenses API: `backend/app/api/expenses.py`
- Imports API: `backend/app/api/imports.py`
- Dashboard API: `backend/app/api/dashboard.py`
- Mercado Pago API: `backend/app/api/mercadopago.py`
- Mercado Pago sync/client/parser: `backend/app/services/mercadopago.py`
- Mercado Pago standalone diagnostic: `backend/app/scripts/mercadopago_poc.py`
- Receipts API: `backend/app/api/receipts.py`
- BBVA card parser: `backend/app/services/bbva_parser.py`
- BBVA account parser: `backend/app/services/bbva_account_parser.py`
- Category rules: `backend/app/services/categorizer.py`
- Merchant learning: `backend/app/services/merchant_learning.py`
- Recurring helpers: `backend/app/services/recurring.py`
- Receipt LLM/OCR parser: `backend/app/services/receipt_ai_parser.py`
- Frontend app: `frontend/src/App.tsx`
- Frontend API client: `frontend/src/api.ts`
- Frontend types: `frontend/src/types.ts`
- E2E tests: `frontend/tests/e2e/app.spec.ts`

## Functional Module Map

Use this section when future requests say "work only on X". Start with the listed files, then expand only if imports or tests show it is necessary.

### Card Statement Parser / Credit Card Import

User phrase examples:
- "trabaja solo en el parser de tarjeta"
- "arregla importacion de BBVA Visa/Master"
- "statement PDF"

Primary files:
- `backend/app/services/bbva_parser.py`
- `backend/app/services/categorizer.py`
- `backend/app/services/merchant_learning.py`
- `backend/app/api/imports.py`
- `backend/app/schemas.py`
- `backend/app/models.py`
- `frontend/src/App.tsx` only for review UI behavior
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests/fixtures:
- `tests/fixtures/bbva_visa_sanitized.txt`
- `tests/fixtures/bbva_visa_sanitized.pdf`
- parser/import unit tests under `tests/unit/`
- import E2E flows in `frontend/tests/e2e/app.spec.ts`

Avoid touching dashboard charts unless the import change affects stored expense semantics.

### Account XLS Parser / Bank Movements

User phrase examples:
- "parser de cuenta"
- "importacion XLS"
- "movimientos de caja de ahorro"

Primary files:
- `backend/app/services/bbva_account_parser.py`
- `backend/app/api/imports.py`
- `backend/app/services/categorizer.py`
- `backend/app/schemas.py`
- `backend/app/models.py`
- `frontend/src/App.tsx` for account import review UI
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests/fixtures:
- account parser/import unit tests under `tests/unit/`
- account import E2E flows in `frontend/tests/e2e/app.spec.ts`

Special rules:
- Bank inflows are income unless explicitly marked as reimbursement.
- Reimbursements reduce consumption in the chosen category/subcategory.
- Card payments are ignored; service payments are not ignored.

### Dashboard / Resumen

User phrase examples:
- "trabaja solo en resumen"
- "graficos"
- "proyeccion recurrente"
- "filtros del dashboard"

Primary files:
- `backend/app/api/dashboard.py`
- `backend/app/services/recurring.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/styles.css`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests:
- `tests/unit/test_dashboard_recurring*` or similarly named dashboard tests
- dashboard/filter/visual tests in `frontend/tests/e2e/app.spec.ts`
- frontend build

Avoid touching parsers unless the chart bug is caused by imported data shape.

### Expenses / Gastos

User phrase examples:
- "vista de gastos"
- "editar/eliminar gastos"
- "busqueda de gastos"
- "ordenar columnas"

Primary files:
- `backend/app/api/expenses.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `frontend/src/styles.css`

Tests:
- expense CRUD/filter unit or integration tests under `tests/unit/`
- expenses E2E flows in `frontend/tests/e2e/app.spec.ts`

Special rule:
- Deleting a Mercado Pago expense must also remove its unreferenced `ImportLine`. The importer also detects old stale fingerprints that no longer reference an expense or earning, removes them, and recreates the movement on the next sync. Do not simplify this into unconditional duplicate rejection.

### Mercado Pago

User phrase examples:
- "Mercado Pago"
- "sincronizar movimientos"
- "settlement report"
- "token de MP"
- "duplicados de MP"

Primary files:
- `backend/app/api/mercadopago.py`
- `backend/app/services/mercadopago.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/api/expenses.py` for deletion/reimport behavior
- `backend/app/main.py` for the daily scheduler lifecycle
- `backend/app/config.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`
- `.env.example`
- `docker-compose.yml`
- `docker-compose.prod.yml`
- `docs/mercadopago_poc.md`

Tests:
- `tests/unit/test_mercadopago_sync.py`
- Mercado Pago profile flow in `frontend/tests/e2e/app.spec.ts`
- frontend build

Durable behavior:
- Integrations belong to a `(home_group_id, user_id)` pair; each user manages only their own token from Perfil, not Casa.
- Integration listings expose only the current user's metadata. Connect, replace, sync, and disconnect operations enforce ownership in the backend.
- Validate a token through Mercado Libre identity before saving it. Never return or log the raw token; HTTP debug logs must redact `Authorization`.
- The settlement report configuration must exist and include all required columns before requesting a report. Mercado Pago may return `404` when this prerequisite is missing.
- Manual sync atomically claims the integration, returns `202 Accepted`, and runs report creation/polling/download/import in an in-process background task with independent short-lived DB sessions. The UI polls persisted lifecycle fields and keeps a global indicator visible across navigation.
- A running sync blocks overlapping manual/scheduled sync, token replacement, and disconnect. Startup converts abandoned `running` states into an interrupted error. Do not solve proxy timeouts by making nginx wait for the 180-second Mercado Pago polling window.
- Correlate polling by the report ID returned from creation. Only when no ID exists may exact begin/end timestamps be used; never choose an older report because it covers the requested range.
- Manual incremental sync advances `last_sync_at`; explicit historical range sync does not advance that cursor.
- Range sync requires both dates; the UI defaults both to the user's local current date.
- Daily auto sync runs in the API process at the configured Argentina hour and overlaps prior days to catch delayed movements. Idempotent fingerprints make overlap safe.
- Linked-card payments are ignored to avoid duplicating credit-card statement expenses. Supported account-money purchases/transfers/refunds become expenses or earnings according to movement semantics.
- Enrich technical CSV references through `/v1/payments/{SOURCE_ID}` where possible. `SOURCE_ID` is preferred over `ORDER_ID`; payment description, business metadata, and recognizable idempotency-key fragments provide merchant-name fallbacks.
- A repeated sync may improve a previously generic description without creating a second expense.
- Mercado Pago import lines persist stable merchant identity from `collector.id`, falling back to `store_id` only when the collector is absent. Never use payment, order, source, or external-reference IDs as merchant learning keys.
- Editing a Mercado Pago expense learns an explicitly changed description plus submitted category/subcategory/recurrent values into a household-wide merchant rule. Rules affect only future imports; duplicate sync may backfill identity but must not alter historical expenses or overwrite manually edited descriptions.
- Expense descriptions are editable for every source, trimmed, non-empty, and limited to 240 characters. Learned description replacement is Mercado Pago-only for now.
- New Mercado Pago expenses have empty notes. Existing generated notes are deliberately not migrated.
- Deleted Mercado Pago expenses must be importable again; an orphan committed import line is stale state, not a valid duplicate.
- Local HTTP debug logging may include personal response data even though credentials are redacted. It must remain disabled in production.

### Categories / Subcategories / Casa

User phrase examples:
- "categorias"
- "subcategorias"
- "Casa"
- "colores"
- "configuracion por defecto"

Primary files:
- `backend/app/api/categories.py` if present
- `backend/app/services/categorizer.py`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `backend/app/database.py` if defaults/compatibility are involved
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests:
- category/subcategory CRUD tests under `tests/unit/`
- Casa/settings E2E flows in `frontend/tests/e2e/app.spec.ts`

Special rule:
- Historical expenses should reflect category name/color edits because expenses store category IDs.

### Tickets / Receipt OCR

User phrase examples:
- "tickets"
- "OCR"
- "Gemini"
- "asociar ticket a gasto"
- "Jumbo"

Primary files:
- `backend/app/api/receipts.py`
- `backend/app/services/receipt_ai_parser.py`
- receipt/Jumbo parser service files under `backend/app/services/`
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests/fixtures:
- receipt AI/local parser tests under `tests/unit/`
- Jumbo receipt tests under `tests/unit/`
- receipt review/association E2E flows in `frontend/tests/e2e/app.spec.ts`

Special rules:
- Prefer LLM parsing when configured; fallback to local OCR/parser.
- Ticket items annotate a related expense and must not create duplicate expenses.

### History / Audit / Import Summary

User phrase examples:
- "historial"
- "log"
- "resumen de importaciones"
- "cobertura de cargas por mes"

Primary files:
- history/audit backend API files under `backend/app/api/` if present
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests:
- audit/history unit tests under `tests/unit/`
- history E2E flows in `frontend/tests/e2e/app.spec.ts`

### Cash Wallet / Efectivo

User phrase examples:
- "efectivo"
- "billetera de efectivo"
- "cash wallet"

Primary files:
- `backend/app/api/expenses.py`
- cash wallet backend API/service files under `backend/app/api/` or `backend/app/services/` if present
- `backend/app/models.py`
- `backend/app/schemas.py`
- `frontend/src/App.tsx`
- `frontend/src/api.ts`
- `frontend/src/types.ts`

Tests:
- cash wallet unit tests under `tests/unit/`
- cash wallet E2E/visual flows in `frontend/tests/e2e/app.spec.ts`

### Deployment / Docker / Homelab

User phrase examples:
- "docker"
- "compose"
- "mini pc"
- "deploy"
- "reverse proxy"

Primary files:
- `docker-compose.yml`
- `docker-compose.test.yml`
- `backend/Dockerfile` if present
- `frontend/Dockerfile` if present
- `.env.example`
- backend startup/config files

Tests:
- `docker compose up -d --build`
- `docker compose ps`
- containerized test runner when dependency/runtime changes

### Testing / Playwright / Visual QA

User phrase examples:
- "tests"
- "Playwright"
- "visual"
- "CI"
- "E2E"

Primary files:
- `frontend/tests/e2e/app.spec.ts`
- Playwright config under `frontend/`
- `docker-compose.test.yml`
- test runner scripts under `scripts/`
- backend unit tests under `tests/unit/`

Rules:
- Add targeted tests for every bug that reached manual testing.
- CI should fail and attach artifacts; it should not auto-edit code.

## Commands

Run app locally:

```powershell
docker compose up -d --build
docker compose ps
```

Run all containerized tests:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner
```

Run all unit tests in container:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "python -m unittest discover -s tests/unit -p 'test_*.py'"
```

Run frontend build in container:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "cd frontend && npm run build"
```

Run targeted E2E for deselected import lines:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash scripts/run-targeted-e2e.sh
```

Strict visual CI mode:

```powershell
$env:CI_STRICT_VISUAL="1"
docker compose -f docker-compose.test.yml run --rm test-runner
```

## Environment

- `.env` exists locally and must not be committed.
- `.env.example` documents expected variables.
- Receipt/ticket LLM parsing uses a Gemini key if configured. If the LLM key is missing, over limit, or fails, fallback is local OCR/parser.
- Personal statements and real financial files should stay uncommitted. Use sanitized fixtures under `tests/fixtures/`.
- Mercado Pago tokens, settlement CSVs, and captured request/response bodies are personal financial data and must never be committed.

## Domain Decisions

### Expenses

Expenses preserve original currency and original amount. ARS reporting values are also stored for charts and comparison.

Important fields:
- `currency`: original currency (`ARS` or `USD`)
- `original_amount`: original signed/absolute amount depending on source semantics
- `amount_ars`: reporting amount in ARS
- `paid_by_user_id`: user who paid
- `uploaded_by_user_id`: user who uploaded/created the data
- `source`: `manual`, `import_pdf` (shown as "Credito" in UI), `bank_import`, `mercadopago`, `cash`, `transfer`, `other`
- optional `category_id`, `subcategory_id`, `notes`, `is_recurring`

No equal split logic exists. Reports can filter by payer/uploader/category/date, but paid totals remain per payer.

### Card PDF Imports

The card parser is BBVA Visa/Mastercard-style and parses:
- account/period metadata
- payment/adjustment section
- `Consumos <persona>` sections
- ARS and USD amounts
- installments like `C.06/06`
- refunds/negative amounts
- taxes/fees

It ignores:
- legal/notice pages
- fee-comparison pages
- total lines such as `TOTAL CONSUMOS ...`
- previous card payments (`SU PAGO EN PESOS`, `SU PAGO EN USD`) by default

Multi-cardholder behavior:
- Each import line may have `cardholder_name`.
- UI groups card statements by person.
- Same repeated cardholder name should be treated as the same person.
- Each person group can have its own payer selected.
- A person group can be selected or omitted.

Deselected lines:
- When processing an import, selected lines are committed.
- Pending but deselected lines are sent as `rejected_line_ids` and marked `ignored`.
- Ignored/deselected lines must not later appear as created expenses.

Use sanitized fixtures:
- `tests/fixtures/bbva_visa_sanitized.txt`
- `tests/fixtures/bbva_visa_sanitized.pdf`

The real `Statements.pdf` is local-only and must not become a permanent fixture.

### Account XLS Imports

BBVA account XLS imports may contain several months. The import review groups lines by month and shows income/expense totals per month and currency.

Rules:
- Card payments must be ignored when they represent paying the card itself.
- `PAGO DE TARJETA ...`, `CUENTA VISA ...`, and `CUENTA MASTER ...` are card payments and should not become expenses.
- `PAGO DE SERVICIOS TARJETA ...` means service payments, not card payment. These are categorized as services.
- `TITULOS ...` are financial MEP/USD buy/sell movements and should not count as consumption.
- Account income is normally an earning, not a negative expense.
- If a bank income is really a shared-expense reimbursement, it should be marked as `Reintegro/Reembolso`; then it becomes a negative consumption in the chosen category/subcategory.

Important UX decision:
- Bank outflows become positive expenses for consumption reporting.
- Bank inflows do not automatically reduce consumption unless explicitly marked as reimbursement.

### Cash Wallet

Cash withdrawals can become cash-wallet inflows. Manual cash expenses reduce wallet balance and count as categorized spend.

Open product question:
- For real-life cash, decide case-by-case whether to treat the withdrawal as uncategorized consumption or track cash expenses manually. Current app supports wallet adjustment/editing.

### Categories And Subcategories

Current default categories include:
- Auto
- Delivery
- Impuestos
- Mascotas
- Ocio / gasto personal
- Regalos
- Salud
- Servicios
- Sin categoria
- Suscripciones
- Transporte
- Vacaciones
- Vestimenta

Known defaults:
- Subcategories exist and can be CRUDed in Casa.
- Edesur should be Servicios / Electricidad.
- All Servicios should default to recurrente.
- Suscripciones should default to recurrente.
- Default categories are not re-applied to an existing configured home on startup. Casa has a manual "Cargar configuracion por defecto" action for loading missing defaults.
- `Compras del hogar` and `Herramientas` were removed from the default configuration; old system-created copies are purged while preserving associated data.

Category edits should affect historical data because expenses store category IDs, not copied labels/colors.

### Merchant Learning

When the user categorizes an imported item correctly, future similar items should learn that category/subcategory/recurrent flag. Mercado Pago additionally has stable identity rules as described above and can learn an explicitly edited description.

Two key cases:
- Installments: descriptions with `01/06`, `02/06`, etc. should normalize to the same merchant/pattern.
- Repeated merchants: e.g. `MERPAGO*TADA` should reuse prior categorization.

Learning is implemented in `backend/app/services/merchant_learning.py` and integrated in import commit.

### Recurring Projection

Recurring projection should:
- show original currency, not only ARS
- group equivalent recurring expenses under a display name
- group by subcategory when service descriptions are generic
- show category, subcategory, last month, last consumption, monthly average, accumulated, annualized projection
- expand rows to show underlying original transactions
- expire recurring card items if they do not appear in the last two loaded card statements
- avoid showing recurring items fully offset by reimbursements/reversals

The last-two-card-statements rule must be based on card statement imports, not bank XLS months. Bank XLS may include months newer than the latest card statement and should not expire card recurrences by itself.

### Receipts / Tickets

Tickets are experimental but useful.

Flow:
- Upload one or more ticket images/videos/text fixtures.
- Prefer LLM extraction/categorization if configured.
- Fall back to local OCR/parser when LLM fails.
- User reviews line items.
- User selects a main category for the ticket.
- Line item categories from the LLM become subcategories under that main category; missing subcategories may be created.
- After saving review, ticket moves to association tab.
- Association tab lets user choose/edit category, associate ticket to an existing expense, or delete it.
- Ticket item details should not create duplicate expenses; they annotate/break down a card/bank/manual expense.

## Dashboard/UI Rules

Dashboard focus is consumption over time.

Current order:
1. Filtros
2. Consumo mensual current year
3. Consumos por categoria
4. Proyeccion recurrente
5. Consumo acumulado current year
6. Promedio mensual por categoria
7. Variacion mensual por categoria

Dashboard filters:
- household/all users or individual payer
- category multi-select
- category filter should affect all charts and metrics
- filters occupy the full dashboard width; keep the height compact/adaptive to the number of categories

Charts:
- legends should use consistent category colors and order
- clicking a legend category highlights that category across charts
- `Consumo mensual` is a stacked category bar chart and shows the visible-category monthly total centered above each non-empty month bar, formatted with the app currency formatter.
- stacked monthly chart tooltips should show only the hovered category/amount
- avoid the default Recharts white translucent cursor overlay
- `Consumos por categoria` is a vertical bar chart immediately after `Consumo mensual`. It uses `amount_ars`, respects the global payer/category filters and non-consumption rules, defaults its own month selector to the latest available month in the filtered dashboard data, allows multiple selected months, sums selected months into one bar per category, orders categories by total descending, stacks each category bar by `paid_by_user_id`, shows a payer legend, always shows the formatted category total above each bar, and keeps labels legible with horizontal scroll/minimum category width on narrow or high-cardinality views.
- Card statement imports have a `statement_period` (`YYYY-MM`) that represents the statement month, separate from individual transaction dates.
- For BBVA card statements, infer `statement_period` from `VENCIMIENTO ACTUAL`: if due date is before day 25, use the previous calendar month; otherwise use the due-date month. The import review UI lets the user override it.
- Import history and dashboard statement coverage for card statements must use `statement_period`, not transaction months. This prevents a June statement with a few July-dated transactions from marking July as loaded.
- `Promedio mensual por categoria` is collapsed by default in the dashboard. It uses the latest covered card statement period for the current dashboard filter. In household view, the latest period is the latest month common to all household members with loaded card summaries; when filtering a person, use that person's latest loaded period.
- Average columns include only months whose card statement period is loaded/covered for the current dashboard filter. Within those covered months, category values of 0 are real data and must be included in the divisor. Example: latest 3 covered months May=0, April=350k, March=20k => average is 370k / 3.
- `Promedio mensual por categoria` shows only `Categoria`, `Mes en curso`, `Ultimo mes`, and `Promedio mensual (6 meses)`, in that order. `Mes en curso` is the accumulated consumption in the current calendar month and respects the dashboard global filters and existing consumption rules. `Ultimo mes` and `Promedio mensual (6 meses)` preserve their prior covered-card-period semantics.
- `Promedio mensual por categoria` has sortable columns and defaults to `Promedio mensual (6 meses)` descending. Headers for the latest month and rolling average are displayed on two lines, e.g. `Promedio mensual` / `(6 meses)` and `Ultimo mes` / `(2026-06 (Junio))`.
- `Consumo acumulado` and `Variacion mensual por categoria` are also collapsed by default in the dashboard. `Variacion mensual por categoria` compares each loaded month in the visible year against the average of up to the previous 3 loaded months in that same visible year. Zero category values in loaded months count in the average; unloaded months are excluded.

Expenses page:
- group expenses by month/year
- current month expanded by default, previous months collapsed
- sortable columns inside each month group
- search must match description, category, and `Sin categoria`
- show original currency/amount and totals in ARS and USD
- uncategorized expenses should have a warning marker
- expenses can be edited/deleted, including description/amount/category/recurrent/notes

Imports page:
- totals by currency must be prominent
- import review lines are editable before commit: category, subcategory, recurrent, notes, reimbursement when applicable
- lines needing review show warning
- processed imports should disappear from pending imports when no pending lines remain
- pending parsed imports can be deleted if they have not created protected expenses

History:
- Log tab shows audit history.
- Import summary tab shows coverage by year/month/type/uploader/payer.

## Tests To Keep Healthy

Unit tests cover:
- BBVA card parser normalization and multi-cardholder sections
- BBVA account parser classification
- import commit accounting, rejected lines, reimbursements, recurring offsets
- dashboard recurring projection behavior and category-by-payer dashboard aggregation
- merchant learning
- receipt AI/local parsing
- Jumbo receipt parser

E2E/visual tests cover:
- test-mode login/reset
- dashboard render and filters
- dashboard category consumption chart render, default latest-month selection, payer legend, visible totals, and tooltip detail
- expenses CRUD/search/sort
- card import review
- pending import deletion
- partial import deletion
- deselected import lines not becoming expenses
- account import classification
- history import summary
- subcategory CRUD
- receipt review/association
- visual snapshots
- Mercado Pago token management, range validation, sync loading state, and result handling

Mercado Pago unit tests cover report parsing, exact report correlation, report-config bootstrap, ownership, token lifecycle, asynchronous job state/results/failures, overlap rejection, interrupted-job recovery, incremental and historical ranges, idempotency, stale fingerprint recovery, deleted-expense reimport, merchant enrichment, stable merchant learning, categorization reuse, empty notes, and failed-download cursor behavior.

When changing imports, always run at least:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "python -m unittest tests.unit.test_bbva_parser tests.unit.test_import_commit_accounting"
docker compose -f docker-compose.test.yml run --rm test-runner bash scripts/run-targeted-e2e.sh
```

When changing dashboard recurring, also run:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "python -m unittest tests.unit.test_dashboard_recurring"
```

When changing dashboard chart UI, run the dashboard unit tests, a targeted Playwright dashboard test, and the frontend build. The Playwright dashboard tests require test auth in the Vite app, for example `VITE_TEST_USER_EMAIL=mauro@example.test`.

When changing Mercado Pago, run at least:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "python -m unittest tests.unit.test_mercadopago_sync"
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "cd frontend && npm run build"
```

Also run the Mercado Pago profile Playwright test when UI behavior changes. A real account has successfully completed connection, settlement-report generation, historical import, merchant enrichment, and repeated synchronization. One final real-account smoke test is planned before merging the current feature branch; do not treat that note as a product defect or replace automated coverage with live-account testing.

When changing frontend broadly, run:

```powershell
docker compose -f docker-compose.test.yml run --rm test-runner bash -lc "cd frontend && npm run build"
```

## Working Style For Future Codex Threads

To reduce token usage:
- Start a fresh thread for each focused area: imports, dashboard, tickets, expenses, deployment, auth.
- Paste or reference only this file plus the specific user request.
- Ask Codex to inspect current files before editing, because the worktree may be dirty.
- Avoid pasting long previous conversations. Put durable decisions here instead.
- Keep new decisions in this file when they affect future work, especially after adding a feature, changing product semantics, changing API response shape, or discovering a test/runtime detail that future work should not rediscover.
- Prefer targeted tests first, then full container tests when a larger workflow changed.

Important safety:
- Do not revert user data or unrelated dirty files.
- Do not commit personal statements or real bank/card documents.
- Use sanitized fixtures for permanent tests.
- Use `apply_patch` for manual edits.
