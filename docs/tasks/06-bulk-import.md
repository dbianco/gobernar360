# Task 06: Bulk data import

## Task description

Everything in gobernar360 is typed in by hand, one record at a time. A municipality
that already keeps its residents, projects or measurements in spreadsheets will not
retype thousands of rows, so today it cannot really start using the system. This
session builds an import pipeline that a non-technical municipal employee can use
without fear of damaging what is already loaded.

The centre of the work is the pipeline and its guarantees, shared by every dashboard:

- **Staged import.** Upload a CSV or XLSX file, then: detect encoding, separator and
  header row; map file columns to fields (suggested automatically, adjustable, and
  remembered as a named template); validate; preview; apply. Nothing touches real
  tables before the last step. An import can be abandoned at any stage.
- **Validation with a per-row report.** Every row is checked with the same rules the
  API applies to a hand-typed record (the rules are reused, not rewritten). The preview
  shows how many rows will be created, updated, skipped and rejected, each rejected row
  with its line number, field and reason in Spanish, downloadable as a file to correct
  and re-upload.
- **People deduplication.** Rows about people are matched against the shared people
  registry by document number, and inside the file itself. A match reuses the person;
  conflicting data (same document, different name) is shown for the user to decide per
  row or with one rule for the whole file. Importing a person into Social who already
  exists in Economic must not duplicate them.
- **Reference resolution.** Values like an area, an axis or a benefit type are matched
  to existing catalogue entries ignoring case and accents; unknown ones can be created
  as part of the import if the user has the level to do so.
- **Atomic apply and undo.** Applying is one transaction: all accepted rows or none.
  Every import is recorded (who, when, file name, counts) and can be undone as a whole
  as long as its records were not modified afterwards; the audit log shows both.
- **Dashboard contract.** Each dashboard declares its importable entities through the
  registry (fields, validation, how to find an existing record), so the pipeline lives
  in the platform and imports no dashboard. This session delivers importers for people
  (Economic and Social), projects with milestones, environmental monthly values and
  procedures with requirements.
- **Scale.** A 20,000-row file validates and applies without timing out the request:
  the work runs in the background with visible progress.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`,
API and web app running. Sample files with made-up data, including deliberately broken
ones, are in `backend/tests/imports/files/`.

Automated, all must pass:

- `cd backend && uv run pytest` — includes tests for: Latin-1 and UTF-8 files with `;`
  and `,` separators; each validation error reported with the right line; a duplicate
  inside the file; a person already in the registry is reused, not duplicated; a
  failure in the last row leaves no row applied; undo removes exactly what the import
  created and refuses when a record was edited afterwards; a member with viewer level
  cannot import; an import can never write into another municipality; a dashboard
  registered only in the test can declare an importable entity.
- `cd backend && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
  — includes a spec that imports a file end to end.

By hand, as `carga@noetinger.test`:

1. Import `people_with_errors.csv` into Social: the preview reports the created,
   reused and rejected counts stated in the file's companion `.expected.json`; download
   the error report and check the line numbers.
2. Apply it. The people list grows by exactly the "created" count; a person who was
   already in Economic appears once in the registry.
3. Import the same file again: everything is reported as already existing, nothing is
   created.
4. Undo the first import from the import history: the people list returns to its
   previous count and the audit log shows the import and its undo.
5. Import `people_20000.csv`: a progress indicator is shown and the import completes.

Pass: every command is green and the five manual checks behave as described.

## Other notes

- Every sample file contains only made-up people and document numbers.
- Out of scope: scheduled or automatic imports from external systems, importing from
  Google Sheets, export-then-reimport round trips (task 08 covers full exports).
