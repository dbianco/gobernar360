# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user. Today it ships the platform base (municipalities, users,
per-dashboard access) and the Projects dashboard, plus a general overview.

- Design: `docs/superpowers/specs/2026-11-18-gobernar360-platform-design.md`
- Implementation plan: `docs/superpowers/plans/2026-11-18-platform-base-and-projects-dashboard.md`
- Functional reference: `tableros-de-gestion-portal-ril.md`

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js.

```bash
docker compose up -d db                 # PostgreSQL/PostGIS on localhost:5434

cd backend
uv run alembic upgrade head             # create the schema
uv run gobernar360 seed-demo            # demo municipalities, users and projects
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
| `operador@gobernar360.test` | Platform operator: creates municipalities, enables dashboards |
| `admin@noetinger.test` | Administrator of Noetinger: manages its users and every dashboard |
| `carga@noetinger.test` | Projects dashboard, data entry |
| `lectura@noetinger.test` | Projects dashboard, read only |
| `sinacceso@noetinger.test` | Member of Noetinger with no dashboard access |
| `admin@comuna-demo.test` | Administrator of a second municipality (Comuna Demo) |

For a real installation create the first operator with
`uv run gobernar360 create-operator --email ... --full-name ...`.

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

Data of different municipalities lives in the same database and is separated by
PostgreSQL row-level security: every tenant table has `municipality_id`, and the
API role can only see rows of the municipality set for the current transaction.

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module = DashboardModule(...)`, register it in
   `main.py`, call `enable_tenant_rls()` for each of its tables in the migration, and add the
   package to both contracts in `backend/.importlinter`.
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component and add an
   entry to `src/dashboards/registry.ts`; put its texts in `src/locales/es-AR.json`.
3. The operator enables it per municipality; administrators grant it per user.

Configuration is read from `GOBERNAR360_*` environment variables; see
`backend/src/gobernar360/core/config.py`. Set `GOBERNAR360_COOKIE_SECURE=true` when serving over HTTPS.
