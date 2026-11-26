# TODO: what is left, how to know it is finished, and what to add

Written on 2026-11-25, after tasks 04 and 07 were merged into `main` (`d5dc4d8`).
Tasks 01 to 05 and 07 are built (`- DONE` in their titles). This file lists everything else:

0. **Priority work with a brief ready to build** (19, 20, 21: CiDi and provincial geography).
1. Pending tasks that already have a brief (06, 08, 09).
2. Fixes and decisions that came out of the reviews of the last merge.
3. New tasks proposed from what similar platforms offer (each one is a candidate for its own
   `docs/tasks/NN-*.md` brief).

**How "complete" is judged everywhere:** the brief's "How to judge completion" section is the
contract. A task is closed when its automated commands are green *and* its manual checks were
walked through by a person on the seeded demo data. The common gate, for every item below, is:

```bash
cd backend && uv run pytest --cov && uv run ruff check . && uv run ruff format --check . && uv run lint-imports
cd frontend && npm test -- --run && npm run test:coverage && npm run lint && npm run build && npm run e2e
```

Reference figures on 2026-11-26 (before it: 2045, 1253 and 95): backend 2448 tests, 99 % coverage;
frontend 1381 tests, 99.9 % of statements and 99.4 % of branches; every file of both is at 95 % or
more; e2e 104 specs. A task must not lower coverage under 95 % per file, and must add its own
cross-municipality isolation test for every new tenant table.

When an item is finished, put ` - DONE` after its title, as the other task files do, and update
the DONE list in `CLAUDE.md`.

---

## 0. Priority: briefs written on 2026-11-25 (CiDi and provincial geography)

Chosen by the product owner. Their briefs are complete and an agent without internet can build
them from the repository: the CiDi documents are in `docs/cidi/`, the IDECOR and CONAE services
(checked live the same day, with sample answers) in `docs/idecor/`.

| # | Task | State | Needs from outside |
|---|---|---|---|
| 21 | [Official provincial geography](21-idecor-official-layers.md): urban radius as a zone, health and school points, CONAE satellite background - DONE | built on 2026-11-26 | the import against the live service and the satellite tiles have not been seen by anybody (built without internet) |
| 20 | [Digitalization of procedures](20-procedures-digitalization.md): CiDi level per procedure, "100 % digital" indicators - DONE | built on 2026-11-26 | nothing |
| 19 | [Notices to residents through CiDi](19-cidi-resident-notices.md) - PARTIAL | **Phase A built on 2026-11-26; Phase B blocked** | the province's technical specification, which is **not public**: see `docs/cidi/questions-for-province.md`; also the adhesion decision in section 2 below |

Suggested order: **21 → 20 → 19A**, in parallel if two agents work (they touch different files;
21 and 19 both add a migration, so take the next free number when merging). 19B starts only when a
person has written `docs/cidi/integration-spec.md`.

Corrections to what was said earlier in the conversation:
- The satellite imagery of Noetinger that GeoMiner uses comes from **CONAE**, not from IDECOR.
  IDECOR provides the vector layers.
- There is **no public CiDi technical specification** (neither protocol nor API). What exists is
  the legal and procedural text, now in `docs/cidi/source/`. Everything that depends on the
  interface (19B, 22, 23, 24) waits for the province's answer.

Decisions taken by the product owner on 2026-11-25 (C5 and C6 later):
- **C1. Each municipality adheres to CiDi by itself**, and configures its own connection in the app
  (task 19 builds the settings: adhesion state, connection data, encrypted write-only secrets). Still
  to ask the Province whether it accepts a third-party system run for the municipality (question 1).
- **C2. The IDECOR and CONAE data are used as MIT-licensed** (kept with attribution; recorded in
  `docs/idecor/README.md`).
- **C4. The only wording for a notice is "Entregado a CiDi"**; never "notificado" or any legal claim.
- **C5. Notices to residents go by email by default** (confirmed on 2026-11-26): a resident with an
  email in the registry is told when their complaint is resolved or rejected.
- **C6. A CiDi connection is complete, for now**, with the adhesion approved, the system name, the
  publication URL and the contact (confirmed on 2026-11-26). The secrets join the list when the
  Province's specification says which ones there are.

For task 09 (noted in its brief on 2026-11-26):
- **C3. The content-security policy of task 09** must allow `geotematico01.conae.gov.ar` for tiles
  (task 21) and the OpenStreetMap tile hosts already used; add both to 09's hardening checklist.

---

## 1. Pending tasks with a brief

Suggested order: **08 (rest) → 09 → 06**. Export/restore and a real deployment are what a
municipality needs before it trusts the system with its records; bulk import is what it needs
to start using it, but it is also the largest.

| # | Task | State | Size | Depends on |
|---|---|---|---|---|
| 08 | Municipality lifecycle | suspend/resume done; **export, restore, delete, isolation audit pending** | large | none |
| 09 | Production deployment, backups, verified restore | not started | large | 08 helps (export is a second kind of backup); needs Docker |
| 06 | Bulk data import | not started | very large | none; benefits from 08's archive code for undo |

### 08, rest: export, restore, delete, isolation audit
Brief: `08-municipality-lifecycle.md`.
- **Finished when:** `gobernar360 export-municipality` and `import-municipality` round-trip the demo
  municipality and a test compares every dashboard's summary, lists and CSV between the original and
  the copy; the isolation audit walks the catalogue (forced RLS, policy and grant on every table with
  `municipality_id`) and runs every list endpoint as municipality A while B holds data.
- **Validate by hand:** the brief's four checks. In particular, open the manifest and compare two
  table counts with `SELECT count(*)`, and delete `noetinger-copia` and search every table for its id.
- **Notes for this repo:** the last two merges added tables (cabinet, commitments, notices, zones,
  `record_zones`, map settings). Export must derive its table list from model metadata, so check that
  `record_zones` (written only by triggers) is **rebuilt** on restore rather than copied, and that
  zone versions keep their `valid_from`/`retired_at`. Commitments point at members by user id: remap
  them. Linked subjects have no foreign key, so remap `ref` ids too (projects). The complete export
  must also cover the monthly reports and public-page copies. Passwords, sessions and tokens never
  go into the archive.
- **Risk:** deletion is irreversible; run every delete test and check only against demo data.

### 09: production deployment, backups, verified restore
Brief: `09-production-deployment.md`.
- **Finished when:** `./deploy/test-stack.sh` exits 0 (images, HTTPS proxy, Playwright against the
  stack, backup → destroy volume → restore, upgrade from the previous migration) and the CI workflow
  runs the same.
- **Validate by hand:** the brief's five checks. Add a sixth specific to the geographic layer:
  after the restore, `SELECT count(*) FROM record_zones` equals the count before, and the
  triggers still assign a zone to a new record (triggers and the PostGIS extension are part of what is
  restored, not only rows).
- **Notes for this repo:**
  - The database image is `postgis/postgis:16-3.4` pinned to `linux/amd64`. It must run on arm64.
  - The read-only role `gobernar360_public` has a **known default password** (`db/init`/migration);
    the stack must refuse to start with it (the brief already says so for development defaults).
  - The map background providers are fetched by the visitor's browser: the content security policy
    has to allow the tile hosts in `platform/geo/backgrounds.py` (and nothing else), or the maps go
    blank in production only.
  - Add `geotematico01.conae.gov.ar` (satellite tiles, task 21) to that list.
  - Verify in the real stack that the OIDC provider settings and `APP_URL` are right for links
    in emails.

### 06: bulk data import
Brief: `06-bulk-import.md`.
- **Finished when:** the sample files in `backend/tests/imports/files/` give exactly the counts in
  their `.expected.json`; an import of 20,000 rows completes in the background with visible progress;
  undo removes exactly what the import created and refuses if a record was edited afterwards.
- **Validate by hand:** the brief's five checks, as `carga@noetinger.test`.
- **Notes for this repo:** add **located records** to the brief's list now that the geographic layer exists
  (a latitude/longitude pair per row, validated with `geo/geojson.location_geometry`, zones assigned
  by the existing triggers). Cabinet commitments are not worth importing. Rows about people
  and households go through the people registry and must respect the Social rule: viewers never see
  what an import brought in about households.
- **Risk:** large; split into pipeline (platform) and one importer per dashboard, and merge in that
  order.

---

## 2. Fixes and decisions from the last review

None of these blocks what is merged. `DONE` says that it was built on 2026-11-26 as the proposed
handling says, with the test its last column asks for; what was decided along the way is under
the table.

| ID | Finding | Decide | Proposed handling | Done when | State |
|---|---|---|---|---|---|
| F1 | The owner of a cabinet commitment can change its due date and completion date, and the headline indicators (`cabinet.overdue`, `cabinet.on_time_ratio`) follow them | product | Freeze the date agreed in the meeting (`agreed_due_date`) and compute on-time against it; the owner can still ask for a new date, which creates a visible history entry | test: an owner who moves the date does not change `on_time_ratio`; history shows the move | DONE |
| F2 | Removing a member leaves their open commitments counted as pending, with nobody told | product | When a member is removed, list their open commitments for the administrator and offer to reassign them; until then show them as "owner left" | test: removing a member with two open commitments reports both; reassigning updates the owner and tells the new one | DONE |
| F3 | `base_version` is optional on the zone `PATCH`, so a client that skips it overwrites a newer edit | code | Make it required (`409` when stale); the web app already sends it | test: patch without it is `422`; stale one is `409` | DONE |
| F4 | The zone import body has no size limit | code | Cap bytes (not only the feature count) before parsing | test: a body over the cap is refused with a clear error | DONE |
| F5 | The Tracestrack tile address was written from memory | check with internet | Open the map with that background and confirm tiles and attribution; fix the template or drop the provider | tiles load in the browser; attribution matches the provider's terms | open: needs internet |
| F6 | `gobernar360_public` ships with a known password | code (task 09) | Refuse to start in production with it | covered by task 09 manual check 1 | DONE (the check; the stack is task 09) |
| F7 | `GET /api/members` lists every member to any member | product | Decide whether a plain viewer should see the whole directory; if not, limit to name only | decision recorded in `CLAUDE.md` | DONE |
| F8 | A viewer can compare two `as_of` values on the Social breakdown to recover a hidden small count | product | Round `as_of` for viewers to whole months, or fix the suppressed cells for the period | test: two requests a day apart give the same suppressed cells for a viewer | DONE |
| F9 | `times_postponed` reaches the owner of a commitment who has no cabinet access (a test says it is deliberate) | product | Confirm it is intended; if so, say so in the cabinet design doc | decision recorded | DONE |
| F10 | Figures for past periods include records that did not exist yet (zones are versioned, records are not) | code | Filter by `created_at <= as_of` in the breakdown | test: a record created next month is not in this month's breakdown | DONE |
| F11 | A point exactly on a shared border counts in both zones | doc | Say so in the zone screen help text and in `docs` | help text exists; `helpKeys` test passes | DONE |
| F12 | The map provider key is sent to every member's browser | doc | By design (the browser needs it); say in Configuración that the key must be restricted by domain at the provider | help text exists | DONE |
| F13 | The two review fixes (a dropped commitment revived as done, and a 500 on huge integer coordinates) are tested, but the manual checks of tasks 04 (6 checks) and 07 (5 checks) have **not** been walked through by a person | person | Walk both checklists on a fresh `seed-demo --reset` and note any difference | both checklists done; anything off becomes an issue | automated; a person still has to walk it |
| F14 | The frontend lockfile was built where some locked versions were unavailable (Mantine 9.8.1, msw 3.0.7, react-router 7.18.6 …); suites were run against the nearest versions | person | Run `npm ci` and the suites on the real lockfile, in CI or by hand | `npm ci && npm test -- --run && npm run build` green on the lockfile as committed | open: needs the real registry |
| F15 | Mutation testing has not been run on the cabinet, commitments or geographic code (target: 80 % of mutants killed; coverage target is already met) | code | Run `tests/run_mutmut.py` on `dashboards/cabinet`, `platform/commitments*`, `platform/geo`; write tests for survivors | survivors listed in the notes, score at or above 80 % | DONE: 96.2 % ([report](mutation-2026-11-26.md)) |
| C1 | The Province's technical specification for CiDi is not public; without it 19B cannot start. Adhesion is per municipality (decided) | person | Send `docs/cidi/questions-for-province.md`; the first municipality files its adhesion form (template: task 19); record the answers in it | answers filled in; `integration-spec.md` written | open: a person |
| F16 | The development database is at migration 0020 but has only the demo data from before it: one hand-made zone "Casco urbano" (`backend/demo_data/noetinger-zonas.geojson`) and no located records or meetings | person | Run `uv run gobernar360 seed-demo --reset` when ready (it deletes all dev data) | maps, breakdowns and the cabinet show data | open: a person |

What was decided along the way. F1, F2 and F10 were confirmed by the product owner on 2026-11-26:

- **F1** (confirmed): on-time figures use the date agreed in the meeting. It reverses what the
  cabinet design had recorded (the figures followed the owner's date). The agreed date only changes in the minutes of a meeting; the owner's new date is kept
  beside it and in the history.
- **F2** (confirmed, the API response too): removing a user (`DELETE …/users/{id}`) now answers `200` with what was left behind (`commitments`,
  `hidden`) instead of `204`. Informal commitments stay private: the administrator sees how many,
  not which; the person who gave each one is told and reassigns it.
- **F6** applies when `GOBERNAR360_ENVIRONMENT=production` or the session cookie is secure. The
  same check refuses the fake CiDi.
- **F7**: the directory stays open to members and carries names only.
- **F8**: a viewer's `as_of` is rounded to the month.
- **F9**: intended, and written in the cabinet design.
- **F10** (confirmed) goes by when the record was entered. A record of the past that is entered or imported
  late is therefore missing from the breakdowns of the periods before it was entered; task 06 has
  to decide whether an import may backdate `created_at`.
- **F13**: the eleven checks are browser specs now; nobody has signed them off by eye.
- **F5** and **F14** could not be closed without internet. Not available to the session that built
  this: fpdf2 2.9.0 (2.8.9 used), msw 3.0.7 (3.0.5) and @msw/url 0.1.3 (0.1.2). Playwright was
  1.64.1 instead of 1.65.1. The rest of both lockfiles was installed as written, and neither
  `package.json` nor `package-lock.json` was changed.

---

## 3. New tasks proposed from similar platforms

Searched: the CiDi platform of the Province of Córdoba (section 0 and 22 to 24), vendors of local-government software (OpenGov, ClearGov, Zencity, Esri's performance
dashboards, Catalis) and Argentine and Latin American public initiatives (the national *Tablero de
Gestión* for municipalities from País Digital, the national open-data guide for provinces and
localities, the *Programa Federal de Estado Abierto*, the digital participatory budget of Mendoza).
Findings are marketing and summary pages, so each proposal below is **a hypothesis to confirm with a
municipality**, not a requirement. Sources are at the end.

Each proposal has the same shape as the existing briefs: what it adds, why, and how it would be
judged. Numbers continue from 09.

| # | Proposal | Seen in | Size | Priority |
|---|---|---|---|---|
| 10 | Built-up area dashboard (GeoMiner) | the project's own plan | large | high: already agreed, waits for two answers |
| 11 | Budget execution and public budget | OpenGov, ClearGov, Mendoza | large | high |
| 12 | Open data catalogue | national guide, *Estado Abierto* | medium | high |
| 13 | Resident surveys feeding indicators | Zencity, ClearGov | medium | medium |
| 14 | Public service-request intake and tracking | 311-style portals, *Concepción Transparente* | medium | high |
| 15 | Government plan and objectives tracker | ClearGov strategic planning, *Estado Abierto* plan tracker | medium | medium |
| 16 | Field inspections with photos (installable app) | Esri field workflows | medium | medium |
| 17 | Alerts on targets and a weekly digest for the mayor | performance dashboards | small | medium |
| 18 | Participatory budget voting | Mendoza digital participatory budget | large | low until 11 exists |
| 22 | Verified resident identity with CiDi | CiDi levels (`docs/cidi/`) | medium | medium; unlocks 13, 14, 18 |
| 23 | Digital signature of minutes and reports | CiDi level 3 | medium | low until question 17 of `docs/cidi/questions-for-province.md` is answered |
| 24 | Staff sign-in with CiDi | CiDi, existing SSO (task 01) | small | low |

### 10. Built-up area dashboard ("Superficie edificada", with GeoMiner)
- **What:** a dashboard fed by the GeoMiner pipeline (`/Users/daniel/src/geominer`): parcels, building
  footprints and their estimated built area against what each parcel declares. It lets the municipality
  see where there is construction nobody declared. Parcels and footprints are located records (task 07),
  so maps and zone breakdowns come for free.
- **Open questions (from the user, still unanswered):** how the data gets in (a command that loads
  GeoMiner's database, or a file import), and who may see an individual parcel (it relates a person's
  property to a discrepancy: treat it as sensitive, like households).
- **Judged by:** a municipality that has run GeoMiner loads its parcels; the summary shows declared vs
  estimated area and the share of parcels with a gap; a viewer sees only zone totals with small counts
  hidden; another municipality sees nothing. Useful data now: `localities` in
  `geominer/config.py` only knows Noetinger (3,086 parcels, urban ones under 3,000 m²).
- **Validate by hand:** compare the total estimated area for one block with GeoMiner's own output.

### 11. Budget execution and public budget
- **What:** the municipality loads its budget by area and period (planned, committed, paid) and sees
  execution against plan, with a public page that shows where the money goes. The two big vendors
  (OpenGov, ClearGov) are built around this; most requests from residents and from provincial control
  bodies are about it. Today only project budgets exist, and they are per project.
- **Judged by:** the load of a sample budget file; execution percentage by area matches the file; the
  monthly report (task 05) gains a budget table; the public page shows only what is marked as
  published and no personal data; a projects' budget can be linked to a budget line (through the
  linkable-subject contract, not an import between dashboards).
- **Validate by hand:** publish one area, open the public page signed out, check the numbers against
  the file.
- **Depends on:** 06 (loading a budget by hand is not realistic).

### 12. Open data catalogue
- **What:** the municipality chooses which datasets to publish (aggregated, no personal data), gets a
  public catalogue with descriptions, update date and licence, CSV and JSON downloads and an API
  description. Use the metadata layout of the national open-data portal (a `data.json` catalogue) so
  the municipality can be harvested by it. Reuses the publication rules of task 05: nothing goes out that
  `publication.names_a_person` would flag, and small counts are masked.
- **Judged by:** a test fails when a dataset contains a free-text column; the catalogue file validates
  against the national schema; downloads are rate-limited like the public page; each dataset lists
  its last update.
- **Validate by hand:** publish two datasets, download them signed out, open the catalogue file in a
  validator.

### 13. Resident surveys feeding indicators
- **What:** the municipality builds a short survey (a few questions, rating or choice), shares a public
  link or QR code, and results appear as indicators with history (satisfaction by service, by zone).
  Zencity and ClearGov both sell this to fill the gap between records and perception.
- **Judged by:** answers are anonymous and not linked to a person; one answer per device per survey
  (best effort, said so); results per zone follow the same small-count rule as task 07; the survey
  result becomes an `IndicatorDefinition` with targets like any other.
- **Risk:** abuse and fake answers. Needs rate limits and a documented limit of what the numbers mean.

### 14. Public service-request intake and tracking
- **What:** residents report a problem (pothole, broken streetlight) from a public form, with a point on
  the map and an optional photo, receive a tracking code, and can see its state. The staff side already
  exists in Complaints (task 03, with the service clock and area queues); this adds the front door.
  Complaints become located records (the brief of task 07 allowed it).
- **Judged by:** a public submission creates a complaint in "received" with the zone filled in by the
  trigger; the resident's code shows state and the public part of the timeline only (no internal notes);
  rate limit and basic spam control; photo size and type limits; the person's contact data never
  appears in public routes.
- **Validate by hand:** submit from a phone-sized browser, follow it through the staff screens, and
  see the state change on the public page.

### 15. Government plan and objectives tracker
- **What:** the municipality writes its plan (axes, objectives, commitments to residents) once, links
  each objective to projects and indicators, and sees progress rolled up. Projects already have axes
  and objectives and indicators have targets, so this is mostly a view across them plus a public
  progress page. The national *Estado Abierto* programme asks municipalities to publish their action
  plan and follow it.
- **Judged by:** an objective's progress is computed from its linked projects' milestones and its
  indicators' targets, never typed; changing a project's state changes the objective; links use the
  linkable-subject contract, so Cabinet commitments can point at an objective too.
- **Validate by hand:** link two projects and one indicator to an objective and compare the roll-up
  with a hand calculation.

### 16. Field inspections with photos (installable web app)
- **What:** an inspector opens the app on a phone, sees the day's list (works to inspect, complaints to
  visit), takes a photo, marks the location and a short note, and it is saved to the record, even with
  a poor connection (queue and retry). Make the front end installable (PWA) and add attachments to
  the platform (none exist yet).
- **Judged by:** a photo is stored per municipality (isolated like any tenant data, size and type
  limits, served only to those who may see the record); an inspection made offline syncs once with no
  duplicates; location comes from the phone and is checked by the same code as typed locations.
- **Risk:** file storage is new (disk or S3-compatible); decide with task 09 so backups cover it.

### 17. Alerts on targets and a weekly digest
- **What:** the platform already emails milestone alerts. Add: an indicator that drifts away from its
  target for two months in a row, a status light that turns red, a commitment that becomes overdue.
  Plus one weekly email to the mayor with what changed. Task 04's brief left "overdue commitments can
  join the notification command" as optional.
- **Judged by:** each alert is sent once per event (`notifications_sent` already guarantees it); opt-out
  per kind works; nothing is sent for a suspended municipality; the digest text is a template editable in
  Configuración like the others.
- **Validate by hand:** pin a red month, run `gobernar360 notify`, read the message in Mailpit.

### 18. Participatory budget voting
- **What:** residents propose and vote for works within a set amount (the Mendoza model). It needs
  identity checking of voters, a budget to vote on (task 11) and strong abuse controls. Only worth
  doing if a municipality asks for it.
- **Judged by:** one vote per verified resident, results frozen at close and auditable.


### 22. Verified resident identity with CiDi (levels 1 and 2)
- **What:** a resident signs in with CiDi to use the public parts proposed above (14 intake,
  13 surveys, 18 voting): the request is tied to a verified person without them typing a DNI, and
  one answer or vote per person is enforceable. Ask for **level 2** (identity verified by the
  province) when it matters; level 1 only proves an email.
- **Judged by:** with the fake provider, sign-in creates a session that is **not** a member of any
  municipality and reaches only public resident routes; the person is stored as a hash of the CUIL
  (never the secret question, documents or photo), and the same CUIL gives the same hash within a
  municipality so duplicates are refused; level is checked on the server on every request; a
  resident session can never call a staff route.
- **Blocked by:** the province's authentication specification (questions 6 to 9). Build the fake
  first.

### 23. Digital signature of minutes and monthly reports (CiDi level 3)
- **What:** closing the cabinet's minutes (task 04) and a monthly report (task 05) freezes their
  content; signing them with the signatory's certificate would give them the value of a signed
  document. Level 3 is "holder of a digital-signature certificate" (`docs/cidi/reference.md` §2).
- **Judged by:** a signed PDF verifies with a standard validator; changing one byte of the frozen
  content invalidates it; the signer is a member with the right and the signature is in the audit log.
- **Blocked by:** whether CiDi exposes signing to an external system or only identifies the holder
  (question 17). It may turn out to be a separate task about PDF signature with a local token.

### 24. Staff sign-in with CiDi
- **What:** municipal staff sign in with their CiDi account instead of a password. Single sign-on
  by OpenID Connect already exists (task 01: only existing, active accounts with a provider-verified
  email are signed in, nothing is created), so this is mostly a second provider if CiDi does not
  speak OpenID Connect, plus the rule "administrators need level 2".
- **Judged by:** with the fake provider a member with a matching CUIL signs in; an unknown CUIL
  does not create an account; an `sso`-session cannot reach the operator routes (existing rule);
  the municipality can turn it on or off (`sso_enabled`).
- **Blocked by:** questions 6 to 9.

---

## Suggested sequence

0. (21, 20 and 19 Phase A are built.) Send `docs/cidi/questions-for-province.md` now, since its answer takes time.
1. By hand: F5, F13, F14, F16 and the first IDECOR import (section 0).
2. 08 (rest) → 09: trust the data and the installation.
3. 06 import, then 11 budget and 12 open data (both need data in the system).
4. 14 public intake and 17 alerts (small, visible to residents and to the mayor).
5. 10, 13, 15, 16 by demand. 18 only on request.
6. 22 to 24 when the province's CiDi specification arrives (19B first, it proves the connection).

## Sources for section 3

(The CiDi and IDECOR facts are not here: they are in `docs/cidi/` and `docs/idecor/`, with their origin.)

- ITU, city platforms and citizen dashboards: https://www.itu.int/en/publications/Documents/tsb/2021-U4SSC-Digital-solutions-for-integrated-city-management-and-use-cases/files/basic-html/page25.html
- ClearGov (budget and performance for local government): https://www.capterra.com/p/149444/ClearGov/
- OpenGov and ClearGov compared (public budget visualisation): https://www.rfp.wiki/vendors/opengov/cleargov
- Zencity, resident feedback: https://slashdot.org/software/comparison/ClearGov-vs-Zencity/
- Rochester Hills, resident surveys feeding budget planning: https://www.route-fifty.com/finance/2026/06/michigan-city-launches-digital-hub-budget-transparency-and-planning/414007/
- País Digital, tools for municipal management: https://www.argentina.gob.ar/noticias/conoce-algunas-de-las-herramientas-de-pais-digital-para-mejorar-la-gestion-municipal
- Mendoza, digital participatory budget: https://www.opengovpartnership.org/the-open-gov-challenge/mendoza-argentina-launch-a-digital-participatory-budget-program
- Argentina, open-data guide for provinces and localities: https://www.argentina.gob.ar/sites/default/files/datos_-_guia_de_apertura_para_gobiernos_provinciales_y_locales.pdf
- Programa Federal de Estado Abierto, selected initiatives: https://argentina.gob.ar/sites/default/files/iniciativas_seleccionadas_programa_federal_de_estado_abierto.pdf
