# Environment Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the environment dashboard ("Tablero de Gestión Ambiental"): municipality-defined variables in seven fixed categories, values per period, summary against targets, tracking chart, CSV export and overview indicators.

**Architecture:** A second dashboard module, `gobernar360.dashboards.environment` (backend) and `src/dashboards/environment` (frontend), following the projects module's contract. Helpers that two dashboards now need move from the projects module to `platform`.

**Tech Stack:** unchanged (FastAPI, SQLAlchemy 2, Alembic, PostgreSQL RLS; React, TanStack Query, Mantine, Recharts).

**Spec:** `docs/superpowers/specs/2026-11-18-environment-dashboard-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Dashboard key `environment`; tables prefixed `environment_`; every table tenant-scoped with forced RLS.
- Dashboard modules never import each other (backend `lint-imports`; frontend by convention).
- Routes flush, never commit; every body-referenced id goes through `resolve()`.
- Tests hit the real `gobernar360_test` database; no mocks in the backend.
- Access: viewer reads and downloads, editor also writes values, admin also manages subcategories and variables.
- One commit per task, on `main`, not pushed.

## Review Focus

1. A value whose period does not match the variable's frequency (month on an annual variable, period 0 on a monthly one) — rejected with 422.
2. A value or variable referencing another municipality's variable/subcategory — 422 `invalid_reference`, and never readable.
3. Compliance with zero or missing numbers: target 0, value 0, no values — no division error, `null` where undefined.
4. A year far outside the supported range in a query string — 422, not 500.
5. Clearing a cell in the entry grid deletes the value instead of storing 0.

---

### Task 1: Shared groundwork

**Files:**
- Create: `backend/src/gobernar360/platform/api_types.py`, `backend/src/gobernar360/platform/csv_export.py`
- Modify: `backend/src/gobernar360/dashboards/projects/{schemas,export}.py`, `backend/src/gobernar360/platform/admin_router.py`
- Move: `frontend/src/dashboards/projects/EditableList.tsx` → `frontend/src/platform/EditableList.tsx`
- Test: `backend/tests/platform/test_admin_users.py`

**Interfaces — Produces:**
- `platform.api_types`: `Name`, `Year`, `OrmModel`, `PatchModel` (moved unchanged; `projects.schemas` re-imports them).
- `platform.csv_export`: `safe_text(value) -> str`, `plain_number(value: Decimal | None) -> str`, `csv_response(filename, header, rows) -> Response`.
- `MemberOut.grants` lists only dashboards currently enabled for the municipality.
- `platform/EditableList.tsx` with texts under `app.list.{empty,renameNamed,deleteNamed}`.

- [ ] Write `test_member_grants_of_a_disabled_dashboard_are_hidden_and_do_not_block_edits`: member with grants on `projects` and `demo`; `demo` is disabled; `GET /admin/users` omits `demo`; `PATCH` with the listed grants returns 200.
- [ ] Run it: FAIL (grants include `demo`).
- [ ] Filter grants in `_out` by `enabled_dashboard_keys`.
- [ ] Move the shared types, CSV helpers and `EditableList`; update imports and locale keys.
- [ ] Run backend suite, `lint-imports`, ruff, frontend tests, tsc, oxlint: all green.
- [ ] Commit `refactor: share dashboard helpers and hide grants of disabled dashboards`.

### Task 2: Environment module — tables, subcategories and variables

**Files:**
- Create: `backend/src/gobernar360/dashboards/environment/{__init__,access,models,schemas,parameters_router}.py`, `backend/migrations/versions/0003_environment.py`
- Modify: `backend/src/gobernar360/main.py`, `backend/.importlinter`
- Test: `backend/tests/environment/{__init__,factories,test_parameters,test_isolation}.py`

**Interfaces — Produces:**
- `KEY = "environment"`; `Viewer`, `Editor`, `Admin` dependencies.
- `CATEGORIES = ("energy","waste","water","air","mobility","biodiversity","governance")`.
- Models `Subcategory(category, name)`, `Variable(subcategory_id, name, unit, frequency, target, direction, source, annual_aggregation)`, `Value(variable_id, year, period, value)` with unique `(variable_id, year, period)`, check `period BETWEEN 0 AND 12`; `Variable.subcategory` joined; FKs `RESTRICT`.
- Routes: `GET /subcategories?category=`, `POST /subcategories {category,name}`, `PATCH /subcategories/{id} {name}`, `DELETE`; `GET /variables?category=&subcategory_id=`, `POST /variables`, `PATCH /variables/{id}` (no `frequency`; unknown fields rejected), `DELETE`.
- `VariableOut`: `id, name, unit, frequency, target (float|null), direction, source, annual_aggregation, subcategory {id, name, category}`.
- Test factories: `environment_member(level, ...)`, `make_subcategory`, `make_variable`, `make_value`.

Tests (names): admin creates subcategory and variable; unknown category rejected; editor cannot change parameters; viewer lists; member without grant gets 403; another municipality's parameters are not listed nor editable (404); variable cannot reference a foreign subcategory (422 `invalid_reference`); deleting a subcategory with variables or a variable with values returns `in_use`; frequency cannot be patched (422); parameter change is audited; every `environment_` table has forced RLS and a `tenant_isolation` policy.

- [ ] Write tests and factories; run: FAIL (404 routes / import errors).
- [ ] Implement models, autogenerate migration `0003` and add `enable_tenant_rls` for a literal table list, schemas, router, registration, import-linter entries.
- [ ] Run backend suite and linters: green.
- [ ] Commit `feat: add environment dashboard parameters`.

### Task 3: Values, rules, summary, series, export and overview

**Files:**
- Create: `backend/src/gobernar360/dashboards/environment/{rules,values_router,summary,export}.py`
- Modify: `environment/__init__.py`, `environment/schemas.py`
- Test: `backend/tests/environment/{test_rules,test_values,test_summary,test_export}.py`, `backend/tests/platform/test_overview.py`

**Interfaces — Produces:**
- `rules.annual_value(aggregation: str, values_by_period: Mapping[int, Decimal]) -> Decimal | None`
- `rules.achievement(direction, value, target) -> float | None` (ratio; 1.0 = target reached)
- `rules.target_met(direction, value, target) -> bool | None`
- `rules.expected_loads(frequency) -> int` (12 or 1)
- `GET /values?year=&variable_id=` → `[{variable_id, year, period, value}]`
- `PUT /values {variable_id, year, period, value|null}` (editor) → 200 with the stored value, 204 when cleared.
- `GET /summary?year=` (default: current year) → `{year, variable_count, loaded, expected, targets_met, targets_missed, categories: [{category, loaded, expected, variables: [{variable: VariableOut, value, loaded, expected, achievement, target_met}]}]}`; all seven categories always present.
- `GET /variables/{id}/series?year=` → `{variable, year, monthly: [{period, value|null} × 12], annual: [{year, value, loaded, expected}]}` (`monthly` empty for annual variables).
- `GET /export/values.csv?year=` → columns `category, subcategory, variable, unit, frequency, year, period, value`.
- `summary.get_summary(ctx, today)` → indicators `environment.variables`, `environment.load_completion` (ratio), `environment.targets_met`, `environment.targets_missed`; empty list when there are no variables.

Rule tests: sum / average / last (last = highest loaded period); no values → `None`; achievement higher-is-better 150/200 → 0.75; lower-is-better target 80 value 100 → 0.8; lower-is-better value 0 → 1.0; higher-is-better target 0 → `None`; `target_met` for both directions and `None` without target or value.

API tests: editor upserts and replaces a value; null clears it; viewer gets 403; period/frequency mismatch 422; period 13 and year 99999 → 422; foreign variable → 422 `invalid_reference`; values of another municipality are not listed; summary numbers for a known data set; summary lists all categories when empty; series for monthly and annual variables; series of a foreign variable 404; CSV has the BOM, the rows of the year and neutralises formulas; overview includes the environment indicators.

- [ ] Write rule tests; run: FAIL. Implement `rules.py`; run: PASS.
- [ ] Write API tests; run: FAIL. Implement routers; run: PASS.
- [ ] Backend suite and linters green.
- [ ] Commit `feat: add environment values, summary and export`.

### Task 4: Web — module shell, parameters and data entry

**Files:**
- Create: `frontend/src/dashboards/environment/{api.ts,types.ts,routes.tsx,ParametersPage.tsx,VariableForm.tsx,EntryPage.tsx,YearSelect.tsx,testData.ts,testRender.tsx}` and tests `routes.test.tsx`, `ParametersPage.test.tsx`, `EntryPage.test.tsx`
- Modify: `frontend/src/dashboards/registry.ts`, `frontend/src/locales/es-AR.json`

**Interfaces — Produces:**
- Registry entry `{key: 'environment', labelKey: 'environment.title', basePath: '/d/environment'}`.
- Tabs: `summary` (index), `tracking`, `entry` (editor+), `parameters` (admin).
- `api.ts`: `BASE`, `useSubcategories()`, `useVariables()`, `useValues(year)`, `useSummary(year)`, `useSeries(variableId, year)`, `useAction()`, `send()`.
- `types.ts`: `CATEGORIES`, `Subcategory`, `Variable`, `Value`, `Summary`, `Series`.
- `YearSelect({value, onChange})`: native select, current year ± range.
- Entry grid cell: `aria-label` "`{variable} — {period label}`"; saves on blur when the text changed; empty text sends `value: null`.

Tests: tabs shown per level (viewer: no entry/parameters; editor: entry; admin: all); parameters page lists subcategories per category, adds one, creates a variable with the form (request body asserted), shows load error; entry page renders 12 month cells for a monthly variable and one for an annual one, saves a changed cell with `PUT /values`, clears a cell with `value: null`, does not send when unchanged, shows an empty state without variables.

- [ ] Write tests; run: FAIL. Implement; run: PASS.
- [ ] Frontend suite, tsc, oxlint, build green.
- [ ] Commit `feat: add environment dashboard parameters and data entry screens`.

### Task 5: Web — summary, tracking and overview labels

**Files:**
- Create: `frontend/src/dashboards/environment/{SummaryPage.tsx,TrackingPage.tsx,SeriesChart.tsx}` and tests `SummaryPage.test.tsx`, `TrackingPage.test.tsx`
- Modify: `frontend/src/locales/es-AR.json`, `frontend/src/dashboards/overview/OverviewPage.test.tsx`

**Interfaces — Consumes:** `useSummary`, `useSeries`, `useVariables`, `YearSelect` from Task 4.

Summary: four stat cards (variables, loads `loaded / expected`, targets met, targets missed), download link, one section per category that has variables with a table (variable, `value / target unit`, compliance, loads), and a note naming the categories without variables.

Tracking: selects for category, subcategory, variable and year; monthly/annual toggle (annual only for annual variables); `SeriesChart` — one line, 2px, markers, target as a dashed reference line labelled "Meta", hover tooltip, table toggle; text tokens for labels.

Tests: summary shows value against target and compliance, a dash without target, the loads fraction, the categories-without-variables note, and requests the chosen year; tracking lists variables filtered by category, shows the series as a table with twelve months, switches to annual, and shows an empty state when the municipality has no variables; overview renders the environment indicator labels.

- [ ] Write tests; run: FAIL. Implement; run: PASS.
- [ ] Frontend suite, tsc, oxlint, build green.
- [ ] Commit `feat: add environment summary and tracking screens`.

### Task 6: Demo data, end-to-end test and docs

**Files:**
- Modify: `backend/src/gobernar360/seed.py`, `backend/tests/test_seed.py`, `README.md`
- Create: `frontend/e2e/environment.spec.ts`

**Interfaces — Produces:** `seed_demo()` also enables `environment` for both demo municipalities, grants it to the demo editor and viewer, and loads variables with two years of values for Noetinger. On a database that already has the demo but no environment data it adds only the environment part and returns `True`.

Tests: seed adds environment data to an already seeded database without duplicating users or projects; seeded summary has loads, a met and a missed target; seeded accounts list both dashboards. e2e: editor loads a value in the grid and the summary's loads count goes up by one; viewer sees no entry or parameters tab and a direct `PUT` is forbidden; the overview shows the environment indicators; the second municipality sees none of Noetinger's variables.

- [ ] Write seed tests; run: FAIL. Implement; run: PASS.
- [ ] Write the e2e spec; run the e2e suite: PASS.
- [ ] Update README (dashboards list, demo accounts, plan/spec links).
- [ ] Full verification: backend, frontend, e2e, linters, build.
- [ ] Commit `feat: add environment demo data and end-to-end tests`.
