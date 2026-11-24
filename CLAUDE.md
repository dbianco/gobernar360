# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

gobernar360 is a multi-tenant workspace of management dashboards for Argentine local governments. A FastAPI + SQLAlchemy + PostgreSQL backend (`backend/`, managed with uv, Python 3.12) and a React 19 + Mantine + TanStack Query web app (`frontend/`, Vite, npm). Each dashboard (projects, environment, economic, social, procedures) is an independent module, enabled per municipality by the platform operator and granted per user.

`README.md` documents demo accounts, roles, and per-dashboard domain rules. Each feature has a design and a plan under `docs/superpowers/specs/` and `docs/superpowers/plans/`; `tableros-de-gestion-portal-ril.md` is the functional reference (Spanish).

## Commands

Everything needs the database container: `docker compose up -d db` (PostgreSQL/PostGIS on `localhost:5434`; `db/init/01-roles.sql` creates the `gobernar360_app` role and the `gobernar360_test` and `gobernar360_e2e` databases on first start).

Backend, from `backend/`:

```bash
uv run alembic upgrade head                      # migrate the dev database
uv run gobernar360 seed-demo                     # demo data; --reset deletes ALL data first
uv run gobernar360 snapshot-indicators           # this month's indicators; --from 2026-01 rebuilds
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000
uv run pytest                                    # runs against gobernar360_test, migrates it itself
uv run pytest tests/procedures/test_summary.py::test_name
uv run pytest --cov                              # with coverage; fails below 95 % ([tool.coverage])
uv run mutmut run --max-children 1               # mutation pilot ([tool.mutmut]); one at a time: shared DB
uv run ruff check .
uv run ruff format .
uv run lint-imports                              # module-boundary contracts (.importlinter)
uv run alembic revision --autogenerate -m "..."  # then hand-edit, see Migrations
```

Frontend, from `frontend/`:

```bash
npm run dev                                      # http://localhost:5173, proxies /api to :8000
npm test -- --run                                # vitest component tests (jsdom + msw)
npm test -- --run src/dashboards/procedures/SummaryPage.test.tsx
npm test -- --run -t "test name"
npm run coverage                                 # fails below the thresholds in vite.config.ts
npm run mutation                                 # Stryker mutation pilot (stryker.config.mjs)
npm run lint                                     # oxlint
npm run build                                    # tsc -b && vite build (the type check)
npm run e2e                                      # Playwright
npx playwright test e2e/procedures.spec.ts
```

`npm run e2e` starts its own API (port 8001) and web server (5174), and wipes and re-seeds the `gobernar360_e2e` database on every run. It runs with one worker because specs share and mutate that seeded data.

## Architecture

### Layers and module boundaries

- `backend/src/gobernar360/core`: settings, engines and sessions, security, the error type.
- `backend/src/gobernar360/platform`: municipalities, users, sessions, access levels, audit log, people registry, status lights, overview, and helpers shared by dashboards (`tenant_crud`, `listing`, `api_types`, `csv_export`, `clock`).
- `backend/src/gobernar360/dashboards/<key>`: one package per dashboard.
- `frontend/src/platform` and `frontend/src/dashboards/<key>` mirror the split.

Dashboards may import `core`, `platform` and `dashboards/registry.py`, never each other; `core` and `platform` never import a dashboard. `backend/.importlinter` enforces both and `tests/test_architecture.py` runs it inside pytest. Code needed by two dashboards moves to `platform`.

### Dashboard module contract

Each backend dashboard package exposes `module = DashboardModule(key, router, get_summary, indicators)` (`dashboards/registry.py`). `main.py` registers the modules (`install_dashboards()`, also called by the CLI) and mounts each router at `/api/dashboards/<key>`. `platform` reaches dashboards only through the registry:

- `indicators` is the dashboard's catalogue of headline indicators (`IndicatorDefinition`: key, unit, `higher_is_better`, `reconstructible`, Spanish `name`, `aggregate`). Every key `get_summary` returns must be in it with the same unit; names must match `overview.indicators` in the web app (a test checks it). Only `aggregate=True` indicators can be published.
- `name` is the dashboard's Spanish name and `report_tables(ctx, first_day, last_day)` optionally adds tables to the monthly report (no personal data: reports are handed out and published).
- `get_summary(ctx, date)` returns the indicators **as of that date**: today for the overview and for this month's snapshot, the last day of a past month when snapshots are rebuilt. Mark an indicator `reconstructible=True` only if it is computed from records that carry their own date (e.g. deliveries of the year up to the date); anything that depends on how data stands today is not, and its past months are never filled in.
- The platform keeps the monthly history (`indicator_snapshots`, written by `gobernar360 snapshot-indicators`, `platform/snapshots.py`), the targets (`indicator_targets`) and the evolution shown on the summaries and the overview (`platform/indicators.py`, `indicators_router.py`). Indicators combining two dashboards are defined in `platform/indicators.py` (`COMBINED_INDICATORS`) from catalogue keys, and shown only to members who can see both dashboards.

Inside a dashboard package the convention is: `access.py` (the `KEY` plus `Viewer`/`Editor`/`Admin` annotated dependencies), `models.py`, `schemas.py`, one `*_router.py` per resource, `summary.py`, `export.py` (CSV).

On the frontend, `src/dashboards/registry.ts` lists each dashboard with its key, icon, base path `/d/<key>` and a lazy-loaded `routes.tsx` (default export, renders the tabs and nested routes). `App.tsx` wraps each in `RequireDashboard`.

### Monthly reports and the public page

- `platform/reports.py` closes a month into `monthly_reports` with its content frozen as JSON; reopening supersedes the version and creates the next as a draft. `report_pdf.py` renders it deterministically.
- `platform/publication.py` copies what is published into `public_sites`, `public_dashboards`, `public_indicators` and `public_reports`; `public_router.py` serves `/api/public/...` from those only, through `core.db.public_session()` (role `gobernar360_public`, read-only, no tenant). Those tables have RLS policies that let anyone read and let the API role write only its own municipality's rows (`enable_public_copy_rls`). Never give the public routes the normal `get_db`/`Context`.

### Tenant isolation (row-level security)

All municipalities share one database, separated by PostgreSQL RLS, not by query filters:

- Tenant tables use `TenantMixin` (`municipality_id`). Their policy compares it with the transaction-local setting `app.municipality_id`.
- The API connects as `gobernar360_app`, which owns no tables, so RLS applies. Migrations, seeding and test factories connect as the owner role (`admin_database_url`), which bypasses it.
- `get_db` gives one session and one transaction per request. `platform.access.get_context` checks the membership and calls `set_tenant`; a route receives a `RequestContext` (`ctx.db`, `ctx.municipality_id`, `ctx.user`, `ctx.membership`).
- **Flush, never commit**, inside request code: the setting is transaction-local, so after a commit the session sees no tenant rows.
- **Foreign keys are not subject to RLS.** Every id received in a request body must be loaded with `tenant_crud.resolve()` before being stored, or a row could point at another municipality's data.
- Writes go through `tenant_crud.create_entity` / `update_entity` / `delete_entity`, which set `municipality_id`, the audit columns, and append to the audit log.

### Access

Sessions are an opaque token in the `g360_session` cookie (hashed in the `sessions` table), which also holds the active municipality. Levels are `VIEWER < EDITOR < ADMIN` per dashboard; a municipality admin is `ADMIN` on every enabled dashboard; the platform operator sees configuration only and never reaches dashboard routes. Routes declare the level by their context parameter type (`ctx: Editor`).

Unsafe methods under `/api` are rejected without the header `X-Requested-With: gobernar360` (CSRF protection). The frontend `api()` client and the pytest `client` fixture both send it.

### API conventions

- Errors always have the shape `{"error": {"code", "message", "details"?}}`. Raise the constructors in `core/errors.py` (add a new one there for a new code); the frontend maps `code` to a localized text in `platform/errorMessage.ts`.
- Lists use `platform/listing.py`: `PagingParams`, `Page[T]`, `page_of`, and `contains()` for accent- and case-insensitive search.
- Anything depending on the current date takes the `Today` dependency (`platform/clock.py`, Argentine local time) so tests can pin it with `client.app.dependency_overrides[get_today]`.

### Migrations

Alembic revisions are numbered sequentially (`0009_procedures.py`). After autogenerating: import the new models module in `migrations/env.py` if it is a new package, and call `enable_tenant_rls("<table>")` for every new tenant table (it enables and forces RLS, creates the policy and grants the API role). Platform tables without `municipality_id` need `grant_app_access()` instead. A table missing these is invisible to the API or, worse, not isolated.

### Frontend conventions

- All user-facing text lives in `src/locales/es-AR.json` (Spanish, the only locale); components use keys through `useTranslation`. Code, identifiers and comments are English.
- Server state goes through TanStack Query with the thin `api()` wrapper in `src/api/client.ts`; each dashboard has its own `api.ts` and `types.ts`. Mutations use `platform/useAction.ts`, which invalidates the given query keys and exposes a displayable error.
- The dev server proxies `/api` so the session cookie stays same-origin; do not call the API on another origin.
- Every named table column in a dashboard uses `<HelpTh help={t('<dashboard>.help...')}>`. `dashboards/tableHeaders.test.ts` fails on a plain `<Table.Th>` and `dashboards/helpKeys.test.ts` fails when a help key has no text.
- A dashboard's summary page starts with `<StatusStrip dashboardKey year />` (the monthly status light with the month's indicators under it) followed by `<HeadlineIndicators dashboardKey />` (cards with evolution and targets); its parameters page includes `<IndicatorTargets dashboardKey />`. All three live in `platform` and need only the key.
- Indicator names are `overview.indicators.<key>` in `es-AR.json`.

### Tests

- Backend tests hit the real `gobernar360_test` database: `conftest.py` sets the database env vars before importing the app, migrates once per session and truncates every table after each test. Data is built with `tests/factories.py` and `tests/<dashboard>/factories.py`, which write through the owner connection; assertions go through the HTTP `client`. New tenant resources get a cross-municipality isolation test.
- Frontend component tests render with `renderApp` (`src/test/render.tsx`) or the dashboard's `testRender.tsx`, and mock HTTP with `mockApi` / `mockApiError` (`src/test/server.ts`, msw). Unhandled requests are errors. Use the exported `t()` helper instead of hard-coding Spanish copy.
- Playwright specs sign in as the demo accounts from `seed.py` and select by the Spanish UI text.

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module` with its `indicators` catalogue, register it in `install_dashboards()` in `main.py`, import its models in `migrations/env.py`, call `enable_tenant_rls()` per table in the migration, and add the package to **both** contracts in `backend/.importlinter`. Snapshots, targets and evolution then work without platform changes.
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component, add an entry with its icon to `src/dashboards/registry.ts`, add its texts (and `overview.indicators.<key>.*`) to `es-AR.json`, and follow the `StatusStrip`, `HeadlineIndicators`, `IndicatorTargets` and `HelpTh` conventions above.
3. Add demo data to `seed.py` so the e2e suite has something to exercise.

### Domain rules worth knowing before touching the code

- **People registry**: one `people` table per municipality in `platform/people.py`, with no routes of its own. A dashboard keeps its own data in a link table (`economic_people`, `social_people`) and only lists people it incorporated; the rest of the registry is reachable only by exact document number. Removing a person from the last dashboard that uses them deletes the registry row.
- **Social reserved text**: an intervention's `description` is returned only to editors and above (`dashboards/social/access.py`, `reads_reserved_text`). Every response containing interventions must be built by `interventions_router.present`; the CSV export omits the column for viewers.
- **Procedures** is an inventory, not case tracking; only procedures marked active count in summaries and reports, and a procedure's link accepts only `http(s)` URLs because the UI renders it as a link.

## Configuration

Settings come from `GOBERNAR360_*` environment variables or `backend/.env` (`core/config.py`): `DATABASE_URL`, `ADMIN_DATABASE_URL`, `PUBLIC_DATABASE_URL` (the read-only role of the public page), `PUBLIC_RATE_LIMIT_PER_MINUTE`, `SESSION_TTL_HOURS`, `COOKIE_SECURE` (set to `true` behind HTTPS), `CORS_ORIGINS`.
