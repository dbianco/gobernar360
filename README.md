# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user. Today it ships the platform base (municipalities, users,
per-dashboard access, people registry, monthly status lights), the Projects, Environment,
Economic, Social, Procedures and Complaints dashboards, and a general overview.

- Platform and Projects: design `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md`,
  plan `docs/superpowers/plans/2026-11-18-platform-base-and-projects-dashboard.md`
- Environment: design `docs/superpowers/specs/2026-11-18-environment-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-18-environment-dashboard.md`
- Economic and people registry: design `docs/superpowers/specs/2026-11-19-economic-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-19-economic-dashboard.md`
- Social: design `docs/superpowers/specs/2026-11-19-social-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-19-social-dashboard.md`
- Status lights, menu icons and column help: design
  `docs/superpowers/specs/2026-11-20-status-lights-and-ui-design.md`,
  plan `docs/superpowers/plans/2026-11-20-status-lights-and-ui.md`
- Procedures: design `docs/superpowers/specs/2026-11-20-procedures-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-20-procedures-dashboard.md`
- Complaints: design `docs/superpowers/specs/2026-11-23-complaints-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-23-complaints-dashboard.md`, task
  `docs/tasks/03-complaints-dashboard.md`
- Functional reference: `tableros-de-gestion-portal-ril.md`

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js.

```bash
docker compose up -d db                 # PostgreSQL/PostGIS on localhost:5434

cd backend
uv run alembic upgrade head             # create the schema
uv run gobernar360 seed-demo            # demo municipalities, users and dashboard data
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000

cd ../frontend
npm install
npm run dev                             # http://localhost:5173
```

### Demo accounts

Every demo account uses the password `gobernar360-demo`. Demo data is for local
use only; never load it into a database with real data (`seed-demo --reset`
deletes everything first).

| Email | Role |
|---|---|
| `operador@gobernar360.test` | Platform operator (super-admin): creates and configures municipalities |
| `admin@noetinger.test` | Administrator of Noetinger: manages its users and every dashboard |
| `carga@noetinger.test` | Projects, environment, economic and social dashboards, data entry |
| `lectura@noetinger.test` | Projects, environment, economic and social dashboards, read only |
| `sinacceso@noetinger.test` | Member of Noetinger with no dashboard access |
| `admin@comuna-demo.test` | Administrator of a second municipality (Comuna Demo) |

The demo loads several hundred made-up complaints for Noetinger but leaves the Complaints
("Reclamos") dashboard disabled there: the operator enables it from the municipality's page, and
its administrator grants it to other users. A resident already in the registry, for trying the
document lookup: DNI 33.123.456 (Lucía Fernández). Comuna Demo has the dashboard enabled with a
few complaints of its own.

For a real installation create the first operator with
`uv run gobernar360 create-operator --email ... --full-name ...`.

### Who administers what

Municipalities are independent: no municipality can see another one's data.

- The **platform operator** creates municipalities and configures each one: name and
  kind, enabled dashboards, and users (add, permissions, administrators, remove, set a
  new password). The operator can also **suspend** a municipality, giving a reason: its data,
  users and permissions stay, but nobody can work in it. Members already signed in are
  refused from their next request (`403 municipality_suspended`) and see a notice; it leaves
  their municipality switcher. Resuming it restores everything as it was, in the same sessions.
  Both are recorded in the municipality's audit log.
  The operator sees configuration only, never dashboard data, unless
  added as a user of that municipality.
- A **municipality administrator** manages a subset of that for their own municipality:
  its users and their permissions. They cannot rename it, enable dashboards, change
  passwords or add an email that already has an account: accounts are shared between
  municipalities, so those are left to the operator.

## Tests

```bash
cd backend
uv run pytest            # API and tenant-isolation tests, against the gobernar360_test database
uv run ruff check .
uv run lint-imports      # dashboard modules must not import each other

cd ../frontend
npm test -- --run        # component tests
npm run lint
npm run build
npm run e2e              # browser tests; starts its own API and web server on ports 8001/5174
                         # and resets the gobernar360_e2e database
```

## How it is organised

- `backend/src/gobernar360/core`: settings, database sessions, security, errors.
- `backend/src/gobernar360/platform`: municipalities, users, sessions, access levels, audit log, overview.
- `backend/src/gobernar360/dashboards/<key>`: one package per dashboard, registered through
  `DashboardModule` (`dashboards/registry.py`).
- `frontend/src/platform`, `frontend/src/dashboards/<key>`: the same split in the web app.

### People registry

Each municipality has one registry of people (`people` table, `platform/people.py`), shared
by the dashboards that work with residents. It has no screen or routes of its own:

- A dashboard keeps its own data about a person in a link table (`economic_people`,
  `social_people`) and
  points every other table at that link, so it only lists and opens people it incorporated.
- The rest of the registry is reachable only by exact document number, to reuse a person
  another dashboard already loaded instead of duplicating them.
- Removing a person from the last dashboard that uses them deletes them from the registry.
- The web form with the document lookup is shared too:
  `frontend/src/platform/people/RegistryPersonForm.tsx`.

### Reserved text in the Social dashboard

The description of an intervention holds sensitive detail, so the API returns it only to
members with editor level or above on the dashboard (`dashboards/social/access.py`,
`reads_reserved_text`). Viewers see that an intervention happened, its type, date and who
did it; lists answer `description: null` and the CSV has no such column. Every response
with interventions is built by `interventions_router.present`.

Data of different municipalities lives in the same database and is separated by
PostgreSQL row-level security: every tenant table has `municipality_id`, and the
API role can only see rows of the municipality set for the current transaction.

### Procedures dashboard

An inventory, not case tracking: the procedures the municipality offers, what each asks
for, and who already holds that data.

- Requirements come from a single list per municipality and each points at its source
  (municipal, provincial, national or other); a requirement without a source is something
  the person brings themselves.
- The opportunities report ranks sources by how much asking for their data weighs on
  procedures: requirements asked, distinct procedures and their estimated yearly volume,
  each procedure counted once. Municipal sources come first.
- Only procedures marked as active count in the summary, the report and the overview.
- Editors load procedures and requirements; areas and sources are for dashboard admins.
  Access is per dashboard, not per area: the area is a field of the procedure.
- A procedure's link only accepts `http(s)` addresses, because the screen renders it as a link.

### Complaints dashboard

Every complaint a resident makes, followed from reception until it is solved, with the time
it took measured in business days.

- **Lifecycle.** Received → assigned → in progress ⇄ waiting for the resident → resolved →
  closed; rejected from any open state; a resolved complaint can be reopened. Only the moves
  in `dashboards/complaints/lifecycle.py` are accepted (409 `invalid_transition` otherwise),
  and rejecting or reopening needs a note. Each move, reassignment, change of type and note is
  kept in the complaint's timeline with who, when and why; nothing is deleted and nothing can
  be dated back (the server's time is used).
- **Service clock** (`dashboards/complaints/clock.py`, pure functions). Business days of the
  municipality's calendar (working weekdays and holidays, under Parameters). The day of
  reception does not count; the clock stops while waiting for the resident and when resolved
  or rejected. Reopening counts the days the case spent wrongly marked as resolved. A case is
  at risk with a quarter of its target or less left, overdue past it. The clock is read, not
  stored, so a holiday loaded late also corrects earlier cases; the target is copied onto the
  complaint when it is registered, so changing a type's target does not rewrite history.
- **Queues.** A type routes new complaints to its area; editors reassign. Each area's queue is
  ordered by business days left.
- **Residents.** A complaint points at a person of the shared registry, found by exact document
  number (or added to it), or is anonymous.
- **Analysis.** Period figures are about the complaints *received* in the period, so the median
  of `resolution_business_days` per type in the cases CSV equals the summary's median for that
  type (percentiles interpolate like a spreadsheet's PERCENTILE.INC). Backlog figures are as of
  today, whatever the period.
- Levels: viewers read and download; editors register complaints and act on them; dashboard
  admins manage areas, zones, types and the calendar.

### Status lights

Each dashboard has a monthly traffic light (green, yellow or red) that its administrators
set by hand: it is their own reading of the month, not something computed from the
indicators. A month may be left without one, and months that have not started cannot be set.

- The light lives in the platform (`platform/status.py`, `platform/status_router.py`,
  table `dashboard_statuses`), so a new dashboard gets it without code of its own.
- `<StatusStrip dashboardKey year />` at the top of a dashboard's summary shows the twelve
  months and lets administrators change them.
- The general overview shows, per dashboard, its icon on the color of the latest month that
  has a light and the lights set in the five months before it.
- A light is never shown by color alone: every state has its own mark and its name.

### Table header help

Every named column of a dashboard table is rendered with `<HelpTh help={...}>`, which adds an
info icon explaining the column. Help texts live under `<dashboard>.help.*` in the locale
file. `dashboards/tableHeaders.test.ts` fails when a dashboard table uses a plain
`<Table.Th>` for a named column.

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module = DashboardModule(...)`, register it in
   `main.py`, import its models in `migrations/env.py`, call `enable_tenant_rls()` for each of
   its tables in the migration, and add the package to both contracts in `backend/.importlinter`.
   Helpers shared by dashboards live in `platform` (`tenant_crud`, `api_types`, `csv_export`).
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component and add an
   entry (with its icon) to `src/dashboards/registry.ts`; put its texts in
   `src/locales/es-AR.json`. Put `<StatusStrip>` at the top of its summary and use `<HelpTh>` for
   table headers.
3. The operator enables it per municipality; administrators grant it per user.

Configuration is read from `GOBERNAR360_*` environment variables; see
`backend/src/gobernar360/core/config.py`. Set `GOBERNAR360_COOKIE_SECURE=true` when serving over HTTPS.
