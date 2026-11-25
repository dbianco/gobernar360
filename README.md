# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user. Today it ships the platform base (municipalities, users,
per-dashboard access, people registry, monthly status lights, accounts by email with
notifications and single sign-on), the Projects, Environment, Economic, Social,
Procedures and Cabinet dashboards, and a general overview.

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
- Accounts by email, notifications and single sign-on: design
  `docs/superpowers/specs/2026-11-22-email-accounts-and-notifications-design.md`,
  task `docs/tasks/01-email-accounts-and-notifications.md`
- Cabinet meetings, commitments and linkable subjects: design
  `docs/superpowers/specs/2026-11-24-cabinet-commitments-design.md`,
  task `docs/tasks/04-cabinet-commitments.md`
- Functional reference: `tableros-de-gestion-portal-ril.md`

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js.

```bash
docker compose up -d                    # PostgreSQL on 5434, mail catcher, sign-on provider

cd backend
cp .env.example .env                    # local email and single sign-on settings
uv run alembic upgrade head             # create the schema
uv run gobernar360 seed-demo            # demo municipalities, users and dashboard data
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000

# in another terminal, from backend/: delivers emails as they are queued
uv run gobernar360 send-email --watch

cd ../frontend
npm install
npm run dev                             # http://localhost:5173
```

`docker compose up -d` starts three services:

| Service | Address | What for |
|---|---|---|
| `db` | `localhost:5434` | PostgreSQL with the dev, test and browser-test databases |
| `mailpit` | inbox at http://localhost:8025, SMTP on 1025 | Catches every email the API sends |
| `oidc` | http://localhost:5556 | OpenID Connect provider for trying single sign-on (`dev/oidc-provider`) |

### Demo accounts

Every demo account uses the password `gobernar360-demo`. Demo data is for local
use only; never load it into a database with real data (`seed-demo --reset`
deletes everything first).

| Email | Role |
|---|---|
| `operador@gobernar360.test` | Platform operator (super-admin): creates and configures municipalities |
| `admin@noetinger.test` | Administrator of Noetinger: manages its users and every dashboard |
| `carga@noetinger.test` | Every dashboard of Noetinger, data entry |
| `lectura@noetinger.test` | Every dashboard of Noetinger, read only |
| `sinacceso@noetinger.test` | Member of Noetinger with no dashboard access |
| `admin@comuna-demo.test` | Administrator of a second municipality (Comuna Demo) |

The local sign-on provider knows the same demo emails with the same password, plus
`sinacceso@noetinger.test` with an email it has not verified and
`desconocida@example.test`, who has no gobernar360 account; gobernar360 lets neither in.
Single sign-on is off for every municipality until its administrator turns it on in
*Configuración*, in the menu or as a tab of *Usuarios* (for the demo: sign in as
`admin@noetinger.test`).

For a real installation create the first operator with
`uv run gobernar360 create-operator --email ... --full-name ...`.

### Who administers what

Municipalities are independent: no municipality can see another one's data.

- The **platform operator** creates municipalities and configures each one: name and
  kind, enabled dashboards, users (add, permissions, administrators, remove, set a
  new password) and its *Configuración* (button on the municipality's page). The operator
  sees configuration only, never dashboard data, unless added as a user of that
  municipality.
- A **municipality administrator** manages a subset of that for their own municipality:
  its users and their permissions, and its configuration (*Configuración*, in the menu):
  who receives notification emails, whether members may use single sign-on, and the text
  of every email it sends. They cannot rename it, enable dashboards or change passwords.

Every list in the app (users, dashboard tables, parameter catalogs, the operator's
municipalities) has a search by name or its main field and shows 10, 20 or 50 rows per
page; the size chosen is remembered per table in the browser. Searches ignore case and
accents, and people are also found by document number. Confirmations (removing a user,
deleting a record, discarding changes) are asked in a modal window, never the browser's
popup.

Users can be added or updated from a CSV file
(*Importar CSV*, with an example to download): one row per person with email, nombre,
administrador (sí/no) and one column per enabled dashboard (Lectura, Carga,
Administración, or empty for no access). The last row for an email wins, whether in the
same file or a later one; a dashboard column left out keeps that access as it is; the
whole file is checked first and nothing changes if any row is wrong.

Nobody types a password for someone else. Adding a user emails them an invitation link
to choose their own. Accounts are shared between municipalities, so adding an email that
already has an account only adds it to the municipality and emails its owner a notice:
the answer is the same either way, and whoever added them gets no way into the account.

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
                         # and resets the gobernar360_e2e database; needs the mail catcher
                         # and the sign-on provider of `docker compose up -d`
```

Coverage and mutation testing (the targets are 95 % coverage and 80 % of mutants killed,
in both halves):

```bash
cd backend
uv run pytest --cov --cov-report=term-missing
uv run python tests/make_test_databases.py 5        # once: a test database per mutmut worker
GOBERNAR360_TEST_DATABASES=5 uv run mutmut run --max-children 4
uv run mutmut results                               # what survived; `mutmut show <name>` for the diff

cd ../frontend
npm run test:coverage    # report in coverage/
npm run test:mutation    # Stryker; report in reports/mutation/index.html
```

Mutation testing takes hours on a laptop. Both tools keep their results, so later runs
only test again what changed (`mutmut run <names>` re-checks given mutants; Stryker runs
incrementally).

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

### Cabinet dashboard

What was agreed about what the other dashboards show: meetings, the commitments taken in
them, who owes each one and by when.

- A municipality has one open meeting at a time, never dated before the last one. Closing it
  copies its minutes, which no later change reaches, and nothing of it can be edited again.
- The proposed agenda has the dashboards whose latest light is yellow or red (and those whose
  month that just ended closed in red, even if the current one is already green), commitments
  overdue or due before the meeting, and what the previous one left undiscussed. It only
  considers lights of dashboards the person preparing it can open, and says how many it left out.
- Preparing a meeting carries over every open commitment, whatever its due date. How many times
  one was postponed is how many meetings it was carried to.
- "Overdue" is computed from the date, never stored. The share delivered on time counts overdue
  commitments against it.
- Editors record and change; whoever owes a commitment may add progress notes even as a viewer.

### Linkable subjects

How one module points at another without importing it (`platform/subjects.py`):

- Every dashboard's months can be linked. A dashboard also declares which of its records can,
  how to search and name them and who may see them, with `DashboardModule.linkable`
  (Projects: `dashboards/projects/subjects.py`).
- Links are checked on write against the municipality and the person's access. Whoever cannot
  see what is linked reads that something of that kind is, and nothing else.
- A module that keeps commitments gives `DashboardModule.get_commitments`; status strips and
  record pages (`<SubjectCommitments>`) show them to whoever can open both dashboards.

### Status lights

Each dashboard has a monthly traffic light (green, yellow or red) that its administrators
set by hand: it is their own reading of the month, not something computed from the
indicators. A month may be left without one, and months that have not started cannot be set.

- The light lives in the platform (`platform/status.py`, `platform/status_router.py`,
  table `dashboard_statuses`), so a new dashboard gets it without code of its own.
- `<StatusStrip dashboardKey year />` at the top of a dashboard's summary shows the twelve
  months, lets administrators change them and lists the open commitments about each one.
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
   its tables in the migration, add the package to both contracts in `backend/.importlinter`,
   and add its name under `dashboards.<key>` in `backend/src/gobernar360/locales/es-AR.json`.
   To email its administrators about events, give the module `alert_kinds` and `get_alerts`.
   To let commitments point at its records, give it `linkable`.
   Helpers shared by dashboards live in `platform` (`tenant_crud`, `api_types`, `csv_export`).
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component and add an
   entry (with its icon) to `src/dashboards/registry.ts`; put its texts in
   `src/locales/es-AR.json`. Put `<StatusStrip>` at the top of its summary and use `<HelpTh>` for
   table headers.
3. The operator enables it per municipality; administrators grant it per user.

### Email, notifications and single sign-on

- **Outbox.** Every email is written to the `email_outbox` table in the same transaction
  as the change that caused it, and `uv run gobernar360 send-email` delivers it over SMTP.
  Run once, it sends everything pending; with `--watch` it keeps running and retries
  failures with growing delays (30 s, doubling, at most an hour). A failed SMTP server
  loses nothing; each message is sent under a row lock, so two workers never send the
  same one. `--retry-failed` gives messages that ran out of attempts (20) another round.
- **Links.** Invitation and recovery links carry a single-use token, stored only as its
  SHA-256, that expires (invitations in 7 days, recovery in 1 hour). Choosing a password
  through one closes every session of the account.
- **Forgot my password** answers the same whether or not the email has an account, and
  accepts 3 requests per address per hour (known or not, so the limit reveals nothing).
- **Notifications.** `uv run gobernar360 notify`, run on a schedule (e.g. daily), emails
  about overdue project milestones and about a dashboard without a status light for the
  month that just ended. They go to the municipality's list of recipients
  (Configuración), or, while that list is empty, to the administrators of each dashboard.
  Each event is emailed once per address, however often the command runs. Anyone with an
  account can turn each kind off in *Mi cuenta*. A dashboard raises its own alerts through
  `DashboardModule.get_alerts`.
- **Single sign-on** through any OpenID Connect provider (authorization code with PKCE,
  state and nonce checked). The platform configures the provider with
  `GOBERNAR360_OIDC_ISSUER`, `_CLIENT_ID` and `_CLIENT_SECRET` (the callback is
  `<app url>/api/auth/sso/callback`); each municipality decides in Configuración whether
  its members may use it, off by default. It only signs in people who already have an
  account with an email the provider verified, never creates accounts, and a session
  opened this way only reaches municipalities that allow it and never operates the
  platform. With Google, for example, the issuer is `https://accounts.google.com`.
- **Email texts.** Every email is HTML with a plain-text copy. The defaults are Spanish
  and live in `backend/src/gobernar360/locales/es-AR.json`; each municipality can replace
  any of them in Configuración with a rich-text editor (invitation, access to an existing
  account, password recovery and each notification). Saved texts are sanitised, may only
  use the variables of their email and must keep the required ones (e.g. `{{link}}`).
  Password recovery uses the text of the account's municipality when it belongs to
  exactly one, the default otherwise.

Configuration is read from `GOBERNAR360_*` environment variables or `backend/.env`; see
`backend/src/gobernar360/core/config.py` and `backend/.env.example`. In production set at
least `GOBERNAR360_APP_URL`, the `SMTP_*` settings and `GOBERNAR360_EMAIL_FROM`, and
`GOBERNAR360_COOKIE_SECURE=true` when serving over HTTPS.

The mail server is only configuration: any provider that accepts SMTP works. For Twilio
SendGrid, for example:

```bash
GOBERNAR360_SMTP_HOST=smtp.sendgrid.net
GOBERNAR360_SMTP_PORT=587
GOBERNAR360_SMTP_SECURITY=starttls        # or port 465 with "tls"
GOBERNAR360_SMTP_USERNAME=apikey          # the literal word "apikey"
GOBERNAR360_SMTP_PASSWORD=<SendGrid API key>
GOBERNAR360_EMAIL_FROM=Municipio <avisos@your-verified-domain>
```

The sender address must be one the provider has verified. Keep the API key out of the
repository: set it in the environment of the API and of the `send-email` worker.
