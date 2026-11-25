# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

gobernar360 is a multi-tenant workspace of management dashboards for Argentine local governments. A FastAPI + SQLAlchemy + PostgreSQL backend (`backend/`, managed with uv, Python 3.12) and a React 19 + Mantine + TanStack Query web app (`frontend/`, Vite, npm). Each dashboard (projects, environment, economic, social, procedures, cabinet) is an independent module, enabled per municipality by the platform operator and granted per user.

`README.md` documents demo accounts, roles, and per-dashboard domain rules. Each feature has a design and a plan under `docs/superpowers/specs/` and `docs/superpowers/plans/`; `tableros-de-gestion-portal-ril.md` is the functional reference (Spanish). `docs/tasks/NN-*.md` are briefs for larger pieces of work (01, email and invitations, and 04, cabinet commitments, are built; the rest are not: indicator targets, complaints, bulk import, geography, deployment...), each with a task description, how completion is judged, and notes; read the relevant one before starting such a task.

## Commands

Everything needs the database container: `docker compose up -d db` (PostgreSQL/PostGIS on `localhost:5434`; `db/init/01-roles.sql` creates the `gobernar360_app` role and the `gobernar360_test` and `gobernar360_e2e` databases on first start). `docker compose up -d` also starts Mailpit (inbox http://localhost:8025, SMTP 1025) and a dev OpenID Connect provider (`dev/oidc-provider`, http://localhost:5556); `backend/.env.example` has the settings that point the API at both.

Backend, from `backend/`:

```bash
uv run alembic upgrade head                      # migrate the dev database
uv run gobernar360 seed-demo                     # demo data; --reset deletes ALL data first
uv run gobernar360 send-email [--watch]          # deliver the email outbox over SMTP
uv run gobernar360 notify [--no-send]            # queue notification emails (run on a schedule)
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000
uv run pytest                                    # runs against gobernar360_test, migrates it itself;
                                                 # tests/test_architecture.py shells out to `uv run lint-imports`
uv run pytest tests/procedures/test_summary.py::test_name
uv run pytest --cov --cov-report=term-missing     # statement + branch coverage (pyproject [tool.coverage])
uv run python tests/make_test_databases.py 5     # once: gobernar360_test_0..4 for parallel runs
GOBERNAR360_TEST_DATABASES=5 uv run mutmut run --max-children 4   # mutation testing, hours;
uv run mutmut results; uv run mutmut show <name> # survivors and their diff ([tool.mutmut])
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
npm run test:coverage                            # v8 coverage report in coverage/ (text summary + html)
npm run test:mutation                            # Stryker (stryker.config.mjs), hours; reports/mutation/,
                                                 # incremental: later runs only retest what changed
npm run lint                                     # oxlint
npm run build                                    # tsc -b && vite build (the type check)
npm run e2e                                      # Playwright
npx playwright test e2e/procedures.spec.ts
```

`npm run e2e` starts its own API (port 8001) and web server (5174), and wipes and re-seeds the `gobernar360_e2e` database on every run. It runs with one worker because specs share and mutate that seeded data. Single sign-on is off per municipality by default, so specs that use it call `configureNoetinger(page, { sso_enabled: true })` first. It also needs Mailpit and the OIDC provider running: `e2e/helpers.ts` runs `gobernar360 send-email` and reads messages from Mailpit's API (`theEmailTo`, `passwordLink`); Mailpit keeps old messages, so filter by a start time and use unique addresses.

## Architecture

### Layers and module boundaries

- `backend/src/gobernar360/core`: settings, engines and sessions, security, the error type.
- `backend/src/gobernar360/platform`: municipalities, users, sessions, access levels, audit log, people registry, status lights, overview, and helpers shared by dashboards (`tenant_crud`, `listing`, `api_types`, `csv_export`, `clock`).
- `backend/src/gobernar360/dashboards/<key>`: one package per dashboard.
- `frontend/src/platform` and `frontend/src/dashboards/<key>` mirror the split.

Dashboards may import `core`, `platform` and `dashboards/registry.py`, never each other; `core` and `platform` never import a dashboard. `backend/.importlinter` enforces both and `tests/test_architecture.py` runs it inside pytest. Code needed by two dashboards moves to `platform`.

### Dashboard module contract

Each backend dashboard package exposes `module = DashboardModule(key, router, get_summary)` (`dashboards/registry.py`). `main.register_dashboards()` registers the modules (the CLI calls it too) and `create_app` mounts each router at `/api/dashboards/<key>`. `get_summary` feeds the general overview; optional `alert_kinds` and `get_alerts(db, today) -> list[Alert]` feed email notifications (projects raises `milestone_overdue` in `dashboards/projects/alerts.py`); optional `linkable` declares records other modules may point at, and `get_commitments` gives the open commitments a module keeps about them (see Linkable subjects). `platform` reaches dashboards only through the registry.

Inside a dashboard package the convention is: `access.py` (the `KEY` plus `Viewer`/`Editor`/`Admin` annotated dependencies), `models.py`, `schemas.py`, one `*_router.py` per resource, `summary.py`, `export.py` (CSV).

On the frontend, `src/dashboards/registry.ts` lists each dashboard with its key, icon, base path `/d/<key>` and a lazy-loaded `routes.tsx` (default export, renders the tabs and nested routes). `App.tsx` wraps each in `RequireDashboard`.

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

### Linkable subjects

One module points at another's months or records only through `platform/subjects.py`. A subject is `(dashboard_key, kind, ref)`: kind `month` exists for every dashboard (`ref` is `2026-10`); other kinds are declared in `DashboardModule.linkable` (`LinkableRecord(kind, search, describe, min_level)`; projects: `dashboards/projects/subjects.py`). A table that links uses `SubjectMixin` plus `subject_check()`.

- **On write** pass the request's `SubjectIn` through `subjects.resolve()`: there is no foreign key behind a link. Missing and not-visible get the same answer on purpose.
- **On read** use `subjects.present()`; never store or return a linked record's name by other means. `describe()` ignores who is asking and is only for copies that are `redact()`ed later (meeting minutes). Agenda items about a light store no title for the same reason.
- **Reverse view:** `/api/subjects/...` collects `get_commitments` from every module the member can open. `StatusStrip` and `<SubjectCommitments subject>` show it; a new record page only has to render the latter.
- `tests/platform/test_subjects.py` exercises the contract with a dashboard that exists only in the test.

### API conventions

- Errors always have the shape `{"error": {"code", "message", "details"?}}`. Raise the constructors in `core/errors.py` (add a new one there for a new code); the frontend maps `code` to a localized text in `platform/errorMessage.ts`.
- Lists use `platform/listing.py`: `PagingParams`, `Page[T]`, `page_of`, and `contains()` for accent- and case-insensitive search.
- Anything depending on the current date takes the `Today` dependency (`platform/clock.py`, Argentine local time) so tests can pin it with `client.app.dependency_overrides[get_today]`.

### Email, accounts and notifications

- **Never send email from request code.** Queue it in the request's transaction: `platform/email_templates.send(db, to, municipality_id, key, **params)` renders the municipality's text (or the default) to HTML plus plain text and calls `outbox.enqueue`; `send-email` delivers it (row lock with `SKIP LOCKED`, backoff, `failed` after 20 attempts).
- **Email texts** are templates: defaults under `email.templates.<key>` (subject + HTML) in the backend locale file `src/gobernar360/locales/es-AR.json`, overridable per municipality in `email_templates` (Configuración). `email_templates.Spec` lists each key's allowed and required `{{variables}}`; saves are sanitised with `nh3` and validated. Values are HTML-escaped when filled in, except `Html(...)` ones the code built. Other backend texts use `platform/texts.text()`, which raises on a missing key or placeholder.
- **Configuración** (`platform/settings_router.py`: `build_router(context)` serves `/api/admin/settings` and `/api/admin/email-templates` to municipality admins and the same routes under `/api/platform/municipalities/{id}` to the operator, as `members.build_router` does) stores `municipality_settings` and `email_templates`. Both are platform tables (no RLS) because sign-in and recovery read them before a municipality is chosen; routes filter by `ctx.municipality_id`.
- **Passwords are chosen only through links** sent to the account's own address (`platform/accounts.py`): `users.password_hash` is NULL until then. Tokens are single use (an `UPDATE ... WHERE used_at IS NULL` is the check), expire, and are stored as SHA-256. `accounts.set_password` closes sessions and revokes outstanding links; use it for every password change.
- **Adding a member must look the same whether the email had an account** (`platform/members.py`): a new or never-activated account gets an invitation, an existing one a notice, same response. Password recovery likewise answers 204 for any address and rate limits per address hash for known and unknown ones alike.
- **Members** (`platform/members.py`): `GET .../users` is paginated (`Page[MemberOut]`, `limit`/`offset`); the UI offers 10/20/50 per page through `Pager`'s `pageSizes`. Adding one person and importing a CSV (`platform/members_csv.py`, `POST .../users/import` with the decoded text, `GET .../users/import-template.csv`) share `_add_member`; an import validates every row before applying any, the last row per email wins, and it must leave at least one administrator.
- **Notifications** (`platform/notifications.py`): recipients are the municipality's `notification_emails` list, or, when empty, the members with ADMIN level on the alert's dashboard; an address whose account is in `notification_opt_outs` for the kind is skipped. `notifications_sent` (a tenant table, unique per address, kind and event key) is claimed with `INSERT ... ON CONFLICT DO NOTHING` in the same transaction as the email, which is what makes each event go out once. A new kind needs `email.templates.<kind>` and `email.items.<kind>` in the backend locale, and `account.notifications.kinds.<kind>` and `settings.templates.keys.<kind>` in the frontend one.
- **Single sign-on** (`platform/sso.py`, `sso_router.py`): the provider comes from `GOBERNAR360_OIDC_*`; a municipality allows it with `municipality_settings.sso_enabled` (off by default). Sessions record `auth_method`; an `sso` session only reaches municipalities that allow it (`access.reachable`, checked in `get_context` on every request) and never passes `require_operator`. Only existing, active accounts with a provider-verified email are signed in; nothing is created. The HTTP client is the `get_http_client` dependency so tests can put `tests/fake_oidc.py` behind it.

### Migrations

Alembic revisions are numbered sequentially (`0009_procedures.py`). After autogenerating: import the new models module in `migrations/env.py` if it is a new package, and call `enable_tenant_rls("<table>")` for every new tenant table (it enables and forces RLS, creates the policy and grants the API role). Platform tables without `municipality_id` need `grant_app_access()` instead. A table missing these is invisible to the API or, worse, not isolated.

### Frontend conventions

- All user-facing text lives in `src/locales/es-AR.json` (Spanish, the only locale); components use keys through `useTranslation`. Code, identifiers and comments are English.
- Server state goes through TanStack Query with the thin `api()` wrapper in `src/api/client.ts`; each dashboard has its own `api.ts` and `types.ts`. Mutations use `platform/useAction.ts`, which invalidates the given query keys and exposes a displayable error.
- The dev server proxies `/api` so the session cookie stays same-origin; do not call the API on another origin.
- Every named table column in a dashboard uses `<HelpTh help={t('<dashboard>.help...')}>`. `dashboards/tableHeaders.test.ts` fails on a plain `<Table.Th>` and `dashboards/helpKeys.test.ts` fails when a help key has no text.
- **Dates** are written and shown as DD/MM/YYYY: inputs use `<DateField>` (`platform/DateField.tsx`, ISO value in and out) and text `formatDate`. Never `type="date"`, which follows the browser's language; `platform/dateFields.test.ts` fails on it. Tests type dates as people do (`fill('15/01/2030')`).
- **Lists:** every table has a `SearchInput` and a `Pager` with 10/20/50 per page. Lists the API paginates use `usePaging(key)` plus `fitPage(paging, query)` and send `q`, `limit`, `offset` (backend: `PagingParams`, `SearchText`, `listing.every_word`); lists the API returns whole use `useLocalTable(key, items, text)` (`platform/paging.ts`), which searches in the browser ignoring accents. `EditableList` catalogs get both once they exceed 10 items.
- **Confirmations** use `useConfirm()` (`platform/confirmContext.ts`, modal rendered by `ConfirmProvider` in `main.tsx` and the test `renderApp`), never `window.confirm`; tests answer it with `answerConfirm(user, accept, title)` from `src/test/confirm.ts`.
- Municipality administration lives under `/admin/*` (`platform/AdminRoutes.tsx`): tabs *Usuarios* (`UsersAdminPage`) and *Configuración* (`platform/settings/`), each also a sidebar link for municipality admins. The operator reaches the same *Configuración* screen for any municipality at `/platform/municipalities/:id/settings` (`MunicipalitySettingsPage`); `settings/scope.ts` tells the screen which API base and query keys to use. Email texts are edited with `settings/RichTextEditor.tsx`, a Tiptap editor with a Mantine toolbar (links may point at placeholders such as `{{link}}`).
- A dashboard's summary page starts with `<StatusStrip dashboardKey year />` (the monthly status light, implemented entirely in `platform`).

### Tests

- Backend tests hit the real `gobernar360_test` database: `conftest.py` sets the database env vars before importing the app, migrates once per session and empties every table after each test (with `DELETE`, faster than `TRUNCATE` for a few rows). It also swaps in a cheap argon2 hasher and builds the app once per session (`app` fixture; `client` clears `dependency_overrides` after each test). With `GOBERNAR360_TEST_DATABASES=N` each test process takes its own `gobernar360_test_{k}` (advisory lock), re-chosen after a fork; mutmut needs it, ordinary runs do not. Data is built with `tests/factories.py` and `tests/<dashboard>/factories.py`, which write through the owner connection; assertions go through the HTTP `client`. New tenant resources get a cross-municipality isolation test.
- Emails are asserted from the outbox table (`emails_to`, `link_token`, `accept_invitation` in `tests/factories.py`; `body` is the plain text, `body_html` the HTML); `make_user(password=None)` is an invited account; `configure(municipality, notification_emails, sso)` sets Configuración. `tests/fake_smtp.py` is a real SMTP server for transport tests; settings are changed per test with `monkeypatch.setattr(get_settings(), ...)`.
- Frontend component tests render with `renderApp` (`src/test/render.tsx`) or the dashboard's `testRender.tsx`, and mock HTTP with `mockApi` / `mockApiError` (`src/test/server.ts`, msw). Unhandled requests are errors; default handlers answer every dashboard's `GET .../status` and `GET /subjects/.../commitments` with `[]` (so summary and record pages render their `StatusStrip` and commitments), `GET /auth/sso` and `GET /overview`. Use the `t()` helper exported by `src/test/render.tsx` instead of hard-coding Spanish copy.
- Every component test ends with a snapshot of the screen it leaves (`src/test/setup.ts`): once no request is in flight and no spinner shows, `screenText()` (`src/test/screen.ts`: the text, accessible names and placeholders, one per line; select options and the status strip left out) is compared with `__snapshots__/<file>.snap`. After an intended change of copy or layout, review the diff and run `npx vitest --run -u`. Tests run on a fixed date (2026-11-23, only `Date` is faked) so screens that show the current year do not change with the calendar; a test that needs another date sets it with `vi.useFakeTimers({ toFake: ['Date'], now })`.
- Playwright specs sign in as the demo accounts from `seed.py` and select by the Spanish UI text.
- **Coverage and mutation testing** (both held at or above their targets: 95 % coverage of statements, branches, functions and lines; 80 % of mutants killed). Assert what a caller sees, exactly: the whole error envelope (`{"code", "message"}`), the email text, the order of a list, the log message an operator would read (`caplog`; `migrations/env.py` keeps the app's loggers on). Test boundaries (the last valid year, 300 vs 301 characters) and ties in orderings. On the frontend, cover the error alert, the empty state, the Escape/cancel path and the failed save of every form and list.
- Mutation-testing exclusions are deliberate and few: `seed.py` (demo data) is not mutated; helpers that only run while modules are imported (model column helpers, `core/db.py` mixins, schema type factories, CSV aliases) or only inside migrations carry `# pragma: no mutate block` with a comment naming the test that checks them instead (`tests/test_models_match_migrations.py`, `tests/platform/test_tenant_isolation.py`). Stryker skips presentational JSX props (`stryker-ignore-styling.mjs`). Do not add pragmas to silence a mutant a test could kill; equivalent mutants (e.g. an explicit join condition SQLAlchemy would infer) are left as survivors.

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module`, register it in `main.py`, import its models in `migrations/env.py`, call `enable_tenant_rls()` per table in the migration, add the package to **both** contracts in `backend/.importlinter`, and add its name under `dashboards.<key>` in the backend locale file (status-light emails use it; `tests/platform/test_texts.py` checks it).
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component, add an entry with its icon to `src/dashboards/registry.ts`, add its texts to `es-AR.json`, and follow the `StatusStrip` and `HelpTh` conventions above.
3. Add demo data to `seed.py` so the e2e suite has something to exercise.

### Domain rules worth knowing before touching the code

- **People registry**: one `people` table per municipality in `platform/people.py`, with no routes of its own. A dashboard keeps its own data in a link table (`economic_people`, `social_people`) and only lists people it incorporated; the rest of the registry is reachable only by exact document number. Removing a person from the last dashboard that uses them deletes the registry row.
- **Social reserved text**: an intervention's `description` is returned only to editors and above (`dashboards/social/access.py`, `reads_reserved_text`). Every response containing interventions must be built by `interventions_router.present`; the CSV export omits the column for viewers.
- **Cabinet:** one open meeting per municipality (partial unique index). Every write to a meeting goes through `meetings_router._open_meeting`, which locks it and refuses closed ones; minutes are a copy made on closing (`minutes.snapshot`). The postponed count is the number of `cabinet_carryovers` rows, never a counter. `overdue` is derived (`rules.effective_state`).
- **Procedures** is an inventory, not case tracking; only procedures marked active count in summaries and reports, and a procedure's link accepts only `http(s)` URLs because the UI renders it as a link.

## Configuration

Settings come from `GOBERNAR360_*` environment variables or a `.env` in the working directory, normally `backend/.env` (`core/config.py`, example in `backend/.env.example`): `DATABASE_URL`, `ADMIN_DATABASE_URL`, `SESSION_TTL_HOURS`, `COOKIE_SECURE` (set to `true` behind HTTPS), `CORS_ORIGINS`, `APP_URL` (base of links in emails and of the SSO callback), `SMTP_HOST/PORT/USERNAME/PASSWORD/SECURITY`, `EMAIL_FROM`, token lifetimes and the recovery rate limit, and `OIDC_ISSUER/CLIENT_ID/CLIENT_SECRET/SCOPES`.
