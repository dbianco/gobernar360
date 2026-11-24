# Complaints Dashboard Implementation Plan

**Goal:** A sixth dashboard, `complaints` ("Reclamos"): every complaint a resident makes, followed from reception until it is solved, with a business-day service clock, area queues and analysis.

**Architecture:** A module under `backend/src/gobernar360/dashboards/complaints/` whose core is two pure modules, `lifecycle.py` (states and allowed moves) and `clock.py` (calendar and clock reading), plus `cases.py` (calendar loading, readings, numbering, timeline entries), routers, `summary.py` and `export.py`. The clock is always computed on read from the timeline. A folder `frontend/src/dashboards/complaints/` mirrors it. The platform gains only a `Now` dependency and two error codes.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest; React 19, Mantine 9, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-23-complaints-dashboard-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Tables `complaints_*` with `TenantMixin` and `enable_tenant_rls`; body ids through `tenant_crud.resolve` (422 `invalid_reference`), path ids through `get_or_404`; writes through `tenant_crud` plus `cases.add_event` for the timeline.
- Register the module in `main.py`, `migrations/env.py`, both `.importlinter` contracts and the frontend registry (icon `IconMessageReport`).
- Levels: viewer reads and downloads; editor registers, moves, reassigns, corrects and comments; admin manages areas, zones, types and calendar.
- Every change is stamped with `Now`; there is no way to date a step back.

## Review Focus

- Every pair of states outside `TRANSITIONS` → 409 `invalid_transition`, state and timeline unchanged.
- Clock: day of reception not counted; weekends, holidays and waiting days excluded; reopening counts the wrongly-resolved days.
- Ids of another municipality (type, zone, area, person) → 422; its complaints → 404; its data never listed.
- The median per type in the cases CSV equals the summary's.

---

### Task 1: Lifecycle and clock (pure)

**Files:** `lifecycle.py`, `clock.py`, `stats.py`, `tests/complaints/test_clock.py`.

- [x] Calendar counting with weekdays and holidays, `add_business_days`, `read_clock` with waiting, resolution, rejection and reopening; status on time / at risk / overdue; percentiles like PERCENTILE.INC.

### Task 2: Module, catalogs, migration

**Files:** `__init__`, `access`, `models`, `schemas`, `parameters_router`, `migrations/versions/0010_complaints.py`, `tests/complaints/{factories,test_parameters}.py`; modify `main.py`, `env.py`, `.importlinter`.

- [x] Areas and zones (named catalogs), types (area, target 1–365, vigente), working weekdays and holidays; in-use deletes → 409; other municipalities' catalogs invisible and untouchable.

### Task 3: Cases, lifecycle API and queues

**Files:** `cases.py`, `complaints_router.py`, `tests/complaints/{test_lifecycle,test_complaints}.py`.

- [x] Create (registry person by id, new person, or anonymous), list with filters (including clock status), detail with `moves` and timeline, transitions, reassignment, retyping, notes, `GET /queues`, `GET /queues/{area_id}`, `GET /people/lookup`.

### Task 4: Analysis, exports, overview

**Files:** `summary.py`, `export.py`, `tests/complaints/{test_summary,test_export}.py`, `tests/platform/test_clock.py`.

- [x] Backlog today (state, status, ageing); period totals, monthly flow, by type and area, repeated, top zones and types; `complaints.csv`, `areas.csv`; four overview indicators.

### Task 5: Demo data

**Files:** `seed_complaints.py`; modify `seed.py`, `tests/test_seed.py`.

- [x] Several hundred simulated complaints for Noetinger over twelve months (not enabled there), the commune enabled with four of its own, idempotent on older demo databases.

### Task 6: Screens

**Files:** `frontend/src/dashboards/complaints/*`; modify `registry.ts`, `es-AR.json`.

- [x] Summary (status strip, period, downloads), list and form with document lookup, complaint page with clock, valid moves only and timeline, queues, parameters; component tests.

### Task 7: End to end and docs

**Files:** `frontend/e2e/complaints.spec.ts`; modify `README.md`, `CLAUDE.md`.

- [x] Operator enables the dashboard; a complaint for a registry person reaches its queue and goes from received to closed with a wait that costs no time; CSV median matches; viewer read-only; the commune sees nothing of Noetinger.
