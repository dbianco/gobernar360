# Task 04: Internal management — cabinet meetings and commitments - DONE

## Task description

The dashboards tell a mayor what is going wrong, but not what was agreed to do about it.
That lives in someone's notebook after each cabinet meeting. This session adds the
missing link: meetings, the commitments taken in them, who owes each one and by when,
shown next to the thing they are about. A dashboard with a red light for October should
have, right beside it, what was agreed and who has not delivered.

It is a new dashboard module (`dashboards/cabinet`, key `cabinet`). The hard part, and
the centre of the session, is connecting it to the rest without breaking the rule that
dashboards never import each other:

- **Linkable subjects.** A commitment can point at a dashboard's month (its status
  light) or at a specific record of another dashboard, starting with a project. This is
  done through a new platform contract: a dashboard declares in the registry which of
  its records can be linked, how to search them, how to label them and who may see
  them. The cabinet module only talks to that contract. Links are checked against the
  tenant on write, because foreign keys are not covered by row-level security, and a
  link to a record the reader cannot access shows that something is linked without
  revealing what.
- **The reverse view.** The platform exposes "commitments about this subject", so the
  status strip of any dashboard and the project detail page show their open
  commitments without knowing the cabinet module exists.
- **Meetings.** Date, attendees, agenda items, notes and the commitments that came out
  of each item. A meeting can be closed, after which its minutes are frozen and can be
  downloaded.
- **Commitments.** Owner (a member of the municipality), due date, state (open, done,
  dropped, overdue computed from the date), progress notes with their history, and the
  meeting where it was taken. A commitment not done by the next meeting is carried over
  and keeps count of how many times it was postponed.
- **Generated agenda.** Preparing a new meeting proposes its agenda automatically:
  dashboards whose latest light is red or yellow, commitments overdue or due before the
  meeting, and items carried from the previous one. The person preparing it accepts,
  drops or reorders them.
- **Follow-up.** Summary with commitments by state and by owner, share delivered on
  time, the most postponed ones, and each person's "my commitments" view. Headline
  indicators go to the general overview. CSV export.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`
(the demo data now includes several meetings with commitments linked to projects and to
red lights), API and web app running.

Automated, all must pass:

- `cd backend && uv run pytest tests/cabinet tests/platform tests/projects` — includes
  tests for: a commitment cannot link to another municipality's project; a member
  without access to Projects sees the commitment but not the project's name; a closed
  meeting cannot be edited; carrying over increments the postponed count once; the
  generated agenda for a pinned date contains exactly the expected red lights and
  overdue commitments; a dashboard registered only in the test can declare a linkable
  record and receive commitments with no change to the cabinet module.
- `cd backend && uv run ruff check . && uv run lint-imports` — `cabinet` is in both
  contracts and imports neither `projects` nor any other dashboard.
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
  — includes `e2e/cabinet.spec.ts`.

By hand, as `admin@noetinger.test`:

1. Set the Environment light for last month to red. Start a new meeting: the proposed
   agenda includes that dashboard and every overdue commitment.
2. From an agenda item create a commitment linked to a project, with an owner and date.
   Open that project's detail page: the commitment is shown there.
3. Open the Environment summary: the red month shows its commitments beside the light.
4. Close the meeting and download the minutes; editing the meeting is no longer possible.
5. Start the next meeting without completing the commitment: it is carried over and
   shows it was postponed once.
6. As a user with the cabinet dashboard but not Projects, the commitment is visible and
   its link reads as a project the user cannot open.

Pass: every command is green and the six manual checks behave as described.

## Other notes

- The linkable-subject contract is platform code and is what makes this more than
  another list-and-form dashboard; a solution that imports `projects` models from
  `cabinet` is a fail even if the screens work.
- If task 01 exists, overdue commitments can join the notification command; not
  required here.
- Out of scope: calendar integration, voting, attachments.
