# Operator Municipality Administration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the platform operator edit a municipality and manage its users with the same rules as the local administrator, plus set a user's password.

**Architecture:** The member-management routes become a router factory (`platform/members.py`) parameterised by the dependency that yields the `RequestContext`. It is mounted under `/admin` (active municipality, municipality admin) and under `/platform/municipalities/{municipality_id}` (path municipality, operator). The operator context sets the tenant so audit rows can be written, and carries no membership. The web reuses one `MembersPanel` for both.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest against `gobernar360_test`; React + Mantine + TanStack Query, Vitest + MSW, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-19-operator-municipality-admin-design.md`

## Global Constraints

- Source code in English; UI copy only in `frontend/src/locales/es-AR.json`.
- Routes flush, never commit. Errors use `core/errors.py` helpers.
- One local commit per task on `main`; never push. Commit messages end with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- The operator never gains access to dashboard data or `/api/overview`.
- Backend checks: `uv run ruff format -q . && uv run ruff check . && uv run lint-imports && uv run pytest -q`. Frontend checks: `npx tsc -b && npm run lint && npm test -- --run`.

## Review Focus

- A `membership_id` of municipality B sent to `/platform/municipalities/{A}/users/{id}` (PATCH, DELETE, password): must be 404 and change nothing.
- A municipality admin calling any `/platform/...` route, including the password one: 403.
- Operator demoting or removing the only administrator: 409, as for the local admin; adding the first user of an empty municipality as non-admin: allowed.
- Password set by the operator: every open session of that account ends, the old password stops working, a password under 10 characters is 422.
- Operator PATCH of a municipality with `slug` or an unknown field, or a blank name: 422 and nothing changes.

---

### Task 1: Backend — shared member routes, municipality edit, password

**Files:**
- Create: `backend/src/gobernar360/platform/members.py`
- Modify: `backend/src/gobernar360/platform/admin_router.py` (becomes a thin mount), `backend/src/gobernar360/platform/operator_router.py`, `backend/src/gobernar360/platform/access.py` (`RequestContext.membership: Membership | None`)
- Test: `backend/tests/platform/test_operator.py`, new `backend/tests/platform/test_operator_users.py`

**Interfaces:**
- Produces: `members.build_router(context: Callable[..., RequestContext]) -> APIRouter` with `GET /dashboards`, `GET/POST /users`, `PATCH/DELETE /users/{membership_id}` (schemas `MemberIn`, `MemberPatch`, `MemberOut` move here unchanged). `operator_router.get_operator_context(municipality_id, db, operator) -> RequestContext` (404 for an unknown municipality; calls `set_tenant`; `membership=None`).
- API: `PATCH /api/platform/municipalities/{id}` body `MunicipalityPatch(name?: 1..200 chars stripped, kind?: municipality|commune)`, `extra="forbid"`, returns `MunicipalityDetail`. `PUT /api/platform/municipalities/{id}/users/{membership_id}/password` body `{password}` → 204. `POST .../admins` is removed.

- [ ] **Step 1: Write failing tests** in `test_operator_users.py` (fixture `operator_client` as in `test_operator.py`, municipalities via factories with `demo` enabled):
  - `test_operator_lists_only_the_users_of_that_municipality`
  - `test_operator_adds_a_user_with_grants_who_can_then_sign_in`
  - `test_operator_adds_the_first_administrator_of_a_new_municipality`
  - `test_operator_changes_grants_and_admin_role`
  - `test_operator_cannot_leave_a_municipality_without_administrator` (PATCH `is_admin: false` and DELETE → 409)
  - `test_operator_removes_a_user`
  - `test_operator_grant_for_a_dashboard_not_enabled_is_rejected` (422)
  - `test_membership_of_another_municipality_is_not_found` (PATCH, DELETE, password → 404; the membership is unchanged)
  - `test_unknown_municipality_returns_not_found` (GET users → 404)
  - `test_operator_changes_are_audited_in_the_municipality` (audit row with the operator's `user_id` and that `municipality_id`)
  - `test_operator_sets_a_password_and_ends_open_sessions` (a second client signed in as the user gets 401 afterwards; old password fails; new one works)
  - `test_short_password_is_rejected` (422)
  - `test_municipality_admin_cannot_use_operator_user_routes` (GET, POST, password → 403)
  - `test_operator_lists_enabled_dashboards_of_a_municipality`
  And in `test_operator.py`: replace the `/admins` test with `test_operator_renames_a_municipality_and_changes_its_kind`, `test_municipality_slug_and_unknown_fields_cannot_be_patched` (422, unchanged), `test_blank_municipality_name_is_rejected`, `test_patching_an_unknown_municipality_returns_not_found`, `test_non_operator_cannot_patch_a_municipality`.
- [ ] **Step 2: Run** `uv run pytest tests/platform/test_operator.py tests/platform/test_operator_users.py -q` — Expected: the new tests FAIL (404/405).
- [ ] **Step 3: Implement.** Move the handlers of `admin_router.py` into `members.build_router`; `admin_router.router = APIRouter(prefix="/admin", tags=["admin"])` including `build_router(require_municipality_admin)`. In `operator_router.py` add the PATCH, `get_operator_context`, include `build_router(get_operator_context)` under `/municipalities/{municipality_id}`, add the password route (membership looked up by id **and** municipality; deletes the user's `sessions`), remove `/admins` and `AdminIn`.
- [ ] **Step 4: Run** the backend checks from Global Constraints — Expected: all pass.
- [ ] **Step 5: Commit** `feat: let the operator edit municipalities and manage their users`.

### Task 2: Web — municipality configuration page

**Files:**
- Create: `frontend/src/platform/MembersPanel.tsx`, `frontend/src/platform/MunicipalityPage.tsx`, `frontend/src/platform/MunicipalityPage.test.tsx`
- Modify: `frontend/src/platform/UsersAdminPage.tsx` (title + `<MembersPanel base="/admin" scope={['admin']} />`), `frontend/src/platform/UserForm.tsx` (prop `base: string` replaces `adminOf`; always posts `{...account, is_admin, grants}` to `${base}/users`), `frontend/src/platform/OperatorPage.tsx` (list + create form only; each municipality links to its page), `frontend/src/App.tsx` (route `platform/municipalities/:id`), their tests, `frontend/src/locales/es-AR.json`
- Test: `MunicipalityPage.test.tsx`, updated `OperatorPage.test.tsx`, `UserForm.test.tsx`

**Interfaces:**
- Consumes: Task 1 API.
- Produces: `MembersPanel(props: { base: string; scope: string[]; canSetPassword?: boolean })` — `base` is the API prefix (`/admin` or `/platform/municipalities/{id}`); query keys are `[...scope, 'users']` and `[...scope, 'dashboards']`; actions invalidate `scope[0]` and `me`.

- [ ] **Step 1: Write failing tests** (`MunicipalityPage.test.tsx`, rendered through `<App />` at `/platform/municipalities/m-1` as an operator with no municipalities, mocking `/platform/municipalities`, `/platform/dashboards`, `/platform/municipalities/m-1/users`, `/platform/municipalities/m-1/dashboards`):
  - `renames the municipality` — PATCH body `{ name: 'Noetinger Nuevo', kind: 'municipality' }`
  - `enables a dashboard` — PUT body `{ keys: ['projects'] }`
  - `lists the users of the municipality and changes a level` — PATCH to `/platform/municipalities/m-1/users/ms-2` with `{ grants: { projects: 'editor' } }`
  - `adds an administrator` — POST to `/platform/municipalities/m-1/users` with `is_admin: true, grants: {}`
  - `sets a new password for a user` — PUT `.../users/ms-2/password` with `{ password: 'long-password-2' }`, then a confirmation text
  - `rejects a short new password without calling the server`
  - `says so when the municipality does not exist`
  - `keeps the page away from non-operators`
  `OperatorPage.test.tsx`: keep create; replace the dashboard and admin tests with `links each municipality to its configuration`. `UserForm.test.tsx`: pass `base="/admin"`.
  The existing `UsersAdminPage.test.tsx` must pass unchanged, and must not show a password button.
- [ ] **Step 2: Run** `npm test -- --run src/platform` — Expected: new tests FAIL.
- [ ] **Step 3: Implement** the files above. The password dialog is a small form inside `MembersPanel` (field `users.newPassword`, min 10 characters checked client-side).
- [ ] **Step 4: Run** the frontend checks — Expected: all pass.
- [ ] **Step 5: Commit** `feat: add the municipality configuration page for operators`.

### Task 3: End-to-end and README

**Files:**
- Modify: `frontend/e2e/platform.spec.ts`, `README.md`

- [ ] **Step 1: Rewrite the operator e2e test** as `operator creates a municipality, configures it and its administrator signs in`: create "Villa Prueba"; open its configuration; rename to "Villa Prueba Norte"; enable Proyectos (still checked after reload); add user `admin@villa-prueba.test` as administrator; log out; sign in as that user (password typed in the form) and see "Villa Prueba Norte" in the header and "Proyectos" in the sidebar. Add `operator sets a new password for a municipality user`: for `sinacceso@noetinger.test` in Noetinger; sign in with the new password. (The e2e `login` helper takes the password as an optional third argument.)
- [ ] **Step 2: Run** `npm run e2e` — Expected: all pass.
- [ ] **Step 3: README** — describe operator vs municipality administrator in the roles/accounts section.
- [ ] **Step 4: Commit** `test: cover operator municipality administration end to end`.
