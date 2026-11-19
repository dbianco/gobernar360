# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user. Today it ships the platform base (municipalities, users,
per-dashboard access, people registry), the Projects, Environment, Economic and
Social dashboards, and a general overview.

- Platform and Projects: design `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md`,
  plan `docs/superpowers/plans/2026-11-18-platform-base-and-projects-dashboard.md`
- Environment: design `docs/superpowers/specs/2026-11-18-environment-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-18-environment-dashboard.md`
- Economic and people registry: design `docs/superpowers/specs/2026-11-19-economic-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-19-economic-dashboard.md`
- Social: design `docs/superpowers/specs/2026-11-19-social-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-19-social-dashboard.md`
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

For a real installation create the first operator with
`uv run gobernar360 create-operator --email ... --full-name ...`.

### Who administers what

Municipalities are independent: no municipality can see another one's data.

- The **platform operator** creates municipalities and configures each one: name and
  kind, enabled dashboards, and users (add, permissions, administrators, remove, set a
  new password). The operator sees configuration only, never dashboard data, unless
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

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module = DashboardModule(...)`, register it in
   `main.py`, import its models in `migrations/env.py`, call `enable_tenant_rls()` for each of
   its tables in the migration, and add the package to both contracts in `backend/.importlinter`.
   Helpers shared by dashboards live in `platform` (`tenant_crud`, `api_types`, `csv_export`).
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component and add an
   entry to `src/dashboards/registry.ts`; put its texts in `src/locales/es-AR.json`.
3. The operator enables it per municipality; administrators grant it per user.

Configuration is read from `GOBERNAR360_*` environment variables; see
`backend/src/gobernar360/core/config.py`. Set `GOBERNAR360_COOKIE_SECURE=true` when serving over HTTPS.
