# Task 20: Digitalization of procedures: how many can be done online, and with CiDi

Priority: **high** (chosen by the product owner on 2026-11-25).
Read first: `docs/cidi/reference.md` §2 (the three levels) and §6. This task needs **no CiDi
connection and no knowledge of its technical interface**: it records, per procedure, whether people
sign in with CiDi to do it, and measures digitalization.

## Task description

The Procedures dashboard is an inventory (`dashboards/procedures`): each procedure has a channel
(`in_person`, `online`, `both`), an address where it is done online and the requirements it asks
for, each one on paper or digital. It already reports `procedures.online` and
`procedures.online_ratio`. A mayor asked "how much of the municipality's paperwork can a resident do
from home?" gets only "has an online channel", which says nothing about whether the resident still
has to print and bring a copy, and nothing about the provincial sign-in (CiDi) that most online
procedures in Córdoba now use. This task adds the two missing facts and the figures they allow.

- **What a procedure asks to sign in.** New attribute `cidi_level`: empty (people do not sign in with
  CiDi, or it is not known), `1`, `2` or `3`, the levels of `docs/cidi/reference.md` §2
  (Confirmado, Verificado, Autenticado). A procedure that is in person only cannot have a level
  (database `CHECK` and API validation, error in Spanish).
- **Fully digital** is a *computed* property, never typed: the procedure is active, its channel is
  `online` or `both`, it has an online address, and **no mandatory requirement is asked on paper**.
  (A requirement whose `format` is `paper` and `mandatory` is true makes a procedure not fully
  digital, because the resident still has to bring it.) `both` counts: the resident *can* do it
  entirely online; the figure answers "could", not "do".
- **Indicators** (all `aggregate=True`, none `reconstructible`: they depend on how the inventory
  stands today, like the existing ones):
  - `procedures.cidi`: active procedures with a `cidi_level`.
  - `procedures.cidi_ratio` (unit `ratio`): of the active procedures that can be started online
    (`online` or `both`), the share with a `cidi_level`. No value when there are none.
  - `procedures.digital`: active procedures that are fully digital.
  - `procedures.digital_ratio` (unit `ratio`): of all active procedures, the share fully digital.
  Names (Spanish, in the module's `INDICATORS` and in `overview.indicators.<key>` of `es-AR.json`,
  which a test compares): "Trámites con ingreso por CiDi", "Proporción de trámites en línea que usan
  CiDi", "Trámites 100 % digitales", "Proporción de trámites 100 % digitales". When a ratio has no
  denominator, do what `procedures.online_ratio` does today and keep that behaviour in the tests.
- **Summary**, monthly report and public page: the summary page gains a card with the four figures
  and a table "por nivel de CiDi" (counts per level, plus "sin CiDi"); the monthly report gets the
  same table through `report_tables` (counts only, no free text, no personal data); the indicators
  can be published on the public page like any `aggregate` one (task 05) and the existing tests of
  publication must still pass.
- **Where the data is entered.** The procedure form gets a select "Ingreso con CiDi" (options below)
  and the list shows a column and a filter for it; the CSV export gets the column; the list also
  marks "100 % digital" with a badge and a help text explaining the rule. Every named table column
  uses `<HelpTh>` (project rule).

## How to judge completion

Setup: database up, `uv run alembic upgrade head` (the next free migration number),
`uv run gobernar360 seed-demo --reset`, API and web app running.

Automated, all must pass:

- `cd backend && uv run pytest tests/procedures tests/platform` — includes tests for: a procedure
  with channel `in_person` and a `cidi_level` is rejected (API and database); levels 0 and 4 are
  rejected; a procedure `online` with a URL and only digital requirements is fully digital; one with
  a mandatory paper requirement is not; one with an optional paper requirement is; one with channel
  `both` and no URL is not; an inactive procedure counts nowhere; `cidi_ratio` is computed only over
  online-capable procedures and is absent (not zero) when there are none; the four indicators are in
  the catalogue with the right units and `get_summary` returns exactly those keys; the CSV has the
  column and its values; the report table has no row with free text; the isolation test (another
  municipality's procedures do not count); the existing procedure tests still pass unchanged.
- `cd backend && uv run pytest && uv run pytest --cov` (≥ 95 % per file), `uv run ruff check . &&
  uv run ruff format --check . && uv run lint-imports`.
- `cd frontend && npm test -- --run && npm run test:coverage && npm run lint && npm run build &&
  npm run e2e` — includes a spec in the procedures e2e that sets a level on a procedure and sees
  the summary change. Screen snapshots are reviewed before `-u` is accepted
  (`dashboards/helpKeys.test.ts`, `tableHeaders.test.ts` and the indicator-name test must pass).

By hand, as `admin@noetinger.test`:

1. Open Procedures → Resumen: the four new figures and the "por nivel de CiDi" table are there and
   agree with a count you do by eye on the list (demo data has a mix of levels, in-person-only
   procedures and some paper requirements).
2. Edit an online procedure: set "Nivel 2 – Verificado". The `cidi` count goes up by one; the
   procedure's badge reads as set.
3. Try to set a level on an in-person-only procedure: the form refuses with a clear message.
4. Add a mandatory requirement on paper to a procedure that was "100 % digital": the badge goes
   away and `digital` goes down by one. Mark that requirement optional: it comes back.
5. Download the CSV: the CiDi column is there. Close the month's report: the table is in it.
6. As `admin@comuna-demo.test` the figures are Comuna Demo's own.

Pass: every command is green and the six manual checks behave as described.

## Other notes

- Suggested copy for the select ("Ingreso con CiDi"): "No usa CiDi o no se sabe"; "Nivel 1 –
  Confirmado: cuenta con correo confirmado"; "Nivel 2 – Verificado: identidad verificada (DNI,
  selfie o Clave Fiscal)"; "Nivel 3 – Autenticado: firma digital". Help for "100 % digital": "Se
  puede iniciar en línea, tiene dirección web y no pide ningún requisito obligatorio en papel."
- Add to the demo a procedure source "CiDi – Centro de Documentación Digital" (level `provincial`)
  and use it for a requirement like "Copia del DNI", so the inventory shows what the province
  already holds. This is data only; no figure depends on it.
- A level means "the minimum the procedure asks": a level 2 account can do a level 1 procedure.
  Nothing in the code compares levels.
- Out of scope: connecting to CiDi, checking that the address really works, counting how many
  residents did the procedure online, a requirement-level "obtained from CiDi" figure.
