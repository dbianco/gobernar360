# Task 03: Complaints and citizen service dashboard - DONE

## Task description

gobernar360 has a Procedures dashboard, but it is an inventory: it does not follow
individual cases. This session adds the dashboard a mayor usually looks at most: every
complaint a resident makes (a broken street light, uncollected waste, a pothole),
followed one by one from the moment it is received until it is solved, with the time
it took measured honestly.

It is a new dashboard module (`dashboards/complaints`, key `complaints`) that follows
the existing module contract, but the centre of the work is the case engine, which no
other dashboard has:

- **Case lifecycle.** A complaint moves through explicit states (received, assigned,
  in progress, waiting for the resident, resolved, closed, rejected, reopened). Only
  valid transitions are accepted, each one records who did it, when and with what note,
  and the full timeline is shown on the case. A resolved complaint can be reopened and
  keeps its history.
- **Service clock.** Each complaint type has a target resolution time in business
  days. The clock uses a per-municipality calendar of working days and holidays, stops
  while the case waits for the resident and resumes afterwards. Every open case shows
  time used, time left and whether it is on time, at risk or overdue.
- **Assignment.** Types route to a responsible area by default; an editor can reassign.
  Each area has its queue, ordered by how close cases are to their deadline.
- **Who complains.** A complaint can be linked to a person in the shared people
  registry by document number, reusing the platform lookup, or left anonymous.
- **Zone.** Each complaint has an address and a zone from a list the municipality
  defines.
- **Analysis.** The summary shows: open cases by state, received against resolved per
  month, median and 90th percentile resolution time by type and by area, share resolved
  on time, ageing of the backlog, repeated complaints (same type and address within a
  period) and the zones and types with most cases. CSV export of cases and of the
  per-area report.
- **Overview.** The module contributes its headline indicators (open, overdue, share
  resolved on time, median resolution time) to the general overview.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`
(the demo data now includes several hundred made-up complaints over twelve months),
API and web app running. The operator enables "Reclamos" for Noetinger.

Automated, all must pass:

- `cd backend && uv run pytest tests/complaints tests/platform` — includes tests for:
  every invalid transition is rejected; the clock excludes weekends, holidays and
  waiting time (cases with pinned dates); reopening keeps the timeline; resolution
  percentiles on a known data set; a viewer cannot change state; a municipality cannot
  read or reference another's complaints, types or areas.
- `cd backend && uv run ruff check . && uv run lint-imports` — `complaints` is listed
  in both import contracts and imports no other dashboard.
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
  — includes `e2e/complaints.spec.ts` taking one complaint from received to closed.

By hand, as `admin@noetinger.test`:

1. Create a complaint for a person found by document number; it appears in the queue
   of the area its type routes to, with its deadline.
2. Move it to "waiting for the resident" and back: the timeline shows both steps and
   the time left did not shrink while it waited.
3. Try to close a complaint that was never resolved: the action is not offered and the
   API refuses it.
4. The summary's median resolution time by type matches the same figure computed from
   the CSV export.
5. As `lectura@noetinger.test` (after being granted the dashboard) cases are visible but
   no change is possible.
6. As `admin@comuna-demo.test` none of Noetinger's complaints are visible.

Pass: every command is green and the six manual checks behave as described.

## Other notes

- All complaints, people and addresses are made-up demo data.
- Works on its own. If task 07 (geographic layer) is done first, the zone becomes a
  polygon and complaints appear on the map; if not, zone is a plain list.
- Out of scope: a public form for residents to submit complaints, notifications to the
  resident, attachments.
