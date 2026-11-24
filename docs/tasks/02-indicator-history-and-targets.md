# Task 02: Indicator history, targets and cross-dashboard indicators - DONE

## Task description

Every headline indicator in gobernar360 is computed at the moment it is shown
(`DashboardModule.get_summary(ctx, today)`) and nothing is kept. A mayor can see that
there are 4 delayed projects today, but not whether that is better or worse than last
month, or how far it is from what the municipality set out to achieve. The monthly
status light is set by hand with no numbers next to it.

This session adds memory and goals to all five dashboards at once, as a platform
feature, so that a future dashboard gets it without code of its own:

- **Monthly snapshots.** A platform table stores the value of every indicator of every
  enabled dashboard at the close of each month. A command
  (`gobernar360 snapshot-indicators`) takes the snapshot for every municipality, each
  inside its own tenant-scoped transaction. It is idempotent, and it can rebuild past
  months (`--from 2026-01`) by asking each dashboard for its indicators as of that date.
  Where a dashboard cannot honestly reconstruct the past, the indicator is declared
  "not reconstructible" and the month is left empty rather than filled with today's value.
- **Indicator catalogue.** Dashboards declare their indicators (key, unit, whether
  higher is better, whether it can be reconstructed) through the registry contract, so
  the platform never imports a dashboard.
- **Targets.** Dashboard administrators set a target per indicator and year. The
  platform computes the deviation and whether the indicator is on track, taking the
  direction (higher or lower is better) into account.
- **Evolution.** Each dashboard summary and the general overview show, per indicator:
  current value, change against the previous month and against the same month last
  year, a twelve-month series and the target line. The status strip shows the numbers
  of the month next to each light.
- **Cross-dashboard indicators.** The overview adds indicators that combine dashboards
  (for example procedures available online per economic actor, or social deliveries
  against active projects in the same axis), defined in the platform from catalogue
  keys, and shown only to members who can see every dashboard involved.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`
(the demo data now includes twelve months of history and targets), API and web app
running.

Automated, all must pass:

- `cd backend && uv run pytest` — includes tests for: the snapshot command run twice
  gives the same rows; a rebuilt past month matches the value the API returned on that
  date (pinned clock); a municipality never gets snapshot rows of another; deviation
  sign for "lower is better" indicators; a non-reconstructible indicator stays empty
  when rebuilding; a cross-dashboard indicator is hidden from a member lacking one of
  its dashboards; a dashboard registered only in the test (`demo_dashboard` fixture)
  gets snapshots without platform changes.
- `cd backend && uv run ruff check . && uv run lint-imports` — the platform still does
  not import any dashboard.
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`

By hand, as `admin@noetinger.test`:

1. Open the Projects summary: every headline card shows the change against last month
   and a twelve-month sparkline; opening a card shows the series with its target line.
2. In the dashboard's parameters set a target for "delayed projects" lower than the
   current value: the card turns to "off track" and shows the deviation.
3. The general overview shows the cross-dashboard indicators; signed in as a user with
   access to only one dashboard they are absent.
4. Run `uv run gobernar360 snapshot-indicators --from 2026-01` twice and confirm the
   row count in `indicator_snapshots` does not change the second time.

Pass: every command is green and the four manual checks behave as described.

## Other notes

- Task 05 (monthly report and public page) reads these snapshots; do this one first.
- The snapshot table is tenant data and must be covered by row-level security like
  every other tenant table.
- Out of scope: forecasting, alerts by email (task 01), per-area breakdown of indicators.
