# Economic Dashboard and People Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the per-municipality people registry to the platform and the Economic dashboard (actors, people, tools, assignments, summary, reports, exports) on top of it.

**Architecture:** `people` is a tenant table owned by the platform (`platform/people.py`: model helpers and schemas, no routes). The dashboard module `dashboards/economic` follows the environment module: `access.py`, `models.py`, `schemas.py`, one router per area, registered in `main.py`. A person enters the dashboard through the link table `economic_people`; every economic foreign key to a person points at that link, so the dashboard can only reach people it incorporated. The web gets `frontend/src/dashboards/economic/` registered in `registry.ts`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest against `gobernar360_test`; React + Mantine + TanStack Query + Recharts, Vitest + MSW, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-19-economic-dashboard-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Routes flush, never commit. Every id taken from a request body goes through `tenant_crud.resolve`. Writes go through `tenant_crud` so they are audited.
- Every new table is tenant data: `TenantMixin`, and its migration calls `enable_tenant_rls` with a literal table list.
- Dashboard modules never import each other; `economic` is added to both contracts of `backend/.importlinter`.
- Lists of actors, people and assignments answer `{items, total}` and take `q`, `limit` (default 50, max 200) and `offset`.
- One local commit per task on `main`; never push. Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Backend checks: `uv run ruff format -q . && uv run ruff check . && uv run lint-imports && uv run pytest -q`. Frontend checks: `npx tsc -b && npm run lint && npm test -- --run`.

## Review Focus

- A person incorporated only by another dashboard (present in `people`, absent from `economic_people`): never listed, never reachable by id, only found by exact DNI lookup.
- Ids of another municipality in any body (`actor_type_id`, `sector_id`, `category_id`, `subcategory_id`, `tool_id`, `actor_id`, `person_id`): 422 `invalid_reference`, nothing written.
- Assignment with both or neither of `actor_id`/`person_id`, or with a tool whose audience excludes the target: 422.
- DNI typed with dots or spaces, a duplicate DNI on create (reuse) and on edit (409 `dni_exists`), and an already incorporated person (409 `already_registered`).
- Search text containing `%` or `_` matches literally; `limit` above 200 or negative `offset` is 422.

---

### Task 1: People registry in the platform

**Files:**
- Create: `backend/src/gobernar360/platform/people.py`, `backend/migrations/versions/0004_people.py`, `backend/tests/platform/test_people.py`
- Modify: `backend/src/gobernar360/platform/models.py` (`Person`), `backend/src/gobernar360/core/errors.py` (`dni_exists()` → 409 `dni_exists`)

**Interfaces (produced):**
- `Person(TenantMixin, AuditMixin, Base)`, table `people`: `first_name` (100), `last_name` (100), `dni` (20, nullable, `UniqueConstraint(municipality_id, dni)`), `birth_date` (Date, nullable), `phone` (50), `email` (200), `address` (200), `neighborhood` (100); text columns default `""`.
- `people.Dni` (annotated str: strips `.` and spaces, then 6–9 digits), `PersonIn`, `PersonPatch(PatchModel)` (`nullable = {dni, birth_date}`), `PersonOut`.
- `people.find_by_dni(ctx, dni: str) -> Person | None`
- `people.create_person(ctx, data: PersonIn) -> Person` (duplicate DNI → `dni_exists`)
- `people.update_person(ctx, person, changes: dict) -> Person` (duplicate DNI → `dni_exists`; no-op for empty changes)
- `people.release_person(ctx, person) -> bool` — deletes the registry row inside a savepoint; returns False and keeps it when something still references it.

- [ ] **Step 1: Failing tests** (`test_people.py`; a `ctx` helper builds a `RequestContext` on `tenant_session`): `test_person_is_created_with_a_normalised_dni` (`"12.345.678"` → `"12345678"`), `test_invalid_dni_is_rejected` (`"12"`, `"abc"`, 10 digits), `test_two_people_without_dni_can_coexist`, `test_duplicate_dni_in_the_same_municipality_is_rejected`, `test_same_dni_in_two_municipalities_is_allowed`, `test_find_by_dni_does_not_cross_municipalities`, `test_update_rejects_a_dni_used_by_someone_else`, `test_changes_are_audited`, `test_release_deletes_an_unreferenced_person`, `test_people_table_enforces_tenant_isolation` (RLS flags as in the environment test).
- [ ] **Step 2: Run** `uv run pytest tests/platform/test_people.py -q` — Expected: FAIL (import error).
- [ ] **Step 3: Implement** model, `uv run alembic revision --autogenerate --rev-id 0004 -m people` (renamed `0004_people.py`, plus `enable_tenant_rls("people")`), `people.py`.
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add the people registry to the platform`.

### Task 2: Economic module — tables, parameters and tools

**Files:**
- Create: `backend/src/gobernar360/dashboards/economic/{__init__,access,models,schemas,parameters_router}.py`, `backend/migrations/versions/0005_economic.py`, `backend/tests/economic/{__init__,factories,test_parameters}.py`
- Modify: `backend/src/gobernar360/main.py`, `backend/migrations/env.py`, `backend/.importlinter`

**Interfaces (produced):**
- `KEY = "economic"`; `Viewer`, `Editor`, `Admin`.
- Models: `ActorType`, `Sector`, `ToolCategory` (`name`); `ToolSubcategory` (`category_id`, `name`); `Tool` (`category_id`, `subcategory_id?`, `name`, `description`, `audience` ∈ `AUDIENCES = ("actors", "people", "both")`); `Actor` (`name`, `actor_type_id?`, `sector_id?`, `cuit` 11 digits or `""`, `address`, `phone`, `email`, `employee_count?` ≥ 0, `notes`); `EconomicPerson` table `economic_people` (`person_id` → `people.id` unique, `employment_status` ∈ `EMPLOYMENT_STATUSES = ("unknown", "employed", "self_employed", "unemployed", "student", "retired", "other")`, `occupation`); `ActorPerson` table `economic_actor_people` (`actor_id` CASCADE, `person_id` → `economic_people.id` CASCADE, `role` ∈ `ROLES = ("owner", "contact", "employee")`, unique pair); `Assignment` (`tool_id`, `actor_id?`, `person_id?` → `economic_people.id`, `date`, `note`; check exactly one target). Other foreign keys RESTRICT.
- API under `/api/dashboards/economic`: `GET/POST /actor-types`, `PATCH/DELETE /actor-types/{id}`; same for `/sectors`, `/tool-categories`, `/tool-subcategories` (POST takes `category_id`; PATCH only `name`); `/tools` with `ToolIn(category_id, subcategory_id?, name, description="", audience="both")`, `ToolPatch`, `ToolOut(id, name, description, audience, category: NamedRef, subcategory: NamedRef | None)`. Reads: Viewer; writes: Admin.
- Test factories: `economic_member(level, email, municipality)`, `make_actor_type`, `make_sector`, `make_tool_category`, `make_tool_subcategory`, `make_tool`, `make_actor`, `make_person` (registry row), `make_economic_person`, `make_actor_person`, `make_assignment`.

- [ ] **Step 1: Failing tests** (`test_parameters.py`): `test_dashboard_admin_manages_each_catalog` (parametrised over the three name catalogs: create trims, rename, list sorted, delete), `test_subcategory_belongs_to_a_category`, `test_tool_is_created_listed_and_updated`, `test_tool_subcategory_must_belong_to_its_category` (422), `test_tool_cannot_reference_parameters_of_another_municipality` (422 `invalid_reference`), `test_unknown_audience_is_rejected`, `test_editor_cannot_change_parameters` (403), `test_viewer_lists_parameters`, `test_member_without_grant_is_rejected`, `test_parameters_of_another_municipality_are_not_listed_nor_editable`, `test_deleting_parameters_in_use_returns_in_use`, `test_parameter_change_is_audited`, `test_every_economic_table_enforces_tenant_isolation` (the nine `economic_*` tables).
- [ ] **Step 2: Run** `uv run pytest tests/economic -q` — Expected: FAIL.
- [ ] **Step 3: Implement**; migration via autogenerate `--rev-id 0005 -m economic` plus the RLS loop.
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add the economic dashboard module with its parameters and tools`.

### Task 3: Actors and people

**Files:**
- Create: `backend/src/gobernar360/dashboards/economic/{actors_router,people_router,listing}.py`, `backend/tests/economic/{test_actors,test_people}.py`
- Modify: `dashboards/economic/__init__.py`, `schemas.py`, `core/errors.py` (`already_registered()` → 409)

**Interfaces (produced):**
- `listing.Paging` dependency (`limit: int = 50` 1..200, `offset: int = 0` ≥ 0), `listing.page(ctx, query, paging) -> tuple[list, int]`, `listing.contains(column, text)` (case-insensitive, `%`/`_` escaped).
- `GET /actors?q&actor_type_id&sector_id` → `Page[ActorOut]`; `POST /actors`; `GET /actors/{id}` → `ActorDetail` (`people: [{id, role, person: EconomicPersonOut}]`); `PATCH`, `DELETE`; `POST /actors/{id}/people {person_id, role}` → 201; `DELETE /actors/{id}/people/{link_id}`. Writes: Editor.
- `GET /people?q&employment_status` → `Page[EconomicPersonOut]` (`{id, person: PersonOut, employment_status, occupation}`), ordered by last name, first name; `GET /people/lookup?dni=` (Editor) → `{person: PersonOut | None, registered_id: uuid | None}`; `POST /people {person: PersonIn, employment_status="unknown", occupation=""}`; `GET /people/{id}` → `PersonDetail` (`actors: [{id, role, actor: NamedRef}]`); `PATCH /people/{id} {person?: PersonPatch, employment_status?, occupation?}`; `DELETE /people/{id}` (then `release_person`).

- [ ] **Step 1: Failing tests.** `test_actors.py`: create with defaults and with every field (CUIT `"30-71234567-8"` stored `"30712345678"`), invalid CUIT 422, list filters (`q` by name and CUIT, type, sector), pagination (`limit=2&offset=2`, total), `limit=201` 422, literal `%` search, update and clear type, foreign type/sector 422, detail lists linked people, link twice 409, link a person of another municipality 422, unlink, delete removes links, viewer cannot write, another municipality's actor 404, audit rows. `test_people.py`: create new, create reusing a registry person by DNI (registry row count stays 1; common data updated), already incorporated 409 `already_registered`, lookup (unknown / in registry only / incorporated; viewer 403; malformed DNI 422), a registry-only person is not listed and `GET /people/{registry id}` is 404, search by last name and DNI, filter by status, patch common and economic fields, patch DNI to one in use 409 `dni_exists`, delete releases the registry row, delete keeps it when the DNI… is still referenced (second link simulated with a test-only row is not possible, so: delete with assignments → 409 `in_use` in Task 4), other municipality 404, viewer cannot write.
- [ ] **Step 2: Run** `uv run pytest tests/economic -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: register economic actors and people`.

### Task 4: Assignments, summary, reports, exports, overview

**Files:**
- Create: `backend/src/gobernar360/dashboards/economic/{assignments_router,summary,export}.py`, `backend/tests/economic/{test_assignments,test_summary,test_export}.py`
- Modify: `dashboards/economic/__init__.py`, `schemas.py`, `backend/tests/platform/test_overview.py`

**Interfaces (produced):**
- `GET /assignments?year&tool_id&actor_id&person_id` → `Page[AssignmentOut]` (`{id, date, note, tool: NamedRef, actor: NamedRef | None, person: {id, full_name} | None}`), newest first; `POST /assignments {tool_id, actor_id? , person_id?, date, note=""}`; `PATCH /assignments/{id} {date?, note?}` (`extra="forbid"`); `DELETE`. Writes: Editor.
- `GET /summary?year` → `{year, actors: {total, with_assignments}, people: {total, with_assignments}, tools, assignments, actor_tools: [{tool, category, count}], person_tools: [...]}`.
- `GET /reports?year` → `{year, actors_by_type, actors_by_sector, assignments_by_category: [{name, count}], people_by_employment_status: [{status, count}], assignments_by_month: [{month, count}]}` (twelve months; actors without type or sector counted under `name: null`).
- `GET /export/actors.csv`, `/export/people.csv`, `/export/assignments.csv?year`.
- `get_summary(ctx, today)` → `economic.actors`, `economic.people`, `economic.tools`, `economic.assignments_year`; `[]` when all four are zero.

- [ ] **Step 1: Failing tests**: assignment to an actor and to a person; both or neither target 422; audience mismatch 422; foreign tool/actor/person 422; `person_id` of a registry-only person 422; list filters and year; patch only date and note; delete; deleting a tool / actor / person with assignments 409 `in_use`; viewer cannot write; summary counts (distinct recipients of the year, tools table sorted by count); empty summary; reports buckets including the untyped actor and all twelve months; exports (header, rows, formula neutralisation, other municipality excluded, 403 without access); overview indicators and empty overview.
- [ ] **Step 2: Run** `uv run pytest tests/economic tests/platform/test_overview.py -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add economic assignments, summary, reports and exports`.

### Task 5: Demo data

**Files:** Modify `backend/src/gobernar360/seed.py`, `backend/tests/test_seed.py`

- [ ] **Step 1: Failing tests**: `test_seed_demo_adds_the_economic_dashboard_to_an_older_demo_database` (delete economic rows, `people`, and the `economic` grants/enablement; `seed_demo()` → True then False; projects and environment counts unchanged), `test_seeded_economic_summary_has_actors_people_and_assignments` (viewer: ≥ 10 actors, ≥ 10 people, both `with_assignments` > 0 and below total, both tool tables non-empty), `test_seeded_economic_data_stays_inside_noetinger`; update the dashboards list in `test_seeded_accounts_can_sign_in_with_their_roles` and the environment "older database" tests so they still isolate the environment step.
- [ ] **Step 2: Run** `uv run pytest tests/test_seed.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `_seed_economic(today) -> bool` like `_seed_environment`; `seed_demo` runs both additive steps and returns whether any changed something.
- [ ] **Step 4: Run** backend checks; then `uv run alembic upgrade head && uv run gobernar360 seed-demo` on the dev database — Expected: pass; the demo gains the dashboard.
- [ ] **Step 5: Commit** `feat: seed demo data for the economic dashboard`.

### Task 6: Web — module scaffold, parameters and tools

**Files:**
- Create: `frontend/src/dashboards/economic/{api.ts,types.ts,routes.tsx,ParametersPage.tsx,ToolForm.tsx,testData.ts,testRender.tsx,routes.test.tsx,ParametersPage.test.tsx}`, `frontend/src/platform/{YearSelect.tsx,CountBarChart.tsx,Pager.tsx}`
- Modify: `frontend/src/dashboards/registry.ts`, `frontend/src/dashboards/projects/CountBarChart.tsx` (thin wrapper over the platform one, same props), `frontend/src/locales/es-AR.json`

**Interfaces (produced):** `api.ts` exports `BASE`, `BASE_PATH`, `useGet`-based hooks (`useActorTypes`, `useSectors`, `useToolCategories`, `useToolSubcategories`, `useTools`, …), `useAction`, `send`. `platform/CountBarChart({title, rows, valueLabel})`, `platform/YearSelect({value, onChange})`, `platform/Pager({total, limit, offset, onChange})`. Tabs: `summary`, `actors`, `people`, `assignments`, `reports`, `parameters` (admin only). Pages of later tasks are placeholders returning `null` until then.

- [ ] **Step 1: Failing tests**: `routes.test.tsx` (viewer sees no parameters tab; admin does; an editor typing `/d/economic/parameters` gets the forbidden notice; the dashboard is in the navigation), `ParametersPage.test.tsx` (lists the four catalogs; adds an actor type; adds a subcategory under a category; creates a tool — body `{category_id, subcategory_id: null, name, description, audience}`; edits a tool; `in_use` message on delete; load error).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/economic` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** frontend checks — Expected: all pass (projects tests unchanged).
- [ ] **Step 5: Commit** `feat: add the economic dashboard shell with parameters and tools`.

### Task 7: Web — actors and people

**Files:** Create `ActorsPage.tsx`, `ActorForm.tsx`, `ActorDetailPage.tsx`, `PeoplePage.tsx`, `PersonForm.tsx`, `PersonDetailPage.tsx`, `AssignmentForm.tsx`, `AssignmentsPanel.tsx` and their tests in `frontend/src/dashboards/economic/`; modify `routes.tsx`, locale.

**Interfaces:** `AssignmentsPanel({target: {actor_id} | {person_id}, audience: 'actors' | 'people', canEdit})` lists that target's assignments and adds one through `AssignmentForm` (tools filtered to the audience).

- [ ] **Step 1: Failing tests**: actors list (rows, search sends `q`, type filter, next page sends `offset=50`, viewer has no create button); actor form (create body with CUIT and `employee_count`, edit); actor detail (fields, linked people, link a person found by search with a role, unlink, add an assignment — body `{tool_id, actor_id, date, note}`, only tools for actors offered, delete with confirm navigates back); people list; person form (DNI lookup on blur prefills the registry data and shows the notice; an already incorporated DNI shows the link instead of saving; create body nested under `person`); person detail (edit, assignment for a person).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/economic` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** frontend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add actors and people screens to the economic dashboard`.

### Task 8: Web — summary, assignments, reports; end-to-end; README

**Files:** Create `SummaryPage.tsx`, `AssignmentsPage.tsx`, `ReportsPage.tsx` and tests, `frontend/e2e/economic.spec.ts`; modify `routes.tsx`, locale (including `overview.indicators.economic.*`), `README.md`.

- [ ] **Step 1: Failing tests**: summary (four cards, both tool tables, year change refetches, empty state with the links to load data, download links); assignments (rows for actor and person, tool filter, delete, CSV link with the year); reports (five charts with their rows as tables, untyped actors labelled, month names).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/economic` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** frontend checks — Expected: all pass.
- [ ] **Step 5: e2e** `economic.spec.ts`: editor registers an actor, adds a person by DNI, links them, assigns a tool and the summary counts it; viewer reads but has no write controls and the API answers 403; admin adds a tool that then appears in the assignment form; the second municipality sees nothing of the first; overview shows the economic indicators; CSV download. Run `npm run e2e` — Expected: all specs pass.
- [ ] **Step 6: README** — add the dashboard and the people registry.
- [ ] **Step 7: Commit** `feat: add economic summary, assignments and reports screens`.
