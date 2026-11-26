# gobernar360

Workspace of management dashboards for local governments (municipalities and
communes). Each dashboard is an independent module, enabled per municipality
and granted per user. Today it ships the platform base (municipalities, users,
per-dashboard access, people registry, monthly status lights, accounts by email with
notifications and single sign-on, zones and maps), the Projects, Environment, Economic, Social,
Procedures, Complaints and Cabinet dashboards, and a general overview.

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
- Indicator history, targets and combined indicators: design
  `docs/superpowers/specs/2026-11-23-indicator-history-and-targets-design.md`
- Monthly report and public page: design
  `docs/superpowers/specs/2026-11-23-monthly-report-and-public-page-design.md`
- Procedures: design `docs/superpowers/specs/2026-11-20-procedures-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-20-procedures-dashboard.md`
- Accounts by email, notifications and single sign-on: design
  `docs/superpowers/specs/2026-11-22-email-accounts-and-notifications-design.md`,
  task `docs/tasks/01-email-accounts-and-notifications.md`
- Complaints: design `docs/superpowers/specs/2026-11-23-complaints-dashboard-design.md`,
  plan `docs/superpowers/plans/2026-11-23-complaints-dashboard.md`, task
  `docs/tasks/03-complaints-dashboard.md`
- Cabinet meetings, commitments and linkable subjects: design
  `docs/superpowers/specs/2026-11-24-cabinet-commitments-design.md`,
  task `docs/tasks/04-cabinet-commitments.md`
- Commitments for everyone and notifications: design
  `docs/superpowers/specs/2026-11-24-commitments-and-notices-design.md`
- Geographic layer: design `docs/superpowers/specs/2026-11-24-geographic-layer-design.md`,
  task `docs/tasks/07-geographic-layer.md`
- Notices to residents and CiDi: task `docs/tasks/19-cidi-resident-notices.md`; what is known
  about CiDi, `docs/cidi/README.md`
- Digitalization of procedures: task `docs/tasks/20-procedures-digitalization.md`
- Official provincial geography: task `docs/tasks/21-idecor-official-layers.md`; the services,
  `docs/idecor/README.md`
- Functional reference: `tableros-de-gestion-portal-ril.md`

## Quick start

Requirements: Docker, [uv](https://docs.astral.sh/uv/), Node.js.

```bash
docker compose up -d                    # PostgreSQL on 5434, mail catcher, sign-on provider

cd backend
cp .env.example .env                    # local email and single sign-on settings
uv run alembic upgrade head             # create the schema
uv run gobernar360 seed-demo            # demo municipalities, users and dashboard data
uv run gobernar360 snapshot-indicators  # record this month's indicators (schedule it daily)
uv run uvicorn gobernar360.main:create_app --factory --reload --port 8000

# in another terminal, from backend/: delivers emails as they are queued
uv run gobernar360 send-email --watch
# and in another, notices to residents through CiDi (the fake one: `cidi-fake-inbox` shows them)
uv run gobernar360 send-notices --watch

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
deletes everything first). Noetinger's demo includes twelve months of indicator
history and targets for this year and the last, closed reports of earlier months (last
month is left open) and its public page at `/p/noetinger` with two dashboards published and
no indicator or report yet. Comuna Demo has neither.

The public page reads through its own database role, `gobernar360_public`, created by
`db/init` on a fresh database or by the migrations otherwise. Its default password matches
the development defaults; change it, and `GOBERNAR360_PUBLIC_DATABASE_URL`, anywhere the
database is reachable by others.

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
The demo loads several hundred made-up complaints for Noetinger but leaves the Complaints
("Reclamos") dashboard disabled there: the operator enables it from the municipality's page, and
its administrator grants it to other users. A resident already in the registry, for trying the
document lookup: DNI 33.123.456 (Lucía Fernández). Comuna Demo has the dashboard enabled with a
few complaints of its own.

For a real installation create the first operator with
`uv run gobernar360 create-operator --email ... --full-name ...`.

### Who administers what

Municipalities are independent: no municipality can see another one's data.

Every user can change their own name, contact phone and password from "Mi cuenta" (their
name in the header). Any change there asks for the current password; leaving the new
password empty keeps the current one, and setting one signs out their other sessions.
An account without a password (one that only signs in through single sign-on) changes its
name and phone without being asked for one, and gets a password only through the
"forgot my password" link.

- The **platform operator** creates municipalities and configures each one: name and
  kind, enabled dashboards, users (add, permissions, administrators, remove, set a
  new password) and its *Configuración* (button on the municipality's page). The operator
  can also **suspend** a municipality, giving a reason: its data, users and permissions
  stay, but nobody can work in it. Members already signed in are refused from their next
  request (`403 municipality_suspended`) and see a notice; it leaves their municipality
  switcher. Resuming it restores everything as it was, in the same sessions. Both are
  recorded in the municipality's audit log. The operator sees configuration only, never
  dashboard data, unless added as a user of that municipality.
- A **municipality administrator** manages a subset of that for their own municipality:
  its users and their permissions, its zones (*Zonas*, in the menu) and its configuration
  (*Configuración*, in the menu), in tabs by kind: *Correos* (who receives notification
  emails, how residents are told about their complaints and the connection to CiDi, and the text
  of every email it sends), *Acceso* (whether members may use single
  sign-on) and *Mapas y zonas* (the background of its maps, and how small a count per zone
  viewers see). They cannot rename it, enable dashboards or change passwords.

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
uv run pytest --cov      # the whole suite with coverage; fails under 95 %

cd ../frontend
npm test -- --run        # component tests
npm run test:coverage    # the same with coverage; fails if any metric is under 95 %
npm run lint
npm run build
npm run e2e              # browser tests; starts its own API and web server on ports 8001/5174
                         # and resets the gobernar360_e2e database; needs the mail catcher
                         # and the sign-on provider of `docker compose up -d`
```

Coverage and mutation testing (the targets are 95 % coverage, of every file and not only in
total, and 80 % of mutants killed, in both halves):

```bash
cd backend
uv run pytest --cov --cov-report=term-missing
uv run python tests/make_test_databases.py 5        # once: a test database per mutmut worker
GOBERNAR360_TEST_DATABASES=5 uv run python -m tests.run_mutmut run --max-children 4
uv run python -m tests.run_mutmut results           # what survived; `show <name>` for the diff

cd ../frontend
npm run test:coverage    # report in coverage/
npm run test:mutation    # Stryker; report in reports/mutation/index.html
```

Mutation testing takes hours on a laptop. Both tools keep their results, so later runs
only test again what changed (`tests.run_mutmut run <names>` re-checks given mutants; Stryker
runs incrementally). `tests/run_mutmut.py` is mutmut with one addition: alone, mutmut skips every
decorated function, which here means all the API routes, commands and validators.

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
  another dashboard already loaded instead of duplicating them, or by exact CUIL. A CUIL
  must have the right last digit and, with a document, have it inside.
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

### Geographic layer

Place is part of the platform (`platform/geo`): a municipality draws its zones, and any
dashboard can give its records a location.

- **Zones** are drawn on a map or uploaded as GeoJSON (*Zonas*, for administrators). A
  boundary that is not closed or crosses itself is refused; overlapping zones are saved and
  reported. Moving a boundary adds a version from that moment on: the figures of a past year
  use the boundaries in force when it ended (before the first zone was drawn, today's) and leave
  out the records loaded since. A point exactly on a border shared by two zones counts in both.
- **Official geography.** `uv run gobernar360 import-idecor noetinger --radius --layers health,schools`
  brings in, from the Province's IDECOR, the urban radius as the zone "Radio urbano" (with the law
  that approves it) and the health centres and schools inside it, which every member can see on
  any map with the switch *Equipamiento*. Safe to repeat; a failure changes nothing; with
  `--from-dir docs/idecor/samples` it needs no internet. The operator says where the municipality
  is (its IDECOR key and its CONAE satellite layer) in its *Configuración*, tab *Mapas y zonas*;
  with a layer, *Satélite (CONAE)* is one more background.
- **Located records**: projects (a point, or a line for works along a street), social
  households and economic actors. The location is set by clicking on the map or typing
  coordinates; nothing is sent to a geocoding service and the address stays as text.
- **Zone assignment** is done by database triggers, for every version of every zone, when a
  location or a boundary changes. A line belongs to every zone it crosses; a record where
  two zones overlap is in both and counts once in totals. What has no zone is listed for
  review in each map and in *Zonas*. `uv run gobernar360 assign-zones` works everything out
  again, e.g. after restoring a backup with the triggers off.
- **Maps** ask only for what is inside the visible area, with the filters of the list, and
  the API groups close records, so the answer stays small however many there are.
- **Sensitive places.** Where a household lives, and its zone, are for editors and above.
  Viewers get counts per zone: those under the municipality's minimum (*Configuración*,
  tab *Mapas y zonas*; 5 by default, from 2 to 100) are hidden, and so are the others needed to keep them from being worked out by subtracting;
  a viewer cannot narrow the counts with a search, and sees the past a month at a time, so that
  two days in a row do not tell what was loaded in between. CSV files follow the same rules.
- **Isolation.** Zones, versions and assignments are tenant tables under row-level security,
  and the triggers also filter by municipality themselves. There are no spatial indexes on
  purpose: row-level security keeps the API role from using them (PostGIS operators are not
  leakproof), so queries narrow by municipality first.
  The list of households, with the address typed as text, is open to viewers as always.
- **Background.** Each municipality chooses it in *Configuración*, tab *Mapas y zonas*, with a
  preview, from OpenStreetMap's list (`platform/geo/backgrounds.py`): standard,
  humanitarian, CyclOSM, German, French, topographic and public transport need no key;
  Thunderforest's cycle and transport maps, Tracestrack and MapTiler ask for the key the
  provider gives the municipality. The default needs none. Public servers are meant for
  moderate use: a busy municipality should choose one with a key. Without the background,
  zones and records are still drawn.

The database needs PostGIS; migration 0019 enables it, which takes a superuser (the local
container's owner role is one).

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
- **Digitalization.** An online procedure may say the least CiDi level people sign in with (1
  Confirmado, 2 Verificado, 3 Autenticado). One is *100 % digital*, always worked out, when it is
  active, can be done online, has an address and asks for nothing mandatory on paper. Four
  indicators, the table by level and the monthly report follow from that.
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
  number or CUIL (or added to it), or is anonymous. Resolving or rejecting one tells its resident
  (see *Notices to residents*).
- **Analysis.** Period figures are about the complaints *received* in the period, so the median
  of `resolution_business_days` per type in the cases CSV equals the summary's median for that
  type (percentiles interpolate like a spreadsheet's PERCENTILE.INC). Backlog figures are as of
  today, whatever the period.
- Levels: viewers read and download; editors register complaints and act on them; dashboard
  admins manage areas, zones, types and the calendar.

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
  commitments against it. The figures go by the date agreed in the meeting: moving it later is
  kept in the history and does not change them. Each list shows both dates.
- Editors record and change; whoever owes a commitment says it is done and may move its date or
  pass it on, with or without access to this dashboard.

### Commitments and notifications

Every member of a municipality has *Compromisos* in the menu, whatever their dashboards.

- Anyone gives a commitment to anyone, or to themselves, and attaches people to be told when it
  is done. Those of a cabinet meeting and the informal ones are listed together: the ones you
  owe, gave or follow.
- When somebody is removed from the municipality, the administrator gets the open ones they owed
  and may see (*Usuarios*) to give them to somebody else, and how many more there are; whoever
  gave an informal one is told. Until then they say that their owner left.
- An informal one is seen only by whoever gave it, whoever owes it and those attached, not by
  administrators or the cabinet. One of a meeting is seen by the cabinet's members too.
- Whoever owes it says it is done and changes its date or its owner. Whoever gave an informal
  one corrects, drops or reopens it. Those attached only read it.
- Two icons beside the user's name count what they owe and what is new; hovering previews them
  and clicking opens *Notificaciones*, with the status and target date of each. Delivered ones
  stay there until they are read. Nothing is emailed.
- Informal ones do not count in the cabinet's figures, agenda or postponements. They show beside
  a project or a month only to those who may see them.

### Linkable subjects

How one module points at another without importing it (`platform/subjects.py`):

- Every dashboard's months can be linked. A dashboard also declares which of its records can,
  how to search and name them and who may see them, with `DashboardModule.linkable`
  (Projects: `dashboards/projects/subjects.py`).
- Links are checked on write against the municipality and the person's access. Whoever cannot
  see what is linked reads that something of that kind is, and nothing else.
- Status strips and record pages (`<SubjectCommitments>`) show the open commitments about them
  to whoever may see both. A dashboard that records commitments tells where each was taken with
  `DashboardModule.get_commitment_origins`.

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
- Under each month's light the strip shows that month's headline indicators.

### Indicator history and targets

Each dashboard declares its headline indicators in its `DashboardModule` (`indicators`: key,
unit, whether higher is better and whether its past can be rebuilt) and computes them with
`get_summary(ctx, date)`, as of that date. The platform keeps their history and targets
without knowing any dashboard, so a new dashboard gets all of this from its catalogue.

- **Monthly snapshots.** `uv run gobernar360 snapshot-indicators` records every indicator of
  every enabled dashboard for the current month, as of today, one municipality at a time and
  each in its own tenant-scoped transaction. Schedule it daily (or at least on each month's
  last day): a month keeps the values of its last run. It is safe to repeat.
- **Rebuilding.** `--from 2026-01` also recomputes the closed months since then, at each
  month's last day, for the indicators that can be rebuilt: those counted from dated records
  (economic assignments, social deliveries and interventions of the year). The others depend
  on how data stands today, so a past month keeps what was recorded at the time or stays
  empty; it is never filled in with today's value.
- **Targets.** Dashboard administrators set a target per indicator and year in the dashboard's
  parameters. The deviation takes the direction into account: positive is better than the
  target and negative worse, so 6 delayed projects against a target of 4 is −2, off track.
- **Evolution.** Summaries and the general overview show each indicator's value today, its
  change since the close of the previous month and of the same month last year, the last
  twelve months and the target line; a card opens the series as a chart or a table.
- **Combined indicators.** The overview also relates dashboards, e.g. online procedures per
  economic actor, defined in `platform/indicators.py` from catalogue keys. A member sees one
  only when they can see both dashboards.

### Monthly report

A municipality administrator closes a month that has ended (Informes). That freezes a
report: each dashboard's light, its indicators at the close of the month with the change
against the previous month and the target, the milestones reached and overdue in the
month, and a comment per dashboard. Later edits to the data never change it.

- Reopening is explicit: the closed version is kept, a new draft version starts with the
  same comments, and both steps are in the audit log. A published report stops being
  published.
- The PDF is rendered on the server (`platform/report_pdf.py`, fpdf2 with the PDF's base
  fonts) and is deterministic: the same report gives the same bytes. Lights carry a drawn
  mark and their name, so it reads in black and white.
- Dashboards add their own tables through `report_tables` in their `DashboardModule`; they
  must hold no personal data.

### Public page

`/p/<address>` shows, without signing in, what the municipality chose to publish (Página
pública): the page itself, each dashboard's lights, each indicator, and each closed report.

- What is published is copied to separate tables (`public_*`) when the choice changes and on
  every snapshot run. The public routes (`/api/public/...`) read only those, through a role
  that cannot read anything else, with no session and no municipality set. They are rate
  limited and cacheable (`ETag`, always revalidated), so unpublishing shows at once.
- Only indicators declared `aggregate` in the catalogue can be published. Counts from 1 to
  the threshold the municipality sets minus one are shown as "menos de N", also in the
  series and in the published PDF.
- The published PDF of a report shows only the dashboards and indicators the page
  publishes at that moment (it is rendered again when the choice changes) and leaves out
  the dashboards' tables, such as the milestones, whose text nobody checked.
- A report whose comments name someone of the people registry (their last name next to
  one of their first names) or one of their document numbers cannot be published.
- When the operator disables a dashboard, what was published of it is forgotten: enabling
  it again publishes nothing until the administrator chooses.

### Table header help

Every named column of a dashboard table is rendered with `<HelpTh help={...}>`, which adds an
info icon explaining the column. Help texts live under `<dashboard>.help.*` in the locale
file. `dashboards/tableHeaders.test.ts` fails when a dashboard table uses a plain
`<Table.Th>` for a named column.

### Adding a dashboard

1. Backend: create `dashboards/<key>/` exposing `module = DashboardModule(...)` with its
   indicator catalogue (with each indicator's Spanish `name`, and `aggregate=True` for those
   that may be published) and its `name`, optionally `report_tables` for the monthly report,
   register it in `register_dashboards()` in `main.py`, import its models in
   `migrations/env.py`, call `enable_tenant_rls()` for each of its tables in the migration, add
   the package to both contracts in `backend/.importlinter`, and add its name under
   `dashboards.<key>` in `backend/src/gobernar360/locales/es-AR.json`.
   To email its administrators about events, give the module `alert_kinds` and `get_alerts`.
   To let commitments point at its records, give it `linkable`.
   To put its records on the map, see *Located records* in `CLAUDE.md`.
   Helpers shared by dashboards live in `platform` (`tenant_crud`, `api_types`, `csv_export`).
2. Frontend: create `src/dashboards/<key>/` with a default-exported routes component and add an
   entry (with its icon) to `src/dashboards/registry.ts`; put its texts, and its indicators'
   names under `overview.indicators`, in `src/locales/es-AR.json`. Put `<StatusStrip>` and
   `<HeadlineIndicators>` at the top of its summary, `<IndicatorTargets>` in its parameters, and
   use `<HelpTh>` for table headers.
3. The operator enables it per municipality; administrators grant it per user.

### Notices to residents

What a resident is told about what they asked for (`platform/resident_notices.py`); today, that
their complaint was resolved or rejected.

- **Channel.** Each municipality chooses it in *Configuración*, tab *Correos*, section *Avisos a
  vecinos*: only email (the default), CiDi and otherwise email, or only CiDi. CiDi is the
  provincial account; its user name is the person's CUIL. Whoever has neither an account nor an
  address is shown as such to the editors, so they know that nobody was told.
- **Adhesion.** Each municipality adheres to CiDi by itself. The same section prints the request,
  keeps how far it is and the connection data. Secrets are write-only and stored encrypted with
  `GOBERNAR360_SECRETS_KEY`. CiDi can be chosen once the adhesion is approved and the data complete.
- **What it says.** The municipality's template with the complaint's number and type, plus the
  message the employee writes *for the resident*. The internal note and the history never leave.
  The text is frozen when queued.
- **Delivery.** Emails go to the outbox. `uv run gobernar360 send-notices` (`--watch` to keep
  running) hands the rest over to CiDi, retrying up to 20 times; somebody CiDi does not know is
  emailed the same text when the municipality wants that. Each event is told once.
- **No legal claims.** The only wording is "Entregado a CiDi".
- `GOBERNAR360_CIDI_MODE`: `off` (the default), `fake` (messages go to a file that
  `uv run gobernar360 cidi-fake-inbox` shows) or `live`, which sends nothing until the Province
  gives its technical specification (`docs/cidi/questions-for-province.md`).

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
`GOBERNAR360_COOKIE_SECURE=true` when serving over HTTPS, and your own passwords: in production
(secure cookies, or `GOBERNAR360_ENVIRONMENT=production`) the API does not start while
`GOBERNAR360_DATABASE_URL` or `GOBERNAR360_PUBLIC_DATABASE_URL` have the development ones, nor with
the fake CiDi. Municipalities
can save secrets once `GOBERNAR360_SECRETS_KEY` is set.

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
