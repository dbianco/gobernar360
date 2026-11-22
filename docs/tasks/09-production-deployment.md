# Task 09: Production deployment, backups and verified restore

## Task description

gobernar360 only runs in development mode: a database container, the API with
auto-reload and the Vite dev server. There is no way for a municipality or a provincial
IT office to install it on a server and trust it with their records. This session
makes it a self-hostable product: one command brings up a production stack, and its
backups are proven to restore.

The centre of the work is operational confidence, shown by tests that run the real
stack rather than by documentation:

- **Images.** Multi-stage, non-root container images for the API and for the web app
  (static build served by a web server that also proxies `/api`, so the browser sees a
  single origin as the session cookie requires). Small, reproducible, with a health
  check each.
- **Production stack.** A `docker-compose.prod.yml` with database, API, web and a
  reverse proxy terminating HTTPS (automatic certificates when a domain is set, a
  self-signed one for local trials). Secrets come from environment or secret files and
  the stack refuses to start with the development default passwords.
- **Safe start-up.** Migrations run once as the owner role in a dedicated step before
  the API starts; the API itself only ever connects as the restricted role, so
  row-level security applies in production exactly as in tests. A start-up check fails
  loudly if the API role owns tables or can bypass row-level security.
- **Hardening.** Secure cookies, security headers and a content security policy that
  the app actually passes, request size limits, rate limiting on sign-in, structured
  logs without personal data, and a `/api/health` that distinguishes "process up" from
  "database reachable and migrated".
- **Backups.** A scheduled backup service producing encrypted, timestamped database
  dumps with retention (daily, weekly, monthly), to a local volume or any S3-compatible
  storage, plus `gobernar360 backup` and `gobernar360 restore` commands.
- **Verified restore.** A test brings the production stack up, loads the demo data,
  takes a backup, destroys the database volume, restores, and checks that sign-in
  works, row counts match and row-level security is still enforced (policies and role
  grants are part of what is restored). A backup that cannot be restored fails the
  build.
- **Upgrades.** A documented and tested upgrade path: start the stack on the previous
  migration, load data, upgrade to the current images, and verify the data is intact.
- **Continuous integration.** A workflow that runs lint, the three test suites, builds
  both images and runs the stack smoke test and the restore test on every push.
- **Operator guide.** Install, configure, first operator account, backup, restore and
  upgrade, written for someone who administers servers but does not know the code.

## How to judge completion

Automated, all must pass:

- `cd backend && uv run pytest && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build && npm run e2e`
- `./deploy/test-stack.sh` — builds the images, starts the production stack on local
  ports, waits for health, runs the Playwright suite against it through the HTTPS
  proxy, then runs the backup, destroy, restore cycle and the upgrade cycle. Exit code
  0 is a pass.
- The CI workflow file exists and runs the same steps; `act` or a push shows it green.

By hand:

1. `cp deploy/.env.example deploy/.env` and run
   `docker compose -f docker-compose.prod.yml up -d` without changing the passwords:
   the stack refuses to start and says why. Set real values: it starts.
2. Open `https://localhost` (self-signed): the app loads, sign-in works, and the
   browser console shows no content security policy violations while using two
   dashboards.
3. `docker compose -f docker-compose.prod.yml exec api id` shows a non-root user, and
   connecting to the database as the API role and running
   `SELECT count(*) FROM people` with no tenant set returns 0.
4. Run a backup, remove the database volume, restore: the demo accounts sign in and
   the dashboards show their data.
5. Follow the operator guide from a clean checkout on a machine that never ran the
   project: it works without reading the source.

Pass: every command is green and the five manual checks behave as described.

## Other notes

- Everything runs on one machine with Docker; no cloud account is needed. S3-compatible
  storage is tested against a local container.
- The database image is currently pinned to `linux/amd64`; this task should make the
  stack run natively on both amd64 and arm64.
- Out of scope: Kubernetes manifests, multi-node high availability, managed-cloud
  templates.
