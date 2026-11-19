# Social Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the Social dashboard (people, households, benefit deliveries, interventions, summary, reports, exports) on top of the people registry.

**Architecture:** `dashboards/social` mirrors `dashboards/economic`: `access.py`, `models.py`, `schemas.py`, one router per area, registered in `main.py`. A person enters through the link table `social_people`, which also holds their household and relationship; deliveries and interventions point at that link. The description of an intervention is returned only to editor level and above. The web gets `frontend/src/dashboards/social/`; the person form with the DNI lookup moves to `frontend/src/platform/people/` so both dashboards share it.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest against `gobernar360_test`; React + Mantine + TanStack Query + Recharts, Vitest + MSW, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-19-social-dashboard-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Routes flush, never commit. Every id taken from a request body goes through `tenant_crud.resolve`. Writes go through `tenant_crud` so they are audited.
- Every new table is tenant data: `TenantMixin`, and its migration calls `enable_tenant_rls` with a literal table list.
- Dashboard modules never import each other, on the backend (`social` is added to both contracts of `backend/.importlinter`) or on the web.
- Lists of people, households, deliveries and interventions answer `{items, total}` and take `limit` (default 50, max 200) and `offset`.
- One local commit per task on `main`; never push. Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Backend checks: `uv run ruff format -q . && uv run ruff check . && uv run lint-imports && uv run pytest -q`. Frontend checks: `npx tsc -b && npm run lint && npm test -- --run`.

## Review Focus

- A viewer never receives an intervention's description: list, list filtered by person or household, CSV. A municipality admin without an explicit grant does receive it.
- A person present in `people` or in `economic_people` but not in `social_people`: never listed, 404 by id, 422 as `person_id`, found only by exact DNI lookup.
- Ids of another municipality in any body or path (`category_id`, `benefit_id`, `intervention_type_id`, `person_id`, household member): 422 `invalid_reference` or 404, nothing written.
- Household rules: a second head (409 `household_has_head`), a person already in another household (409 `in_another_household`), deleting a household frees its members, removing a person from the dashboard leaves the household consistent.
- Delivery quantity 0 or negative, and a delivery or intervention PATCH that tries to change the person, benefit or type: 422.

---

### Task 1: Social module — tables and catalogs

**Files:**
- Create: `backend/src/gobernar360/dashboards/social/{__init__,access,models,schemas,parameters_router}.py`, `backend/migrations/versions/0007_social.py`, `backend/tests/social/{__init__,factories,test_parameters}.py`
- Modify: `backend/src/gobernar360/main.py`, `backend/migrations/env.py`, `backend/.importlinter`

**Interfaces (produced):**
- `KEY = "social"`; `Viewer`, `Editor`, `Admin`; `access.reads_reserved_text(ctx) -> bool` (effective level ≥ editor).
- Models: `BenefitCategory` (`social_benefit_categories`: `name`); `Benefit` (`social_benefits`: `category_id`, `name`, `description`); `InterventionType` (`social_intervention_types`: `name`); `Household` (`social_households`: `name`, `address` 200, `neighborhood` 100); `SocialPerson` (`social_people`: `person_id` → `people.id` unique, `household_id?` → `social_households.id`, `relationship?` ∈ `RELATIONSHIPS = ("head", "partner", "child", "parent", "sibling", "grandparent", "grandchild", "other_relative", "non_relative")`; check `(household_id IS NULL) = (relationship IS NULL)`; partial unique index on `household_id` where `relationship = 'head'`); `Delivery` (`social_deliveries`: `benefit_id`, `person_id` → `social_people.id`, `date`, `quantity` ≥ 1, `note`); `Intervention` (`social_interventions`: `intervention_type_id`, `person_id` → `social_people.id`, `date`, `description`, `performed_by` 200). Every foreign key RESTRICT.
- API under `/api/dashboards/social`: name catalogs `/benefit-categories` and `/intervention-types` (`GET/POST`, `PATCH/DELETE /{id}`); `/benefits` with `BenefitIn(category_id, name, description="")`, `BenefitPatch`, `BenefitOut(id, name, description, category: NamedRef)`. Reads: Viewer; writes: Admin.
- Test factories: `social_member(level, email, municipality)`, `make_benefit_category`, `make_benefit`, `make_intervention_type`, `make_household`, `make_person` (registry row), `make_social_person(municipality, first_name, last_name, household=None, relationship=None, **fields)`, `make_delivery`, `make_intervention`.

- [ ] **Step 1: Failing tests** (`test_parameters.py`): `test_dashboard_admin_manages_each_catalog` (parametrised over the two name catalogs), `test_benefit_is_created_listed_and_updated`, `test_benefit_cannot_reference_a_category_of_another_municipality` (422 `invalid_reference`), `test_editor_cannot_change_parameters` (403), `test_viewer_lists_parameters`, `test_member_without_grant_is_rejected`, `test_parameters_of_another_municipality_are_not_listed_nor_editable`, `test_deleting_a_category_in_use_returns_in_use`, `test_parameter_change_is_audited`, `test_every_social_table_enforces_tenant_isolation` (the seven `social_*` tables).
- [ ] **Step 2: Run** `uv run pytest tests/social -q` — Expected: FAIL (import error).
- [ ] **Step 3: Implement**; migration via `uv run alembic revision --autogenerate --rev-id 0007 -m social` plus the RLS loop.
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add the social dashboard module with its catalogs`.

### Task 2: People and households

**Files:**
- Create: `backend/src/gobernar360/dashboards/social/{people_router,households_router}.py`, `backend/tests/social/{test_people,test_households}.py`
- Modify: `dashboards/social/__init__.py`, `schemas.py`, `core/errors.py` (`household_has_head()`, `in_another_household()`, both 409 with those codes)

**Interfaces (produced):**
- `GET /people?q&neighborhood` → `Page[SocialPersonOut]` (`{id, person: PersonOut, household: NamedRef | None, relationship: str | None}`), ordered by last name, first name; `GET /people/lookup?dni=` (Editor) → `{person, registered_id}`; `POST /people {person: PersonIn}`; `GET /people/{id}`; `PATCH /people/{id} {person: PersonPatch}`; `DELETE /people/{id}` (then `release_person`).
- `GET /households?q` → `Page[HouseholdOut]` (`{id, name, address, neighborhood, member_count, head: PersonRef | None}`), ordered by name; `POST /households {name, address="", neighborhood=""}`; `GET /households/{id}` → `HouseholdDetail` (`members: [{id, full_name, dni, relationship}]`, head first, then by name); `PATCH`; `DELETE` (members are freed first, each change audited); `PUT /households/{id}/members/{person_id} {relationship}` → `HouseholdDetail` (adds the person or changes their relationship); `DELETE /households/{id}/members/{person_id}` → 204. Writes: Editor.

- [ ] **Step 1: Failing tests.** `test_people.py`: create new; create reusing a registry person by DNI (registry count stays 1); a person incorporated by Economic is reused and stays in Economic; already incorporated 409 `already_registered`; lookup (unknown / registry only / incorporated; viewer 403; malformed 422); registry-only person not listed and 404 by its registry id; search by last name without accents and by DNI; neighborhood filter; patch common fields; patch DNI to one in use 409; delete releases the registry row; delete keeps the registry row while Economic uses the person; other municipality 404; viewer cannot write; pagination bounds. `test_households.py`: create, list with `member_count` and head, search by name and address, detail order, add member, change relationship, second head 409 `household_has_head`, member of another household 409 `in_another_household`, re-adding the same member with a new relationship is an update, person of another municipality 404, remove member, delete frees members and keeps the people, patch, viewer cannot write, other municipality 404, audit rows for membership changes.
- [ ] **Step 2: Run** `uv run pytest tests/social -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: register social people and households`.

### Task 3: Deliveries and interventions

**Files:**
- Create: `backend/src/gobernar360/dashboards/social/{deliveries_router,interventions_router}.py`, `backend/tests/social/{test_deliveries,test_interventions}.py`
- Modify: `dashboards/social/__init__.py`, `schemas.py`

**Interfaces (produced):**
- `GET /deliveries?year&benefit_id&category_id&person_id&household_id` → `Page[DeliveryOut]` (`{id, date, quantity, note, benefit: {id, name, category: NamedRef}, person: PersonRef}`), newest first; `POST /deliveries {benefit_id, person_id, date, quantity=1, note=""}`; `PATCH /deliveries/{id} {date?, quantity?, note?}` (`extra="forbid"`); `DELETE`. `deliveries_router.in_year(year)`.
- `GET /interventions?year&intervention_type_id&person_id&household_id` → `Page[InterventionOut]` (`{id, date, intervention_type: NamedRef, person: PersonRef, performed_by, description: str | None}`), newest first; `description` is `None` unless `reads_reserved_text(ctx)`; `POST /interventions {intervention_type_id, person_id, date, description="", performed_by=""}`; `PATCH /interventions/{id} {date?, description?, performed_by?}` (`extra="forbid"`); `DELETE`. `interventions_router.in_year(year)`.

- [ ] **Step 1: Failing tests**: delivery create with default quantity; quantity 0 and -1 → 422; foreign benefit/person 422; `person_id` of a registry-only person 422; filters by year, benefit, category, person and household; patch date, quantity and note; patch `person_id` → 422; delete; deleting a benefit or a person with deliveries → 409 `in_use`; viewer cannot write. Interventions: create; editor reads the description; viewer gets `description: null` in the list and when filtering by person and household; a municipality admin without a grant reads it; filters; patch; patch `person_id` 422; delete; deleting a type or a person in use → 409; viewer cannot write; other municipality's rows invisible.
- [ ] **Step 2: Run** `uv run pytest tests/social -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: record social benefit deliveries and interventions`.

### Task 4: Summary, reports, exports, overview

**Files:**
- Create: `backend/src/gobernar360/dashboards/social/{summary,export}.py`, `backend/tests/social/{test_summary,test_export}.py`
- Modify: `dashboards/social/__init__.py`, `schemas.py`, `backend/tests/platform/test_overview.py`

**Interfaces (produced):**
- `GET /summary?year` → `{year, people, households, people_with_deliveries, deliveries, units, interventions, people_with_interventions, benefits: [{benefit, category, deliveries, units}], intervention_types: [{name, count}]}` (tables sorted by count desc, then name).
- `GET /reports?year` → `{year, deliveries_by_category, interventions_by_type, people_by_neighborhood, deliveries_by_neighborhood: [{name, count}], deliveries_by_month, interventions_by_month: [{month, count}]}` (twelve months; blank neighborhood under `name: null`).
- `GET /export/people.csv` (`last_name, first_name, dni, birth_date, phone, email, address, neighborhood, household, relationship`), `/export/households.csv` (`name, address, neighborhood, members, head`), `/export/deliveries.csv?year` (`date, benefit, category, quantity, person, document, household, note`), `/export/interventions.csv?year` (`date, type, person, document, performed_by` plus `description` only for editor level and above).
- `get_summary(ctx, today)` → `social.people`, `social.households`, `social.deliveries_year`, `social.interventions_year`; `[]` when all four are zero.

- [ ] **Step 1: Failing tests**: summary counts (distinct people of the year, units summed, last year excluded); empty summary; reports buckets including the blank neighborhood and all twelve months; each export (header, rows, formula neutralisation, other municipality excluded, 403 without access); the interventions export has no `description` column for a viewer and has it for an editor; overview indicators and empty overview.
- [ ] **Step 2: Run** `uv run pytest tests/social tests/platform/test_overview.py -q` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** backend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add social summary, reports and exports`.

### Task 5: Demo data

**Files:** Modify `backend/src/gobernar360/seed.py`, `backend/tests/test_seed.py`

- [ ] **Step 1: Failing tests**: `test_seed_demo_adds_the_social_dashboard_to_an_older_demo_database` (delete social rows and the `social` grants/enablement; `seed_demo()` → True then False; other dashboards' counts unchanged), `test_seeded_social_summary_has_people_households_and_records` (≥ 12 people, ≥ 4 households, deliveries and interventions > 0, both tables non-empty), `test_seeded_social_people_share_the_registry_with_economic` (at least two `people` rows referenced by both link tables; no duplicated DNI), `test_seeded_social_data_stays_inside_noetinger`; update the dashboards list in the sign-in test.
- [ ] **Step 2: Run** `uv run pytest tests/test_seed.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `_seed_noetinger_social(municipality_id, today)` registered in `_seed_newer_dashboards`; a seeded person whose DNI is already in the registry reuses that row.
- [ ] **Step 4: Run** backend checks; then `uv run alembic upgrade head && uv run gobernar360 seed-demo` on the dev database — Expected: pass; the demo gains the dashboard.
- [ ] **Step 5: Commit** `feat: seed demo data for the social dashboard`.

### Task 6: Web — shared person form, module scaffold, parameters

**Files:**
- Create: `frontend/src/platform/people/{RegistryPersonForm.tsx,types.ts}`, `frontend/src/platform/Field.tsx`, `frontend/src/dashboards/social/{api.ts,types.ts,routes.tsx,ParametersPage.tsx,testData.ts,testRender.tsx,routes.test.tsx,ParametersPage.test.tsx}`
- Modify: `frontend/src/dashboards/economic/PersonForm.tsx` (wraps the shared form; same behaviour), `economic/types.ts`, `economic/Field.tsx` and `economic/format.ts` (re-export from the platform), `frontend/src/platform/format.ts` (`formatDni`, `todayIso`), `frontend/src/dashboards/registry.ts`, `frontend/src/locales/es-AR.json`

**Interfaces (produced):** `RegistryPersonForm({person?, lookup, existingPath, save, action, onDone, children?})` — `lookup(dni) => Promise<Lookup>`, `existingPath(registeredId) => string`, `save(personBody) => Promise<unknown>` run through `action`, `children` are the dashboard's own fields. Its copy lives under `people.*` in the locale. `social/api.ts` exports `BASE`, `BASE_PATH`, `PAGE_SIZE`, hooks, `useAction`, `send`, `get`. Tabs: `summary`, `people`, `households`, `deliveries`, `interventions`, `reports`, `parameters` (admin only).

- [ ] **Step 1: Failing tests**: `routes.test.tsx` (viewer sees no parameters tab; admin does; an editor typing `/d/social/parameters` gets the forbidden notice; the dashboard is in the navigation), `ParametersPage.test.tsx` (lists the three catalogs; adds an intervention type; creates a benefit — body `{category_id, name, description}`; edits a benefit; `in_use` message on delete; load error).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/social` — Expected: FAIL.
- [ ] **Step 3: Implement**; the economic people tests keep passing unchanged except for locale key names.
- [ ] **Step 4: Run** frontend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add the social dashboard shell with its catalogs`.

### Task 7: Web — people, households and their records

**Files:** Create `PeoplePage.tsx`, `PersonForm.tsx`, `PersonDetailPage.tsx`, `HouseholdsPage.tsx`, `HouseholdForm.tsx`, `HouseholdDetailPage.tsx`, `DeliveryForm.tsx`, `InterventionForm.tsx`, `RecordsPanel.tsx` and tests in `frontend/src/dashboards/social/`; modify `routes.tsx`, locale.

**Interfaces:** `RecordsPanel({scope: {person_id} | {household_id}, canEdit})` shows the deliveries and the interventions of that person or household; adding is offered only for a person. `DeliveryForm({personId?, delivery?, onDone})` and `InterventionForm({personId?, intervention?, onDone})` — without `personId` they ask for the person with a search box.

- [ ] **Step 1: Failing tests**: people list (rows with household, search sends `q`, neighborhood filter, next page sends `offset=50`, viewer has no create button); person form (DNI lookup prefills and shows the notice; create body `{person: {...}}`); person detail (fields, household link, add a delivery — body `{benefit_id, person_id, date, quantity, note}`; add an intervention; a viewer sees "Reservado" instead of the description and no write controls; delete navigates back); households list and create; household detail (members with relationship, add a member found by search, change relationship, remove, records of all members without add buttons, delete).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/social` — Expected: new tests FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** frontend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add people and household screens to the social dashboard`.

### Task 8: Web — deliveries, interventions, summary, reports; end-to-end; README

**Files:** Create `DeliveriesPage.tsx`, `InterventionsPage.tsx`, `SummaryPage.tsx`, `ReportsPage.tsx` and tests, `frontend/e2e/social.spec.ts`; modify `routes.tsx`, locale (including `overview.indicators.social.*`), `README.md`.

- [ ] **Step 1: Failing tests**: deliveries (rows, benefit filter, year change, add choosing a person by search, delete, CSV link with the year); interventions (rows, type filter, reserved text for a viewer, add, CSV link); summary (cards, both tables, year change refetches, empty state, download links); reports (six charts with their rows, blank neighborhood labelled, month names).
- [ ] **Step 2: Run** `npm test -- --run src/dashboards/social` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** frontend checks — Expected: all pass.
- [ ] **Step 5: e2e** `social.spec.ts`: editor adds a person by DNI, creates a household and adds them as head, records a delivery and an intervention and the summary counts them; a person loaded in Economic is offered by the DNI lookup; viewer reads but sees the description reserved, has no write controls and the API answers 403; the second municipality sees nothing of the first; overview shows the social indicators; CSV download. Run `npm run e2e` — Expected: all specs pass.
- [ ] **Step 6: README** — add the dashboard.
- [ ] **Step 7: Commit** `feat: add social deliveries, interventions, summary and reports screens`.
