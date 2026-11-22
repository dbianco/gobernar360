# Task 08: Municipality lifecycle — suspend, export, restore, delete

## Task description

A municipality can be created in gobernar360 but never leaves: it cannot be suspended,
its data cannot be taken out, and it cannot be removed. For software that holds a local
government's records this is a real obstacle: a government changes, a municipality
moves to its own installation, or simply asks for a copy of everything it loaded. This
session gives the platform operator the full lifecycle, and proves that the isolation
between municipalities holds everywhere.

The centre of the work is an export that can be restored, verified by tests rather
than by trust:

- **Suspend and resume.** A suspended municipality keeps its data but nobody can work
  in it: its members' sessions stop resolving to it at once, it disappears from the
  municipality switcher, and its public surfaces (if any) go dark. The operator sees
  the state and the reason. Resuming restores everything as it was.
- **Complete export.** `gobernar360 export-municipality <slug>` and the operator screen
  produce one archive with every row that belongs to the municipality, across platform
  and all dashboard tables, plus its memberships and grants, in a documented, versioned
  format with a manifest (table, row count, checksum). The list of tables is derived
  from the model metadata, not written by hand, so a new dashboard is exported without
  changing this code. Users are exported by reference (email and name), never with
  password hashes.
- **Restore.** `gobernar360 import-municipality <archive>` loads the archive into the
  same or another installation, under a new or the same slug, remapping identifiers so
  it cannot collide with existing data, reattaching users by email or creating inactive
  accounts for unknown ones, and refusing an archive from an incompatible schema
  version with a clear message. It is all-or-nothing.
- **Round-trip proof.** A test seeds the demo municipality, exports it, restores it
  under another slug, and compares every dashboard's summary, list endpoints and CSV
  exports between the two: they must be identical apart from identifiers.
- **Delete.** Deleting a municipality requires it to be suspended, a fresh export to
  exist, and the operator to type its name. It removes every row in dependency order,
  leaves users who belong to other municipalities untouched, and writes a platform
  audit record that survives the deletion.
- **Isolation audit.** A test walks the database catalogue and fails if any table with
  `municipality_id` lacks forced row-level security, the tenant policy or the grant to
  the API role, and if any table without it is reachable in a way that leaks tenant
  data. A second test runs every registered list endpoint as a member of municipality
  A while municipality B holds data, and asserts nothing of B is returned.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`,
API and web app running.

Automated, all must pass:

- `cd backend && uv run pytest` — includes the round-trip test, the isolation audit,
  and tests for: a suspended municipality rejects requests from an already signed-in
  member; resume restores access; the archive contains no password hash or session
  token; a tampered archive (wrong checksum) is refused; a failed restore leaves no
  rows; delete is refused without suspension and without an export; delete leaves a
  shared user's other membership intact; a dashboard registered only in the test with
  its own table is included in export and delete with no change to lifecycle code.
- `cd backend && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`

By hand:

1. As `operador@gobernar360.test` suspend Comuna Demo. In another browser, where
   `admin@comuna-demo.test` was already signed in, the next click says the municipality
   is suspended. Resume it: the admin can work again.
2. Run `uv run gobernar360 export-municipality noetinger -o noetinger.zip`, then
   `uv run gobernar360 import-municipality noetinger.zip --slug noetinger-copia`.
   Sign in as a Noetinger admin, switch to the copy: every dashboard shows the same
   numbers as the original.
3. Open the archive's manifest: row counts match the database
   (`SELECT count(*)` on two tables of your choice, filtered by municipality).
4. Delete `noetinger-copia` from the operator screen: it asks for suspension, an
   export and the typed name; afterwards no row with its id remains in any table, and
   the original Noetinger is untouched.

Pass: every command is green and the four manual checks behave as described.

## Other notes

- Deletion is irreversible by design; the tests and the manual check run only against
  demo data.
- The archive format is documented in `docs/` as part of the task, since another
  installation has to be able to read it.
- Out of scope: partial exports per dashboard, scheduled exports, merging two
  municipalities.
