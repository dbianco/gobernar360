# Procedures Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A fifth dashboard, `procedures` ("Trámites"): an inventory of the municipality's procedures, their requirements and the source of each, with an interoperability-opportunities report.

**Architecture:** Same shape as the economic dashboard: a module under `backend/src/gobernar360/dashboards/procedures/` (catalog router, procedures router, summary, export) and a folder under `frontend/src/dashboards/procedures/`. No personal data and no time dimension. Status light, icon and header help come from the platform.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest; React 19, Mantine 9, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-20-procedures-dashboard-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Tables `procedures_*` with `TenantMixin` + `AuditMixin` and `enable_tenant_rls`; body ids via `tenant_crud.resolve` (422 `invalid_reference`), path ids via `get_or_404`; writes through `tenant_crud`.
- Register the module in `main.py`, `migrations/env.py`, both `.importlinter` contracts, the frontend registry (icon `IconFileText`).
- Levels: viewer reads and downloads; editor writes procedures and requirements; admin writes areas and sources.
- Enumerations: source level `municipal|provincial|national|other`; audience `people|organizations|both`; channel `in_person|online|both`; requirement format `paper|digital`.
- Only active procedures count in summary, opportunities and overview.
- Every named table header uses `<HelpTh>`; the summary starts with `<StatusStrip>` with `onYearChange`.

## Review Focus

- A requirement, source or area id of another municipality in a body → 422, never linked.
- A procedure that asks two requirements of the same source counts once in that source's procedures and annual volume.
- Inactive procedures are excluded from every count, including "top requirements".
- A requirement link addressed through another procedure's path → 404.
- Free procedure sent with a cost; non-municipal source sent with an area → 422.

---

### Task 1: Module, catalogs and migration

**Files:** create `dashboards/procedures/{__init__,access,models,schemas,catalog_router}.py`, `migrations/versions/0009_procedures.py`, `tests/procedures/{__init__,factories,test_catalog}.py`; modify `main.py`, `migrations/env.py`, `.importlinter`.

**Interfaces — produces:**
- Models `Area(name)`, `Source(name, level, area_id?)`, `Requirement(name, description, source_id?)`, `Procedure(name, description, area_id, audience, channel, url, is_free, cost?, duration_days?, annual_volume?, is_active)`, `ProcedureRequirement(procedure_id CASCADE, requirement_id RESTRICT, mandatory, format, note)` unique `(procedure_id, requirement_id)`.
- `GET/POST /areas`, `PATCH/DELETE /areas/{id}` (admin writes) → `{id, name}`.
- `GET/POST /sources`, `PATCH/DELETE /sources/{id}` (admin writes) → `{id, name, level, area: {id,name}|null}`.
- `GET/POST /requirements`, `PATCH/DELETE /requirements/{id}` (editor writes) → `{id, name, description, source: SourceOut|null, procedure_count}`; list ordered by name, optional `q`.
- Test factories `procedures_member(level)`, `make_area`, `make_source`, `make_requirement`, `make_procedure`, `link_requirement`.

- [ ] Write failing tests: CRUD per catalog and level (viewer reads, editor cannot write areas/sources, editor writes requirements, admin writes all); source with area but not municipal → 422; ids of another municipality → 422; delete in use → 409 `in_use`; `procedure_count` counts every procedure using it; other municipality's rows invisible; audit entry on create.
- [ ] Run `uv run pytest tests/procedures -q` — Expected: FAIL.
- [ ] Implement; autogenerate migration `--rev-id 0009`, hand-edit header, RLS loop.
- [ ] Run `uv run pytest tests/procedures -q && uv run lint-imports` — Expected: PASS.
- [ ] Commit `feat: procedures dashboard module and catalogs`.

### Task 2: Procedures and their requirements

**Files:** create `dashboards/procedures/procedures_router.py`, `tests/procedures/test_procedures.py`; modify `__init__.py`, `schemas.py`.

**Interfaces — produces:**
- `GET /procedures?q&area_id&channel&active&limit&offset` → `Page[ProcedureOut]`; `ProcedureOut = {id, name, description, area:{id,name}, audience, channel, url, is_free, cost, duration_days, annual_volume, is_active, requirement_count}`.
- `POST /procedures`, `GET /procedures/{id}` → `ProcedureDetail = ProcedureOut + requirements: [{id, requirement: RequirementRef{id,name,source}, mandatory, format, note}]` ordered by requirement name; `PATCH`, `DELETE`.
- `POST /procedures/{id}/requirements {requirement_id, mandatory=true, format="paper", note=""}` (409 `conflict` when already linked), `PATCH /procedures/{id}/requirements/{link_id}`, `DELETE` (404 when the link belongs to another procedure).

- [ ] Write failing tests: create with only name+area (defaults: audience both, channel in_person, free, active); every field; free with cost → 422; negative days/volume → 422; cost becomes null when patched to free; filters and accent-insensitive search; pagination total; detail lists requirements by name; link/patch/unlink; duplicate link → 409; link through another procedure → 404; foreign ids → 422; viewer cannot write; deleting a procedure removes its links; deleting a linked requirement → 409.
- [ ] Run — Expected: FAIL. Implement. Run `uv run pytest tests/procedures -q` — Expected: PASS.
- [ ] Commit `feat: procedures and their requirements`.

### Task 3: Summary, opportunities, exports and overview

**Files:** create `dashboards/procedures/{summary,export}.py`, `tests/procedures/{test_summary,test_export}.py`; modify `__init__.py`, `schemas.py`.

**Interfaces — produces:**
- `GET /summary` → `{procedures, online, average_requirements, requirements, sources, by_area:[{name,count}], by_channel:[{channel,count}], top_requirements:[{name, source, count}]}` (top 10; ties by name).
- `GET /opportunities` → `{sources:[{source: SourceOut, requirements, procedures, annual_volume}], without_source: {requirements, procedures, annual_volume}}`.
- `GET /export/{procedures,procedure-requirements,opportunities}.csv`.
- `get_summary` → `procedures.active`, `procedures.online_ratio` (unit `ratio`), `procedures.requirements`, `procedures.sources`; `[]` when the dashboard is empty.

- [ ] Write failing tests with a known data set covering each Review Focus line, CSV headers/rows, formula-safe text, viewer access, another municipality's data excluded, overview shape (with `"status": []`).
- [ ] Run — Expected: FAIL. Implement. Run `uv run pytest -q` — Expected: PASS.
- [ ] Commit `feat: procedures summary, opportunities and exports`.

### Task 4: Demo data

**Files:** modify `seed.py`, `tests/test_seed.py`.

- [ ] Write failing tests: seeded Noetinger summary has ≥10 procedures, ≥3 municipal sources in opportunities, the commune's dashboard is enabled and empty, an older demo database gains the dashboard (with its lights) once.
- [ ] Run — Expected: FAIL. Implement `_seed_noetinger_procedures`; add `PROCEDURES` to `STATUS_LIGHTS` and seed its lights when the dashboard is added. Run `uv run pytest -q && uv run ruff check . && uv run lint-imports` — Expected: PASS.
- [ ] Commit `feat: procedures demo data`.

### Task 5: Shell, parameters and requirements screens

**Files:** create `frontend/src/dashboards/procedures/{api.ts,types.ts,routes.tsx,ParametersPage.tsx,SourceForm.tsx,RequirementsPage.tsx,RequirementForm.tsx,testData.ts,testRender.tsx}` and tests; modify `registry.ts`, locale (`procedures.*`, overview indicators).

- [ ] Write failing tests: tabs by level; areas list add/rename/delete; sources table with level and area, form hides area unless municipal; requirements table with source and usage, editor adds/edits/deletes, viewer has no actions, in-use error shown.
- [ ] Run — Expected: FAIL. Implement. Run `npx vitest run` — Expected: PASS.
- [ ] Commit `feat: procedures shell, parameters and requirements screens`.

### Task 6: Procedures list and detail

**Files:** create `ProceduresPage.tsx`, `ProcedureForm.tsx`, `ProcedureDetailPage.tsx`, `RequirementLinkForm.tsx` and tests.

- [ ] Write failing tests: list with filters sent as query, pager, create; form hides cost when free; detail shows data and requirement table with source, add (only requirements not yet linked), edit, remove; viewer read-only; inactive badge.
- [ ] Run — Expected: FAIL. Implement. Run `npx vitest run` — Expected: PASS.
- [ ] Commit `feat: procedures list and detail screens`.

### Task 7: Summary and opportunities screens

**Files:** create `SummaryPage.tsx`, `OpportunitiesPage.tsx` and tests.

- [ ] Write failing tests: headline cards, charts' table data, top requirements table, empty state; opportunities table grouped by level with the without-source row and download links; status strip present with year arrows.
- [ ] Run — Expected: FAIL. Implement. Run `npx vitest run && npx tsc -b && npx oxlint` — Expected: PASS, clean.
- [ ] Commit `feat: procedures summary and opportunities screens`.

### Task 8: End to end and docs

**Files:** create `frontend/e2e/procedures.spec.ts`; modify `README.md`.

- [ ] Write the spec: editor creates a procedure, adds a requirement, sees opportunities change; viewer is read-only; admin adds a source; the other municipality sees nothing.
- [ ] Run `npx playwright test` — Expected: all PASS. Document the dashboard in `README.md`.
- [ ] Commit `test: procedures end to end; docs`.
