# Platform Base and Projects Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the multi-municipality gobernar360 platform base (municipalities, users, per-dashboard roles, tenant isolation), the Projects dashboard on top of it, and a first general overview dashboard.

**Architecture:** A FastAPI modular monolith over one PostgreSQL/PostGIS database, with tenant isolation enforced by row-level security. Each dashboard is a self-contained module registered through a `DashboardModule` contract; modules depend on the platform, never on each other. A separate React single-page app mirrors the same module layout and shows only the dashboards the user is granted.

**Tech Stack:** Python 3.12, uv, FastAPI, SQLAlchemy 2, Alembic, psycopg 3, Pydantic v2, pydantic-settings, argon2-cffi, Typer, pytest, ruff, import-linter. React, TypeScript, Vite, React Router, TanStack Query, Mantine, Recharts, i18next, Vitest, Testing Library, Playwright. Docker Compose with `postgis/postgis:16-3.4`.

**Spec:** `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md` (functional reference: `tableros-de-gestion-portal-ril.md`, section 4)

## Global Constraints

- All source code is in English: identifiers, comments, docstrings, log and exception messages, test names. Spanish appears only in `frontend/src/locales/es-AR.json`, in seed/fixture data, and in docs.
- No user-facing string is hard-coded in a React component; every one goes through i18next keys in `es-AR.json`.
- Python `>=3.12,<3.13`; use the latest stable release of every dependency at install time (`uv add`, `npm install`), never a hand-typed version.
- Host ports: database `5434`, API `8000`, web `5173` (5432, 5433 and 8080–8086 are taken on the dev machine).
- Environment variables use the `GOBERNAR360_` prefix.
- Every tenant data table has `municipality_id uuid NOT NULL`, the audit columns `created_at, updated_at, created_by, updated_by`, and an RLS policy `municipality_id = current_setting('app.municipality_id', true)::uuid` with `FORCE ROW LEVEL SECURITY`.
- The API connects as database role `gobernar360_app` (no table ownership, no `BYPASSRLS`); migrations run as owner role `gobernar360`.
- Dashboard tables are prefixed with the module key (`projects_*`). Dashboard modules import from `gobernar360.core` and `gobernar360.platform` only.
- Backend tests run against the real database (database `gobernar360_test` on port 5434); no mocking of the database.
- Tests are named as behaviour sentences (`test_viewer_cannot_create_project`).
- All API routes live under `/api`. Unsafe methods require the header `X-Requested-With: gobernar360`.

## Review Focus

1. **Cross-tenant foreign IDs.** Foreign keys bypass RLS, so a project created in municipality A with an `axis_id` from municipality B would be accepted by the database. Every referenced id must be resolved through the RLS-scoped session and rejected with 422 when not visible. (Test in Task 7.)
2. **Revoked access with a live session.** A user whose membership or grant is removed keeps a valid cookie; the next request must return 403 and `/auth/me` must no longer list the municipality. (Test in Task 4.)
3. **Empty and zero data in the summary.** No projects, no milestones, zero planned budget or no annual budget must yield `0` or `null` ratios, never a 500 or `NaN`. (Test in Task 8.)
4. **Deleting a parameter in use.** Deleting an axis, objective, department, program or owner that projects reference must return 409 with a readable code, not a 500 integrity error. (Test in Task 6.)
5. **Email normalisation.** `Ana@Muni.gob.ar ` and `ana@muni.gob.ar` are the same account on login and on creation; a duplicate returns 409. (Test in Task 3.)

---

## File Structure

```
docker-compose.yml
db/init/01-roles.sql                      # creates gobernar360_app role and gobernar360_test database
backend/
  pyproject.toml  alembic.ini  .importlinter
  migrations/env.py  migrations/versions/
  src/gobernar360/
    main.py                               # create_app(): routers, dashboard registration
    cli.py                                # create-operator, seed-demo
    core/config.py                        # Settings
    core/db.py                            # engine, Base, TenantMixin, AuditMixin, session helpers
    core/security.py                      # password hashing, session tokens
    core/errors.py                        # ApiError + handlers
    platform/models.py                    # Municipality, User, Session, Membership, MunicipalityDashboard, DashboardGrant, AuditLog
    platform/access.py                    # AccessLevel, RequestContext, get_context, require_dashboard, require_operator, require_municipality_admin
    platform/auth_router.py               # /api/auth/*
    platform/operator_router.py           # /api/platform/*
    platform/admin_router.py              # /api/admin/*
    platform/audit.py                     # record_change()
    platform/overview_router.py           # /api/overview
    dashboards/registry.py                # DashboardModule, SummaryIndicator, register/all
    dashboards/projects/__init__.py       # module = DashboardModule(...)
    dashboards/projects/models.py
    dashboards/projects/schemas.py
    dashboards/projects/rules.py          # pure status/progress/alert rules
    dashboards/projects/parameters_router.py
    dashboards/projects/projects_router.py
    dashboards/projects/summary.py        # compute_summary + router + get_summary
    dashboards/projects/export.py
    dashboards/projects/sdgs.py           # the 17 SDG numbers
  tests/conftest.py  tests/factories.py  tests/platform/  tests/projects/  tests/test_architecture.py
frontend/
  package.json  vite.config.ts  playwright.config.ts
  src/main.tsx  src/App.tsx
  src/api/client.ts                       # fetch wrapper, ApiError
  src/locales/es-AR.json  src/i18n.ts
  src/platform/                           # AuthProvider, LoginPage, AppShell, MunicipalitySwitcher, UsersAdminPage, OperatorPage
  src/dashboards/registry.ts
  src/dashboards/overview/OverviewPage.tsx
  src/dashboards/projects/                # routes.tsx, api.ts, SummaryPage, ProjectsPage, ProjectForm, MilestonesPanel, IndicatorsPage, ParametersPage
  e2e/platform.spec.ts  e2e/projects.spec.ts
```

---

### Task 1: Repository scaffolding and database roles

**Files:**
- Create: `.gitignore`, `docker-compose.yml`, `db/init/01-roles.sql`, `backend/pyproject.toml`, `backend/src/gobernar360/__init__.py`, `backend/src/gobernar360/main.py`, `backend/src/gobernar360/core/config.py`, `backend/tests/test_health.py`, `README.md`

**Interfaces:**
- Produces: `gobernar360.main.create_app() -> FastAPI`; `gobernar360.core.config.Settings` with fields `database_url`, `admin_database_url`, `session_ttl_hours: int = 12`, `cookie_secure: bool = False`, `cors_origins: list[str] = ["http://localhost:5173"]`, and `get_settings()` (cached).
- Default URLs: app `postgresql+psycopg://gobernar360_app:gobernar360_app@localhost:5434/gobernar360`, admin `postgresql+psycopg://gobernar360:gobernar360@localhost:5434/gobernar360`.

- [ ] **Step 1:** Write `docker-compose.yml` with service `db` (`postgis/postgis:16-3.4`, `platform: linux/amd64`, `5434:5432`, user/password/db `gobernar360`, named volume, mounts `./db/init` to `/docker-entrypoint-initdb.d`). `01-roles.sql` creates login role `gobernar360_app` (password `gobernar360_app`) and database `gobernar360_test` owned by `gobernar360`.
- [ ] **Step 2:** `cd backend && uv init --lib --name gobernar360 --python 3.12`, then `uv add fastapi "uvicorn[standard]" sqlalchemy alembic "psycopg[binary]" pydantic-settings argon2-cffi typer` and `uv add --dev pytest httpx ruff import-linter`. Configure ruff (line length 100, rules `E,F,I,UP,B`) and `[project.scripts] gobernar360 = "gobernar360.cli:app"`.
- [ ] **Step 3:** Write the failing test `test_health_endpoint_reports_ok`: `TestClient(create_app()).get("/api/health")` returns 200 and `{"status": "ok"}`.
- [ ] **Step 4:** Run `uv run pytest tests/test_health.py -v`. Expected: FAIL (no `create_app`).
- [ ] **Step 5:** Implement `Settings` and `create_app()` with the health route and CORS (credentials allowed, origins from settings).
- [ ] **Step 6:** Run `docker compose up -d db`, `uv run pytest -v`, `uv run ruff check .`. Expected: 1 passed, no lint errors.
- [ ] **Step 7:** Write `README.md` (how to start the database, run the API, run tests). Commit: `chore: scaffold backend, database and tooling`.

### Task 2: Database layer, platform models and tenant isolation

**Files:**
- Create: `backend/src/gobernar360/core/db.py`, `backend/src/gobernar360/platform/models.py`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/versions/0001_platform.py`, `backend/tests/conftest.py`, `backend/tests/factories.py`, `backend/tests/platform/test_tenant_isolation.py`

**Interfaces:**
- Produces in `core/db.py`:
  - `Base` (declarative), `TenantMixin` (`municipality_id: Mapped[uuid.UUID]`, FK to `municipalities.id`, indexed), `AuditMixin` (`created_at`, `updated_at`, `created_by`, `updated_by`, the last two nullable FKs to `users.id`).
  - `get_engine() -> Engine`, `platform_session() -> Iterator[Session]` (no tenant set), `tenant_session(municipality_id: uuid.UUID) -> Iterator[Session]` (opens a transaction and runs `SELECT set_config('app.municipality_id', :id, true)`; commits on success, rolls back on error).
  - `enable_tenant_rls(table_name: str) -> None`, a helper for migrations that issues `ENABLE` + `FORCE ROW LEVEL SECURITY`, the policy from Global Constraints (`USING` and `WITH CHECK`), and `GRANT SELECT, INSERT, UPDATE, DELETE` to `gobernar360_app`.
- Produces in `platform/models.py` (all ids `uuid` with `gen_random_uuid()` default):
  - `Municipality(id, name, slug unique, kind: 'municipality'|'commune', created_at)`
  - `User(id, email unique, full_name, password_hash, is_platform_operator=False, is_active=True, created_at)`
  - `Session(id, token_hash unique, user_id, active_municipality_id nullable, expires_at, created_at)`
  - `Membership(id, user_id, municipality_id, is_admin=False)`, unique `(user_id, municipality_id)`
  - `MunicipalityDashboard(municipality_id, dashboard_key)`, composite primary key
  - `DashboardGrant(membership_id, dashboard_key, level: 'viewer'|'editor'|'admin')`, composite primary key, cascade delete with membership
  - `AuditLog(id, municipality_id, user_id, action: 'create'|'update'|'delete', entity_type, entity_id, changes: JSONB, created_at)`, RLS-protected via `enable_tenant_rls`
- Platform tables other than `audit_log` have no RLS (login must find a user before a tenant is known); the migration grants `gobernar360_app` DML on them.
- Produces in `tests/conftest.py`: session-scoped fixture that runs `alembic upgrade head` on `gobernar360_test` (admin URL) and points settings at the test database; function-scoped autouse fixture that truncates all tables; `client` fixture (`TestClient` sending `X-Requested-With: gobernar360`). `tests/factories.py`: `make_municipality(name="Noetinger")`, `make_user(email, password="secret-pass-1", operator=False)`, `make_membership(user, municipality, admin=False, grants: dict[str, str] | None = None, enable: list[str] | None = None)`, `login(client, email, password="secret-pass-1")` (added in Task 3).

- [ ] **Step 1:** Write failing tests in `test_tenant_isolation.py`, using `AuditLog` as the tenant table:
  - `test_tenant_session_only_sees_its_own_rows`: insert one row per municipality A and B (each in its own `tenant_session`); `select(AuditLog)` with no filter inside `tenant_session(A)` returns only A's row.
  - `test_tenant_session_cannot_insert_rows_for_another_municipality`: inserting a row with `municipality_id=B` inside `tenant_session(A)` raises `sqlalchemy.exc.ProgrammingError` or `DBAPIError` (RLS check violation).
  - `test_session_without_tenant_sees_no_tenant_rows`: `platform_session()` selects zero `AuditLog` rows.
  - `test_app_role_does_not_bypass_rls`: `SELECT rolbypassrls, rolsuper FROM pg_roles WHERE rolname = current_user` on the app connection returns `(False, False)`.
- [ ] **Step 2:** Run `uv run pytest tests/platform/test_tenant_isolation.py -v`. Expected: FAIL (imports missing).
- [ ] **Step 3:** Implement `core/db.py`, `platform/models.py`, Alembic config (`env.py` uses `admin_database_url` and `Base.metadata`) and migration `0001_platform` (`CREATE EXTENSION IF NOT EXISTS pgcrypto`).
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add platform data model with row-level tenant isolation`.

### Task 3: Authentication and sessions

**Files:**
- Create: `backend/src/gobernar360/core/security.py`, `backend/src/gobernar360/core/errors.py`, `backend/src/gobernar360/platform/auth_router.py`, `backend/tests/platform/test_auth.py`
- Modify: `backend/src/gobernar360/main.py`, `backend/tests/factories.py`

**Interfaces:**
- Produces in `core/security.py`: `hash_password(plain: str) -> str`, `verify_password(plain: str, hashed: str) -> bool` (argon2id), `new_session_token() -> tuple[str, str]` returning `(token, sha256_hex)`, `normalize_email(raw: str) -> str` (strip + lowercase).
- Produces in `core/errors.py`: `ApiError(status_code: int, code: str, message: str)` and a handler returning `{"error": {"code", "message"}}`. Codes used across the plan: `invalid_credentials`, `not_authenticated`, `forbidden`, `not_found`, `conflict`, `in_use`, `invalid_reference`, `csrf_header_missing`.
- Routes: `POST /api/auth/login {email, password}` → 200 `Me` and sets cookie `g360_session` (`HttpOnly`, `SameSite=Lax`, `Secure` from settings, `Max-Age` from `session_ttl_hours`); `POST /api/auth/logout` → 204, deletes the session row; `GET /api/auth/me` → `Me`; `POST /api/auth/active-municipality {municipality_id}` → `Me`.
- `Me` schema: `{user: {id, email, full_name, is_platform_operator}, memberships: [{municipality: {id, name, slug, kind}, is_admin}], active_municipality_id: uuid | null, dashboards: [{key, level}]}`, where `dashboards` lists the effective level per enabled dashboard in the active municipality (resolved in Task 4; return `[]` here).
- On login the active municipality is set automatically when the user has exactly one membership.
- A middleware rejects `POST/PUT/PATCH/DELETE` under `/api` lacking `X-Requested-With: gobernar360` with 403 `csrf_header_missing`.

- [ ] **Step 1:** Write failing tests:
  - `test_login_with_valid_credentials_sets_session_cookie` (200, `g360_session` cookie present and `httponly`)
  - `test_login_with_wrong_password_returns_invalid_credentials` (401, same code for unknown email)
  - `test_login_ignores_email_case_and_surrounding_spaces` (user `ana@muni.gob.ar` logs in as `" Ana@Muni.gob.ar "`)
  - `test_inactive_user_cannot_log_in`
  - `test_me_without_session_returns_not_authenticated` (401)
  - `test_expired_session_is_rejected` (set `expires_at` in the past → 401)
  - `test_logout_invalidates_the_session`
  - `test_single_membership_becomes_active_municipality_on_login`
  - `test_user_cannot_activate_a_municipality_they_do_not_belong_to` (403)
  - `test_unsafe_request_without_csrf_header_is_rejected` (403 `csrf_header_missing`)
- [ ] **Step 2:** Run `uv run pytest tests/platform/test_auth.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement security helpers, error handling, the router and the middleware; add `login()` to factories.
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add email and password authentication with database sessions`.

### Task 4: Access control and dashboard registry

**Files:**
- Create: `backend/src/gobernar360/platform/access.py`, `backend/src/gobernar360/dashboards/registry.py`, `backend/tests/platform/test_access.py`
- Modify: `backend/src/gobernar360/platform/auth_router.py`, `backend/src/gobernar360/main.py`

**Interfaces:**
- Produces in `dashboards/registry.py`:
  - `@dataclass(frozen=True) SummaryIndicator(key: str, value: float | int | None, unit: str | None = None)`
  - `@dataclass(frozen=True) DashboardModule(key: str, router: APIRouter, get_summary: Callable[[RequestContext], list[SummaryIndicator]])`
  - `register(module)`, `all_modules() -> list[DashboardModule]`, `get_module(key) -> DashboardModule | None`, `clear()` (tests).
  - `create_app()` mounts each module router at `/api/dashboards/{key}`.
- Produces in `platform/access.py`:
  - `class AccessLevel(IntEnum): NONE = 0; VIEWER = 1; EDITOR = 2; ADMIN = 3`
  - `@dataclass RequestContext(user: User, municipality_id: uuid.UUID, membership: Membership, db: Session)`, where `db` is a `tenant_session`.
  - `get_current_user(...) -> User` (401 `not_authenticated`)
  - `get_context(...) -> RequestContext` (403 `forbidden` when no active municipality or membership no longer exists)
  - `effective_level(db, membership, dashboard_key) -> AccessLevel`: `NONE` if the dashboard is not enabled for the municipality or not registered; `ADMIN` if `membership.is_admin`; otherwise the grant level, or `NONE`.
  - `require_dashboard(key: str, level: AccessLevel) -> Callable[..., RequestContext]` (dependency factory; 403 `forbidden`)
  - `require_operator(...) -> User`, `require_municipality_admin(...) -> RequestContext`
- A platform operator has no access to municipality data unless they also hold a membership.

- [ ] **Step 1:** Write failing tests. They register a throwaway module `DashboardModule("demo", router, lambda ctx: [])` whose router has `GET /read` (VIEWER), `POST /write` (EDITOR), `PUT /settings` (ADMIN):
  - `test_user_without_grant_is_forbidden`
  - `test_viewer_can_read_but_not_write`
  - `test_editor_can_write_but_not_change_settings`
  - `test_dashboard_admin_can_change_settings`
  - `test_municipality_admin_has_admin_level_on_every_enabled_dashboard`
  - `test_grant_is_ignored_when_dashboard_is_not_enabled_for_the_municipality`
  - `test_operator_without_membership_cannot_reach_municipality_data`
  - `test_request_is_forbidden_after_membership_is_removed` (login, delete membership, `GET /read` → 403, and `/auth/me` shows no memberships)
  - `test_me_lists_effective_dashboard_levels`
- [ ] **Step 2:** Run `uv run pytest tests/platform/test_access.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement the registry and access module; fill `Me.dashboards` using `effective_level`.
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add per-dashboard access levels and dashboard module registry`.

### Task 5: Operator and municipality administration, audit, CLI

**Files:**
- Create: `backend/src/gobernar360/platform/operator_router.py`, `backend/src/gobernar360/platform/admin_router.py`, `backend/src/gobernar360/platform/audit.py`, `backend/src/gobernar360/cli.py`, `backend/tests/platform/test_operator.py`, `backend/tests/platform/test_admin_users.py`, `backend/tests/platform/test_audit.py`
- Modify: `backend/src/gobernar360/main.py`

**Interfaces:**
- Operator routes (`require_operator`): `GET /api/platform/municipalities`; `POST /api/platform/municipalities {name, slug, kind}` (409 `conflict` on duplicate slug); `GET /api/platform/dashboards` → registered keys; `PUT /api/platform/municipalities/{id}/dashboards {keys: [str]}` (422 for unregistered keys); `POST /api/platform/municipalities/{id}/admins {email, full_name, password}` (creates the user if the email is new, otherwise reuses it; membership with `is_admin=True`).
- Admin routes (`require_municipality_admin`): `GET /api/admin/users` → `[{membership_id, user: {id, email, full_name}, is_admin, grants: {key: level}}]` for the active municipality only; `POST /api/admin/users {email, full_name, password, is_admin, grants}`; `PATCH /api/admin/users/{membership_id} {is_admin?, grants?}`; `DELETE /api/admin/users/{membership_id}` (removes the membership, not the user); `GET /api/admin/dashboards` → keys enabled for the municipality.
- Passwords: minimum 10 characters (422). An admin cannot remove or demote themselves when they are the last admin of the municipality (409 `conflict`).
- `platform/audit.py`: `record_change(ctx: RequestContext, action: str, entity: Base, changes: dict | None = None) -> None` adds an `AuditLog` row; `apply_audit_fields(ctx, entity, creating: bool) -> None` sets `created_by`/`updated_by`/`updated_at`.
- CLI: `gobernar360 create-operator --email --full-name` (prompts for password); `gobernar360 seed-demo` (implemented in Task 12; stub that exits with "not implemented" now is not allowed — omit the command until Task 12).

- [ ] **Step 1:** Write failing tests:
  - Operator: `test_operator_creates_municipality`, `test_duplicate_slug_returns_conflict`, `test_non_operator_cannot_manage_municipalities` (403), `test_operator_enables_dashboards_for_a_municipality`, `test_enabling_an_unregistered_dashboard_is_rejected`, `test_operator_creates_first_admin_of_a_municipality`.
  - Admin: `test_admin_lists_only_users_of_the_active_municipality`, `test_admin_creates_user_with_grants`, `test_creating_user_with_existing_email_in_same_municipality_returns_conflict` (case-insensitive), `test_existing_user_of_another_municipality_gets_a_second_membership`, `test_admin_changes_grant_level`, `test_admin_cannot_edit_membership_of_another_municipality` (404), `test_last_admin_cannot_demote_or_remove_themselves`, `test_non_admin_cannot_manage_users`, `test_short_password_is_rejected`.
  - Audit: `test_record_change_stores_actor_entity_and_changes`.
- [ ] **Step 2:** Run `uv run pytest tests/platform -v`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement routers, audit helpers and `create-operator`.
- [ ] **Step 4:** Run `uv run pytest -v && uv run ruff check .`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add operator and municipality user administration`.

### Task 6: Projects module — models and parameters

**Files:**
- Create: `backend/src/gobernar360/dashboards/projects/{__init__,models,schemas,sdgs,parameters_router}.py`, `backend/migrations/versions/0002_projects.py`, `backend/tests/projects/test_parameters.py`, `backend/tests/test_architecture.py`, `backend/.importlinter`
- Modify: `backend/src/gobernar360/main.py`, `backend/tests/factories.py`

**Interfaces:**
- Module key: `"projects"`. `dashboards/projects/__init__.py` exposes `module: DashboardModule`; `create_app()` registers it.
- Models (all with `TenantMixin`, `AuditMixin`, uuid id, RLS via `enable_tenant_rls`; foreign keys `ON DELETE RESTRICT` unless noted):
  - `Term` → `projects_terms(name, start_year, end_year)`; check `end_year >= start_year`
  - `AnnualBudget` → `projects_annual_budgets(term_id, year, total_amount numeric(16,2))`, unique `(term_id, year)`
  - `Axis` → `projects_axes(term_id, name)`
  - `Objective` → `projects_objectives(axis_id, name)`
  - `Department` → `projects_departments(name)`; `Program` → `projects_programs(name)`; `Owner` → `projects_owners(full_name)`
  - `Project` → `projects_projects(term_id, name, description, axis_id, objective_id null, department_id, owner_id null, program_id null, priority, year, start_date null, end_date null, planned_budget numeric(16,2) default 0, executed_budget numeric(16,2) default 0, status, manual_progress int null)`; checks: `priority in ('A+','A','B','C')`, `status in ('not_started','in_progress','finished')`, `manual_progress between 0 and 100`, budgets `>= 0`
  - `ProjectSdg` → `projects_project_sdgs(project_id ON DELETE CASCADE, sdg_number)`, check `1..17`, primary key both (plus `municipality_id`)
  - `Milestone` → `projects_milestones(project_id ON DELETE CASCADE, name, due_date, completed_on date null)`
  - `Indicator` → `projects_indicators(objective_id, name, unit, baseline numeric null, target numeric null, current_value numeric null)`
- `sdgs.py`: `SDG_NUMBERS = range(1, 18)`; titles live in the frontend locale file.
- Parameter routes under `/api/dashboards/projects` (read: VIEWER; write: ADMIN). Each resource has `GET` (list), `POST`, `PATCH /{id}`, `DELETE /{id}`: `/terms`, `/terms/{term_id}/budgets` (`PUT {year, total_amount}` upserts), `/axes?term_id=`, `/objectives?axis_id=`, `/departments`, `/programs`, `/owners`.
- Shared helper in `schemas.py` or a small `refs.py`: `resolve(ctx, Model, id) -> Model` loads through `ctx.db` and raises 422 `invalid_reference` when not visible.
- Deleting a referenced row returns 409 `in_use` (catch `IntegrityError`).
- `.importlinter`: contract `independence` over `gobernar360.dashboards.*` subpackages (excluding `registry`), and contract `forbidden`: `gobernar360.core` and `gobernar360.platform` may not import `gobernar360.dashboards.projects`.
- Factories added: `projects_user(level="editor") -> tuple[Municipality, User]` (municipality with `projects` enabled and a logged-in-ready user), `make_term`, `make_axis`, `make_department`.

- [ ] **Step 1:** Write failing tests:
  - `test_dashboard_admin_creates_term_axis_and_objective`
  - `test_editor_cannot_change_parameters` (403)
  - `test_viewer_lists_parameters`
  - `test_parameters_of_another_municipality_are_not_listed`
  - `test_objective_cannot_reference_axis_of_another_municipality` (422 `invalid_reference`)
  - `test_deleting_axis_used_by_a_project_returns_in_use` (409; insert the project directly with the ORM)
  - `test_term_end_year_before_start_year_is_rejected` (422)
  - `test_annual_budget_upsert_replaces_existing_year`
  - `test_parameter_change_is_audited`
  - `test_architecture.py::test_dashboard_modules_do_not_import_each_other`: `subprocess.run(["lint-imports"], cwd=backend)` exits 0.
- [ ] **Step 2:** Run `uv run pytest tests/projects tests/test_architecture.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement models, migration `0002_projects`, schemas, router, module registration and import-linter config.
- [ ] **Step 4:** Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add projects dashboard data model and parameters`.

### Task 7: Projects module — rules, projects, milestones, indicators

**Files:**
- Create: `backend/src/gobernar360/dashboards/projects/rules.py`, `backend/src/gobernar360/dashboards/projects/projects_router.py`, `backend/tests/projects/test_rules.py`, `backend/tests/projects/test_projects_api.py`
- Modify: `backend/src/gobernar360/dashboards/projects/{__init__,schemas}.py`

**Interfaces:**
- `rules.py` (pure, no database):
  - `@dataclass(frozen=True) MilestoneState(due_date: date, completed_on: date | None)`
  - `milestone_in_alert(m: MilestoneState, today: date) -> bool`: not completed and `due_date < today`
  - `effective_status(status: str, end_date: date | None, milestones: Sequence[MilestoneState], today: date) -> str`: `'finished'` stays; otherwise `'delayed'` when `end_date < today` or any milestone is in alert; otherwise the stored status
  - `progress_percent(status: str, milestones: Sequence[MilestoneState], manual_progress: int | None) -> int`: `100` when finished; with milestones, `round(100 * completed / total)`; without, `manual_progress or 0`
- Routes under `/api/dashboards/projects` (read: VIEWER; write: EDITOR):
  - `GET /projects?term_id=&year=&axis_id=&department_id=&owner_id=&priority=&status=` (`status` filters on effective status), `POST /projects`, `GET /projects/{id}`, `PATCH /projects/{id}`, `DELETE /projects/{id}`
  - `POST /projects/{id}/milestones`, `PATCH /milestones/{id}`, `DELETE /milestones/{id}`
  - `GET /indicators?term_id=&objective_id=`, `POST /indicators`, `PATCH /indicators/{id}`, `DELETE /indicators/{id}`
  - `GET /sdgs` → `[1..17]`
- `ProjectOut`: stored fields plus `effective_status`, `progress`, `sdgs: list[int]`, `milestones: [{id, name, due_date, completed_on, in_alert}]`, and `{id, name}` objects for axis, objective, department, owner, program.
- Validation: every referenced id goes through `resolve`; `objective_id` must belong to `axis_id`, and `axis_id` to `term_id` (422 `invalid_reference`); `year` within the term's years (422); `end_date >= start_date` (422).
- "Today" comes from a dependency `get_today() -> date` so tests can override it.

- [ ] **Step 1:** Write failing unit tests in `test_rules.py`:
  - `test_unfinished_milestone_past_due_is_in_alert`; `test_milestone_due_today_is_not_in_alert`; `test_completed_milestone_is_never_in_alert`
  - `test_project_past_end_date_is_delayed`; `test_project_with_a_milestone_in_alert_is_delayed`; `test_finished_project_is_never_delayed`; `test_not_started_project_within_dates_keeps_its_status`
  - `test_progress_is_share_of_completed_milestones` (1 of 3 → 33); `test_progress_without_milestones_uses_manual_value`; `test_progress_without_milestones_or_manual_value_is_zero`; `test_finished_project_progress_is_100`
- [ ] **Step 2:** Write failing API tests in `test_projects_api.py`:
  - `test_editor_creates_project_with_sdgs`; `test_viewer_cannot_create_project` (403)
  - `test_project_cannot_reference_axis_of_another_municipality` (create the axis in municipality B, post from A → 422 `invalid_reference`, and no row is created)
  - `test_objective_must_belong_to_the_project_axis`; `test_project_year_outside_term_is_rejected`; `test_end_date_before_start_date_is_rejected`; `test_sdg_number_out_of_range_is_rejected`
  - `test_project_list_filters_by_year_axis_department_owner_and_priority`
  - `test_project_list_filters_by_delayed_status`
  - `test_project_of_another_municipality_returns_not_found` (GET, PATCH, DELETE → 404)
  - `test_completing_milestones_updates_progress_and_alert`
  - `test_editor_manages_indicators`; `test_project_changes_are_audited`
- [ ] **Step 3:** Run `uv run pytest tests/projects -v`. Expected: new tests FAIL.
- [ ] **Step 4:** Implement `rules.py`, schemas and the router.
- [ ] **Step 5:** Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 6:** Commit: `feat: add projects, milestones and indicators`.

### Task 8: Projects module — summary, export and overview

**Files:**
- Create: `backend/src/gobernar360/dashboards/projects/summary.py`, `backend/src/gobernar360/dashboards/projects/export.py`, `backend/src/gobernar360/platform/overview_router.py`, `backend/tests/projects/test_summary.py`, `backend/tests/projects/test_export.py`, `backend/tests/platform/test_overview.py`
- Modify: `backend/src/gobernar360/dashboards/projects/__init__.py`, `backend/src/gobernar360/main.py`

**Interfaces:**
- `GET /api/dashboards/projects/summary?term_id=&year=&axis_id=&department_id=&owner_id=&priority=` (VIEWER; `term_id` required) returns:
  ```json
  {"status_counts": {"not_started": 0, "in_progress": 0, "delayed": 0, "finished": 0},
   "active_count": 0, "finished_count": 0, "average_progress": 0,
   "budget": {"total": null, "planned": "0.00", "executed": "0.00", "planned_ratio": null, "executed_ratio": null},
   "milestones": {"total": 0, "completed": 0, "in_alert": 0},
   "by_department": [{"id": "...", "name": "...", "count": 0}],
   "by_owner": [], "by_program": [], "by_sdg": [{"sdg": 1, "count": 0}]}
  ```
  - `active_count` = not finished. `average_progress` is the rounded mean of `progress_percent`, `0` with no projects.
  - `budget.total` = sum of `AnnualBudget.total_amount` for the term (only the filtered year when `year` is given), `null` when none is set. `planned_ratio = planned / total`, `executed_ratio = executed / planned`; each is `null` when its denominator is `null` or zero. Money values are strings with two decimals; ratios are floats rounded to 4 places.
  - `by_owner`/`by_program` skip projects without one; `by_sdg` lists only SDGs with at least one project.
- `compute_summary(projects: Sequence[ProjectSnapshot], total_budget: Decimal | None, today: date) -> SummaryOut` is a pure function in `summary.py`; the route loads data and calls it.
- `get_summary(ctx) -> list[SummaryIndicator]` for the overview, over the most recent term (highest `start_year`); empty list when there is no term. Keys: `projects.active`, `projects.finished`, `projects.delayed`, `projects.average_progress` (unit `percent`), `projects.milestones_in_alert`, `projects.budget_executed_ratio` (unit `ratio`).
- `GET /api/dashboards/projects/export/projects.csv` and `/export/indicators.csv` (VIEWER; same filters as the list endpoints): `text/csv; charset=utf-8`, UTF-8 with BOM, `Content-Disposition: attachment`. Project columns: `name, term, year, axis, objective, department, owner, program, priority, status, progress, planned_budget, executed_budget, start_date, end_date, sdgs` (SDGs joined with `;`, status is the effective status). Indicator columns: `name, axis, objective, unit, baseline, target, current_value`. A cell starting with `=`, `+`, `-` or `@` is prefixed with `'`.
- `GET /api/overview` (any authenticated user with an active municipality) → `[{dashboard_key, indicators: [{key, value, unit}]}]`, one entry per registered module where the user's effective level is at least VIEWER.

- [ ] **Step 1:** Write failing tests:
  - Summary: `test_summary_of_term_without_projects_is_all_zero_and_null_ratios`; `test_summary_counts_projects_by_effective_status`; `test_summary_budget_ratios` (annual budget 1000, planned 400, executed 100 → `planned_ratio 0.4`, `executed_ratio 0.25`); `test_summary_with_zero_planned_budget_has_null_executed_ratio`; `test_summary_counts_milestones_and_alerts`; `test_summary_groups_by_department_owner_program_and_sdg`; `test_summary_respects_filters`; `test_summary_excludes_other_municipalities`.
  - Export: `test_projects_csv_has_header_bom_and_one_row_per_project`; `test_csv_preserves_accented_characters` (project named `Pavimentación Año 1`); `test_csv_neutralises_formula_cells` (name `=SUM(A1)` exported as `'=SUM(A1)`); `test_indicators_csv_lists_indicators`.
  - Overview: `test_overview_includes_projects_indicators_for_a_viewer`; `test_overview_omits_dashboards_the_user_cannot_see`; `test_overview_for_municipality_without_terms_has_empty_indicators`.
- [ ] **Step 2:** Run `uv run pytest tests/projects tests/platform/test_overview.py -v`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement summary, export and overview.
- [ ] **Step 4:** Run `uv run pytest -v && uv run ruff check . && uv run lint-imports`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add projects summary, CSV export and general overview`.

### Task 9: Frontend shell — scaffolding, login, navigation

**Files:**
- Create: `frontend/` via Vite (`react-ts` template), `frontend/src/api/client.ts`, `frontend/src/i18n.ts`, `frontend/src/locales/es-AR.json`, `frontend/src/platform/{AuthProvider,LoginPage,AppShell,MunicipalitySwitcher,RequireDashboard}.tsx`, `frontend/src/dashboards/registry.ts`, `frontend/src/dashboards/overview/OverviewPage.tsx`, `frontend/src/test/{setup.ts,render.tsx}`, tests next to components (`*.test.tsx`)
- Modify: `frontend/vite.config.ts`, `frontend/src/{main,App}.tsx`, `docker-compose.yml` (no change needed for dev; leave as is)

**Interfaces:**
- Dependencies: `@mantine/core @mantine/hooks @mantine/form @mantine/notifications @mantine/dates dayjs @tanstack/react-query react-router-dom i18next react-i18next recharts`; dev: `vitest @testing-library/react @testing-library/user-event @testing-library/jest-dom jsdom msw`.
- Vite dev server proxies `/api` to `http://localhost:8000`.
- `api/client.ts`: `api<T>(path: string, init?: {method?, body?, query?}) -> Promise<T>` (prefixes `/api`, sends `credentials: 'include'` and `X-Requested-With: gobernar360`, JSON-encodes the body, throws `ApiError {status, code, message}`); `downloadUrl(path, query) -> string`.
- Types (in `platform/types.ts`): `Me`, `AccessLevel = 'viewer' | 'editor' | 'admin'`, and `hasLevel(me: Me, key: string, min: AccessLevel) -> boolean`.
- `AuthProvider` exposes `useAuth() -> {me: Me | null, isLoading, login(email, password), logout(), setActiveMunicipality(id)}` backed by the `['me']` query.
- `dashboards/registry.ts`: `interface DashboardEntry {key: string; labelKey: string; basePath: string; routes: React.LazyExoticComponent<...>}`; `export const dashboards: DashboardEntry[]`. Projects is added in Task 10.
- Routes: `/login`; `/` → `OverviewPage`; `/d/{key}/*` → module routes wrapped in `RequireDashboard`; `/admin/users` (Task 11); `/platform` (Task 11). Unauthenticated users are redirected to `/login`.
- `AppShell`: sidebar with "Resumen general" plus one link per dashboard in `me.dashboards` that exists in the registry; header with the municipality name, `MunicipalitySwitcher` (only when more than one membership) and a logout button; "Usuarios" link only for municipality admins; "Plataforma" link only for operators.
- `OverviewPage`: fetches `/overview`, renders one card group per dashboard with indicator labels from `overview.indicators.{key}` in the locale file; values with unit `percent` render as `NN %`, `ratio` as a percentage, `null` as `—`.
- A municipality member with no dashboards sees an explanatory empty state, not a blank page.

- [ ] **Step 1:** Scaffold with `npm create vite@latest frontend -- --template react-ts`, install dependencies, configure Vitest (`jsdom`, setup file with jest-dom and an MSW server) and the proxy. `src/test/render.tsx` exports `renderApp(ui, {me?, route?})` wrapping providers.
- [ ] **Step 2:** Write failing tests:
  - `LoginPage.test.tsx`: `shows an error message when credentials are rejected`; `redirects to the overview after a successful login`.
  - `AppShell.test.tsx`: `lists only the dashboards granted to the user`; `hides the users link from non-admin members`; `shows the municipality switcher only with several memberships`.
  - `OverviewPage.test.tsx`: `renders indicators returned by the overview endpoint`; `shows an empty state when the user has no dashboards`.
  - `client.test.ts`: `throws ApiError with the server error code`; `sends the CSRF header on every request`.
- [ ] **Step 3:** Run `npm test -- --run`. Expected: FAIL.
- [ ] **Step 4:** Implement the shell.
- [ ] **Step 5:** Run `npm test -- --run && npm run build && npm run lint`. Expected: all pass.
- [ ] **Step 6:** Commit: `feat: add web shell with login, navigation and overview`.

### Task 10: Frontend — Projects dashboard

**Files:**
- Create: `frontend/src/dashboards/projects/{routes,api,types,TermContext,SummaryPage,ProjectsPage,ProjectForm,MilestonesPanel,IndicatorsPage,ParametersPage}.tsx` (`api.ts`, `types.ts` as `.ts`), tests next to components
- Modify: `frontend/src/dashboards/registry.ts`, `frontend/src/locales/es-AR.json`

**Interfaces:**
- Consumes: `api`, `useAuth`, `hasLevel` from Task 9; endpoints from Tasks 6–8.
- Registry entry: `{key: 'projects', labelKey: 'projects.title', basePath: '/d/projects', routes: lazy(() => import('./projects/routes'))}`.
- Sub-routes: `` (summary), `projects`, `projects/:id`, `indicators`, `parameters` (visible and reachable only with `admin` level).
- `TermContext`: the selected term ("gestión"), persisted in `localStorage` under `g360.projects.term` (wrapped in try/catch), defaulting to the term with the highest `start_year`; a "Cambiar gestión" select in the dashboard header. With no terms: an empty state that links admins to Parameters.
- `SummaryPage`: filter bar (year, axis, department, owner, priority); stat cards (status counts, active/finished, average progress, budget total / planned % / executed %, milestones completed/total and in alert); bar charts by department, owner and program; SDG chart; "Descargar proyectos" and "Descargar indicadores" links built with `downloadUrl` carrying the current filters.
- `ProjectsPage`: table (name, axis, department, owner, priority, effective status badge, progress bar) with the same filters; "Cargar nuevo proyecto" button only for `editor` and above.
- `ProjectForm`: Mantine form for all project fields; the objective select is filtered by the chosen axis; SDG multi-select with titles from `projects.sdg.{n}`; manual progress input shown only when the project has no milestones; server 422 errors are shown next to the form.
- `MilestonesPanel` (inside project detail): list with alert badge, add, mark completed, delete.
- `IndicatorsPage`: table grouped by axis and objective, showing `current_value / target` and percent of target when both exist.
- `ParametersPage`: tabs for terms (with annual budgets), axes and objectives, departments, programs, owners; a 409 `in_use` shows the message from `errors.in_use`.
- Locale: status labels `Sin iniciar`, `En implementación`, `Retrasado`, `Finalizado`; priorities `A+`, `A`, `B`, `C`; the 17 official SDG titles in Spanish.

- [ ] **Step 1:** Write failing tests (MSW-backed):
  - `SummaryPage.test.tsx`: `renders status counts and budget percentages`; `shows a dash when a ratio is null`; `refetches the summary when a filter changes`; `export links carry the current filters`.
  - `ProjectsPage.test.tsx`: `hides the create button from viewers`; `shows a delayed badge for delayed projects`.
  - `ProjectForm.test.tsx`: `limits objectives to the selected axis`; `submits the selected sdgs`; `shows the server validation message`.
  - `MilestonesPanel.test.tsx`: `marks a milestone as completed`; `flags milestones in alert`.
  - `ParametersPage.test.tsx`: `explains that a parameter in use cannot be deleted`.
  - `TermContext.test.tsx`: `defaults to the most recent term`; `shows an empty state when there are no terms`.
- [ ] **Step 2:** Run `npm test -- --run`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement the module.
- [ ] **Step 4:** Run `npm test -- --run && npm run build && npm run lint`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add projects dashboard to the web app`.

### Task 11: Frontend — user and platform administration

**Files:**
- Create: `frontend/src/platform/{UsersAdminPage,UserForm,OperatorPage}.tsx` and tests
- Modify: `frontend/src/App.tsx`, `frontend/src/locales/es-AR.json`

**Interfaces:**
- Consumes: `/api/admin/*` and `/api/platform/*` from Task 5.
- `UsersAdminPage` (`/admin/users`, municipality admins only): table of members with one access-level select per enabled dashboard (`Sin acceso`, `Lectura`, `Carga`, `Administración`) and an administrator switch; "Agregar usuario" opens `UserForm` (email, full name, initial password, admin switch, grants); remove button with confirmation.
- `OperatorPage` (`/platform`, operators only): list of municipalities; create form (name, slug, kind); per municipality, checkboxes for registered dashboards and a "Crear administrador" form.
- An operator with no membership lands on `/platform` after login instead of the overview.

- [ ] **Step 1:** Write failing tests: `UsersAdminPage.test.tsx` (`changes a user's access level for a dashboard`; `shows the conflict message when removing the last admin`; `redirects non-admin members away`), `UserForm.test.tsx` (`rejects passwords shorter than ten characters`), `OperatorPage.test.tsx` (`creates a municipality`; `enables a dashboard for a municipality`).
- [ ] **Step 2:** Run `npm test -- --run`. Expected: new tests FAIL.
- [ ] **Step 3:** Implement the pages and routes.
- [ ] **Step 4:** Run `npm test -- --run && npm run build && npm run lint`. Expected: all pass.
- [ ] **Step 5:** Commit: `feat: add user and municipality administration screens`.

### Task 12: Demo data and end-to-end verification

**Files:**
- Create: `backend/src/gobernar360/seed.py`, `backend/tests/test_seed.py`, `frontend/playwright.config.ts`, `frontend/e2e/{platform,projects}.spec.ts`
- Modify: `backend/src/gobernar360/cli.py`, `README.md`, `frontend/package.json` (script `e2e`)

**Interfaces:**
- `seed.seed_demo(reset: bool = False) -> None`, exposed as `gobernar360 seed-demo [--reset]`; idempotent. Creates:
  - operator `operador@gobernar360.test`
  - municipality `Noetinger` (slug `noetinger`, kind `municipality`) with `projects` enabled; users `admin@noetinger.test` (admin), `carga@noetinger.test` (projects editor), `lectura@noetinger.test` (projects viewer), `sinacceso@noetinger.test` (no grants)
  - municipality `Comuna Demo` (slug `comuna-demo`, kind `commune`) with `projects` enabled; user `admin@comuna-demo.test` (admin)
  - all passwords `gobernar360-demo`
  - for Noetinger: term `Gestión 2023-2027`, annual budgets, the four axes and several departments from the RIL reference (section 4), programs, owners, about 12 projects spread over statuses, priorities, years and SDGs (some with overdue milestones), and a few indicators
  - for Comuna Demo: one term and two projects, so isolation is visible
- Playwright: `baseURL http://localhost:5173`; `webServer` entries start the API (`uv run uvicorn gobernar360.main:create_app --factory --port 8000`) and `npm run dev`; a global setup runs `uv run alembic upgrade head` and `uv run gobernar360 seed-demo --reset`.

- [ ] **Step 1:** Write failing test `test_seed_demo_is_idempotent_and_creates_two_isolated_municipalities` (run twice; 2 municipalities; Noetinger has at least 10 projects; Comuna Demo's tenant session sees exactly 2).
- [ ] **Step 2:** Run `uv run pytest tests/test_seed.py -v`. Expected: FAIL.
- [ ] **Step 3:** Implement `seed.py` and the CLI command. Run `uv run pytest -v`. Expected: all pass.
- [ ] **Step 4:** Write the end-to-end specs:
  - `platform.spec.ts`: `operator creates a municipality and enables the projects dashboard`; `member without grants does not see the projects dashboard`; `admin grants a user read access and the dashboard appears for them`.
  - `projects.spec.ts`: `editor creates a project with a milestone and the summary updates`; `viewer cannot see the create button and a direct POST is forbidden`; `overview shows the projects indicators`; `admin of the second municipality sees none of the first municipality's projects`; `projects csv download contains the seeded projects`.
- [ ] **Step 5:** Run `npm run e2e`. Expected: all specs pass.
- [ ] **Step 6:** Update `README.md` (quick start, demo accounts, test commands). Commit: `feat: add demo data and end-to-end tests`.
