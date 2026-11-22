# Task 05: Monthly management report and public transparency page

## Task description

Everything in gobernar360 is behind a sign-in and changes as data changes. A
municipality cannot hand the council or the press "the state of management in October",
and cannot show residents anything at all. This session adds both: a monthly report
that is closed and kept, and a public page where the municipality decides what to show.

This is the first time data leaves the signed-in, tenant-scoped area, so the centre of
the work is doing that safely:

- **Closing a month.** A municipality administrator closes a month. That freezes a
  report made of: each dashboard's status light, its headline indicators with change
  against the previous month and target (from the snapshots of task 02), project
  milestones reached and overdue in the month, and a written comment per dashboard. A
  closed report never changes when data is edited later. It can be reopened only
  explicitly, which is recorded in the audit log and produces a new version.
- **PDF.** The closed report is rendered on the server to a PDF with the municipality's
  name, charts and tables, readable when printed in black and white (lights carry their
  mark and name, never colour alone), with correct page breaks and Spanish number and
  date formats. Generation is deterministic: the same report gives the same document.
- **Publication model.** Publishing is opt-in at three levels: the municipality turns
  the public page on and picks its public address; per dashboard; per indicator. What
  is published is a separate, copied set of rows written at publication time, so the
  public side never queries live tenant tables.
- **Public page.** `/p/<municipality-slug>` works without a session: the published
  indicators with their evolution, published lights and the list of published monthly
  reports to download. It is served by routes with no access to tenant data: they read
  only the published tables, are rate limited and cacheable.
- **No personal data, by construction.** Only indicators declared as aggregate in the
  indicator catalogue can be published; the Social dashboard's reserved text and
  anything from the people registry cannot be selected. Small counts below a threshold
  the municipality sets are shown as "fewer than N".
- **Unpublishing.** Turning the page off, or unpublishing an indicator or a report,
  takes effect immediately and removes the copied rows.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`
(Noetinger has closed reports and a public page; Comuna Demo has neither), API and web
app running.

Automated, all must pass:

- `cd backend && uv run pytest` — includes tests for: a closed report is unchanged
  after its source data is edited; reopening creates a new version and an audit entry;
  the PDF of a fixed report is byte-stable or matches a stored text extraction; public
  routes return 404 for a municipality that did not turn the page on; public routes
  never expose an unpublished indicator; an indicator not declared aggregate cannot be
  published; small counts are masked; unpublishing removes access at once; public
  routes run with no tenant set and no session; one municipality's slug never returns
  another's rows.
- `cd backend && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
  — includes a spec that opens the public page in a browser context with no cookies.

By hand:

1. As `admin@noetinger.test` close last month, add a comment, download the PDF. Then
   change a project's progress and download again: the document is the same.
2. Print preview of the PDF in greyscale: every light is still identifiable.
3. Publish two indicators and the report. In a private browser window open
   `http://localhost:5173/p/noetinger`: exactly those two indicators and that report
   are there.
4. Request the public API for an indicator that was not published and for
   `/p/comuna-demo`: both answer not found.
5. Unpublish one indicator and reload the private window: it is gone.
6. Search the public page and the PDF for any name or document number from the demo
   people registry: none appear.

Pass: every command is green and the six manual checks behave as described.

## Other notes

- Requires task 02 (indicator snapshots and catalogue).
- All data is made up. The point of the "no personal data by construction" rule is that
  it would still hold with real data.
- Out of scope: custom themes per municipality, comments from residents, open-data
  downloads in bulk.
