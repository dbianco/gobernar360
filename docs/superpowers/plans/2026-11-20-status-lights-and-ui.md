# Status Lights, Menu Icons and Column Help Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A hand-set monthly traffic light per dashboard, an icon per menu entry, a help tooltip on every dashboard table header, and a general overview with lights on top and collapsible sections.

**Architecture:** The light lives in the platform (one table, one router keyed by dashboard key), so every present and future dashboard gets it without code of its own; the overview endpoint returns each dashboard's recent lights next to its indicators. The frontend gets shared platform components (`status/`, `HelpTh`) that each dashboard's pages use.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest; React 19, Mantine 9, `@tabler/icons-react`, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-20-status-lights-and-ui-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Tenant tables use `TenantMixin` + `AuditMixin` and `enable_tenant_rls`; routes flush, never commit; writes go through `tenant_crud` so they are audited.
- Colors are exactly `green`, `yellow`, `red`. State names: green "En orden", yellow "Con atención", red "Crítico"; no light: "Sin estado".
- A light is never conveyed by color alone: the state name is always present as text or accessible name.
- The overview shows the latest set month and the set months among the 5 calendar months before it.
- One commit per task on `main`; push is not part of this plan.

## Review Focus

- A member with no access to a dashboard, or of another municipality, asks for its lights → 403 / never sees rows (RLS).
- An unknown or disabled dashboard key in the path → 403, no row written.
- Setting a month after the current one (including next year's January in December) → 422.
- Lights set for a year other than the current one do not leak into another year's strip; the overview's "previous 5 months" crosses the year boundary correctly (January → previous year's August–December).
- Two admins setting the same month at once → one row, no 500.

---

### Task 1: Status model, migration and API

**Files:**
- Create: `backend/src/gobernar360/platform/status.py`, `backend/src/gobernar360/platform/status_router.py`, `backend/migrations/versions/0008_dashboard_status.py`, `backend/tests/platform/test_status.py`
- Modify: `backend/src/gobernar360/platform/models.py`, `backend/src/gobernar360/main.py`, `backend/src/gobernar360/core/errors.py`

**Interfaces:**
- Produces: model `DashboardStatus(id, municipality_id, dashboard_key: str(50), year: int, month: int, color: str(10))`, table `dashboard_statuses`, unique `(municipality_id, dashboard_key, year, month)`, checks `month BETWEEN 1 AND 12` and `color IN ('green','yellow','red')`; `STATUS_COLORS = ("green", "yellow", "red")`.
- Produces: `status.recent(db, dashboard_key, today, previous=5) -> list[DashboardStatus]` — the latest row not after `today`'s month, then the rows within the `previous` calendar months before it, newest first; `[]` when none.
- Produces: `GET /api/dashboards/{dashboard_key}/status?year=` → `[{"month": 3, "color": "green"}]` ordered by month (viewer on that key); `PUT /api/dashboards/{dashboard_key}/status/{year}/{month}` body `{"color": "green"|"yellow"|"red"|null}` → 204 (admin on that key; `null` removes; a month after today's → 422 code `future_month`).

- [ ] **Step 1: Write the failing tests** in `tests/platform/test_status.py` (use the `demo_dashboard` fixture and `get_today` pinned to 2025-06-15):
  - `test_admin_sets_a_month_and_a_viewer_reads_it`: PUT 2025/3 green → 204; GET year=2025 → `[{"month": 3, "color": "green"}]`.
  - `test_setting_a_month_again_replaces_its_color` (one row, color red).
  - `test_null_clears_a_month` and clearing a month that has none → 204.
  - `test_viewer_and_editor_cannot_set` → 403.
  - `test_member_without_access_cannot_read` → 403; `test_unknown_dashboard_key_is_forbidden` → 403.
  - `test_a_future_month_is_rejected`: 2025/7 and 2026/1 → 422 `future_month`; 2025/6 → 204.
  - `test_invalid_color_and_month_are_rejected`: color "blue", month 13 → 422.
  - `test_lights_of_another_municipality_are_invisible`.
  - `test_other_years_are_not_listed`.
  - `test_setting_a_month_is_audited`: one `audit_log` row, entity_type `dashboard_statuses`, changes include color.
  - `test_recent_returns_latest_and_previous_five_months_across_years`: rows 2024-07, 2024-09, 2024-12, 2025-01, 2025-07 with today 2025-01-20 → months `[(2025,1),(2024,12),(2024,9)]`.
- [ ] **Step 2: Run** `uv run pytest tests/platform/test_status.py -q` — Expected: FAIL (404s / import error).
- [ ] **Step 3: Implement** the model, `status.py`, the router (level check with `effective_level(ctx.db, ctx.membership, key)`; upsert through `create_entity` / `update_entity` / `delete_entity`; on `IntegrityError` from a concurrent insert re-read and update), `errors.future_month()`, include the router in `main.py` before the dashboard modules, and migration `0008` (autogenerate with `--rev-id 0008`, hand-edit header, `enable_tenant_rls("dashboard_statuses")`).
- [ ] **Step 4: Run** `uv run pytest tests/platform -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: monthly status light per dashboard`.

### Task 2: Lights in the overview

**Files:**
- Modify: `backend/src/gobernar360/platform/overview_router.py`, `backend/tests/platform/test_overview.py`, `backend/tests/{economic,social,environment}/test_summary.py`

**Interfaces:**
- Consumes: `status.recent`.
- Produces: every `/api/overview` item gains `"status": [{"year": 2025, "month": 6, "color": "green"}, ...]` (newest first, at most 6, `[]` when none).

- [ ] **Step 1: Write the failing test** `test_overview_includes_recent_lights_newest_first` and add `"status": []` to the existing exact-equality assertions.
- [ ] **Step 2: Run** `uv run pytest tests -q -k overview` — Expected: FAIL on the missing key.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `uv run pytest -q` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: overview returns each dashboard's recent lights`.

### Task 3: Demo lights

**Files:**
- Modify: `backend/src/gobernar360/seed.py`, `backend/tests/test_seed.py`

- [ ] **Step 1: Write the failing tests**: `test_seeded_noetinger_has_lights_in_every_dashboard` (overview as admin: each of the four dashboards has 6 lights and at least two different colors overall) and `test_seed_demo_adds_lights_to_an_older_demo_database_once` (delete the rows, `seed_demo()` is True then False).
- [ ] **Step 2: Run** `uv run pytest tests/test_seed.py -q` — Expected: FAIL.
- [ ] **Step 3: Implement** `_seed_noetinger_status(municipality_id, today)`: the current month and the 5 before it for each dashboard, from a fixed color table; skipped when Noetinger already has any light. Called from `_seed_newer_dashboards`.
- [ ] **Step 4: Run** `uv run pytest -q && uv run ruff check . && uv run lint-imports` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: demo status lights`.

### Task 4: Menu icons

**Files:**
- Modify: `frontend/package.json`, `frontend/src/dashboards/registry.ts`, `frontend/src/platform/AppShell.tsx`, `frontend/src/platform/AppShell.test.tsx`

**Interfaces:**
- Produces: `DashboardEntry.icon: Icon` (type `Icon` from `@tabler/icons-react`); `dashboardIcon(key): Icon | undefined`. Icons: projects `IconBulb`, environment `IconLeaf`, economic `IconBuildingStore`, social `IconHeartHandshake`; overview `IconLayoutDashboard`, users `IconUsers`, platform `IconBuildingCommunity`.

- [ ] **Step 1: Write the failing test** `every navigation link has an icon`: each link in the navigation contains an `svg`.
- [ ] **Step 2: Run** `npx vitest run src/platform/AppShell.test.tsx` — Expected: FAIL.
- [ ] **Step 3: Implement** (`npm install @tabler/icons-react`; `leftSection` on each `NavLink`, icons `aria-hidden`).
- [ ] **Step 4: Run** the same command — Expected: PASS.
- [ ] **Step 5: Commit** `feat: menu icons`.

### Task 5: Status strip in every dashboard summary

**Files:**
- Create: `frontend/src/platform/status/{api.ts,types.ts,StatusStrip.tsx,StatusStrip.test.tsx}`
- Modify: the four `SummaryPage.tsx`, their tests' API mocks, `frontend/src/locales/es-AR.json`

**Interfaces:**
- Produces: `type StatusColor = 'green' | 'yellow' | 'red'`; `STATUS_COLORS`; `statusBackground(color): string` (Mantine color for fills); `useDashboardStatus(key, year)`; `useSetStatus(key)` mutating `{year, month, color: StatusColor | null}` and invalidating `['status', key]` and `['overview']`; `<StatusStrip dashboardKey year />`.
- Locale: `status.title`, `status.states.{green,yellow,red,none}`, `status.clear`, `status.monthLabel` ("{{month}}: {{state}}"), `status.set` ("Cambiar estado de {{month}}"), `status.months.1..12` (full names), `status.monthsShort.1..12`.

- [ ] **Step 1: Write the failing tests**:
  - `shows the twelve months with their state` (accessible name "Marzo: En orden", "Abril: Sin estado").
  - `a viewer cannot change a month` (no buttons).
  - `an admin sets a month's color` (click month → menu → "Crítico"; PUT body `{color: 'red'}`).
  - `an admin clears a month` (`{color: null}`).
  - `future months cannot be changed` (disabled for months after the current one in the current year).
- [ ] **Step 2: Run** `npx vitest run src/platform/status` — Expected: FAIL.
- [ ] **Step 3: Implement** and place `<StatusStrip>` at the top of each summary (Projects uses the current year; the others their selected year).
- [ ] **Step 4: Run** `npx vitest run` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: monthly status strip in dashboard summaries`.

### Task 6: Overview with lights and collapsible sections

**Files:**
- Create: `frontend/src/platform/status/StatusCard.tsx`
- Modify: `frontend/src/dashboards/overview/OverviewPage.tsx`, `OverviewPage.test.tsx`, locale

**Interfaces:**
- Consumes: overview item `status: {year, month, color}[]`, `dashboardIcon`, `statusBackground`.
- Produces: `<StatusCard entry status />`; collapsed keys stored in `localStorage['overview.collapsed']` (JSON array), every access in try/catch.

- [ ] **Step 1: Write the failing tests**:
  - `shows each dashboard's latest light with its month and state, and the earlier months` (card named by the dashboard; "Junio 2025", "Crítico"; earlier months by accessible name).
  - `a dashboard without lights says so` ("Sin estado").
  - `lights come before the indicator sections` (DOM order).
  - `a section collapses and expands from its heading` (`aria-expanded`, indicators hidden).
  - `collapsed sections are remembered` (render, collapse, unmount, render again).
- [ ] **Step 2: Run** `npx vitest run src/dashboards/overview` — Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run** `npx vitest run` — Expected: PASS.
- [ ] **Step 5: Commit** `feat: overview with status lights and collapsible sections`.

### Task 7: Help on table headers

**Files:**
- Create: `frontend/src/platform/HelpTh.tsx`, `HelpTh.test.tsx`, `frontend/src/dashboards/tableHeaders.test.ts`
- Modify: every dashboard file that renders `<Table.Th>` with a name; locale (`<dashboard>.help.*`, `people.help.*`, `help.about`)

**Interfaces:**
- Produces: `<HelpTh help={string} {...Table.Th props}>label</HelpTh>`: the label plus a focusable info button whose accessible name is `help.about` ("Qué significa {{column}}") and whose tooltip shows `help` on hover, focus and touch.

- [ ] **Step 1: Write the failing tests**: `HelpTh` shows its text on hover and on keyboard focus; `tableHeaders.test.ts` reads every non-test `.tsx` under `src/dashboards` (`import.meta.glob` with `?raw`) and fails on any `<Table.Th` that has content and is not in the allow-list (row headers in the environment entry grid, month and year columns).
- [ ] **Step 2: Run** `npx vitest run src/platform/HelpTh.test.tsx src/dashboards/tableHeaders.test.ts` — Expected: FAIL.
- [ ] **Step 3: Implement** and convert every header, writing one help text per column in the locale.
- [ ] **Step 4: Run** `npx vitest run && npx tsc -b && npx oxlint` — Expected: PASS, clean.
- [ ] **Step 5: Commit** `feat: help tooltip on dashboard table headers`.

### Task 8: End to end and docs

**Files:**
- Create: `frontend/e2e/status.spec.ts`
- Modify: `README.md`

- [ ] **Step 1: Write the e2e spec**: the admin sets this month's light to "Crítico" in Ambiental and sees it on the overview card; the viewer sees the strip without controls; the member without access sees no light cards; a header's help opens on hover; a section collapses and stays collapsed after reload.
- [ ] **Step 2: Run** `npx playwright test` — Expected: all specs PASS.
- [ ] **Step 3: Document** the light (who sets it, where it shows) and the header-help convention for new dashboards in `README.md`.
- [ ] **Step 4: Commit** `test: status lights end to end; docs`.
