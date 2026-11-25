# Task 19: Notices to residents, through CiDi when they have it

Priority: **high** (chosen by the product owner on 2026-11-25).
Read first: `docs/cidi/README.md`, `docs/cidi/reference.md` (sections 4, 5, 7) and
`docs/cidi/questions-for-province.md`. **There is no public CiDi technical specification**; this
task is split so that everything that can be built and proven offline is built now, and the real
connection is a last step that must wait for the province's documents.

## Task description

gobernar360 tells nobody who is not a member: the complaints dashboard (task 03) resolves a
resident's complaint and the resident learns about it only if someone calls them. Residents in
Córdoba already have a provincial account, Ciudadano Digital (CiDi), whose *domicilio electrónico*
is the official place to be notified, and municipalities that adhered can use it. This task gives
the platform a way to tell a resident that something happened to what they asked for, by the best
channel they have: CiDi's "Mis Comunicaciones" when the municipality uses it and the resident has an
account, an email otherwise.

The centre of the work is not the screen but the guarantees:

- **A port, not a vendor.** The platform defines the CiDi interface it needs
  (`platform/cidi/ports.py`, exactly the one in `docs/cidi/reference.md` §7) and works against it.
  A fake implements it for tests and local use. The real adapter exists only after the province's
  documents do (Phase B).
- **Never from request code.** Like email (`platform/outbox.py`): the request queues a notice in
  its own transaction, a command (`gobernar360 send-notices`) delivers it later, with a row lock
  (`SKIP LOCKED`), backoff, and `failed` after 20 attempts.
- **Once per event.** A notice is identified by an `event_key`; asking for the same event twice
  creates one notice, even concurrently (same technique as `notifications_sent`: `INSERT ... ON
  CONFLICT DO NOTHING`).
- **It says only what the resident may know.** The text is built from a template and a few fields
  (name, municipality, complaint number, type, outcome) plus an optional message that the
  employee *writes for the resident*. Internal notes, the timeline, other people's data and the
  assignee never enter a notice. The text is frozen when queued, so what was sent is auditable.
- **No legal claims (decided by the product owner).** CiDi's law says notifications in the
  domicile are binding for the *Government of the Province*. Whether that holds for a municipality
  depends on its own adhesion and ordinance (`reference.md` §4). gobernar360 says **only
  "Entregado a CiDi"**: never "notificado", "notificación fehaciente" or anything that suggests legal
  effect, in the interface, the texts sent, the CSV and the API field names (`handed_over`, not
  `notified`). A test searches the locale files for those words. The municipality's ordinance (a
  setting) may be shown next to it, as information.
- **Minimum personal data.** The only thing taken from CiDi's world is the resident's **CUIL**
  (the CiDi user name), stored in the people registry. Never the secret question, documents or
  photo (`reference.md` §5).

### Phase A: everything provable offline (this is what an agent without the spec does)

1. **CUIL in the people registry.** New nullable `people.cuil` (11 digits, digits only stored; the
   form accepts `20-12345678-6`, with dashes or dots or spaces). Valid only if the check digit is
   right (weights 5,4,3,2,7,6,5,4,3,2 over the first ten digits; 11 minus the sum modulo 11, where
   11 gives 0 and 10 is not a valid CUIL) and, **when the person also has a DNI, the eight middle
   digits equal the DNI padded with zeros to eight** (`20-12345678-6` goes with DNI 12345678).
   Unique per municipality when present (like `dni`). Add it to `PersonIn`/`PersonOut` and to the
   person forms (the shared `PersonSelect`/person editors of Economic, Social and Complaints; find
   them, do not duplicate). Lookup by exact CUIL, like by DNI, never browsing. A CUIL is personal
   data: it appears only where the DNI already does.
2. **Ports and fakes** (`platform/cidi/`): `ports.py` (`Communication`, `Receipt`, `CidiError`,
   `RecipientUnknown`, `Unavailable`, `CommunicationsPort`), `fake.py` (`FakeCidi` with
   constructor arguments `unknown: set[str]`, `unavailable: bool`; keeps what it was sent),
   `__init__.py` with `get_port()` choosing by `GOBERNAR360_CIDI_MODE`:
   `off` (default; nothing is sent through CiDi), `fake` (local demo: appends one JSON line per
   message to the file in `GOBERNAR360_CIDI_FAKE_INBOX`, default `./cidi-fake-inbox.jsonl`, added
   to `.gitignore`; a command `gobernar360 cidi-fake-inbox` prints it), `live` (Phase B; until then
   raises `CidiNotConfigured` with a message pointing to `docs/cidi/questions-for-province.md`).
3. **Notices table `resident_notices`** (tenant table, RLS, `enable_tenant_rls`): `id`, `person_id`
   (resolved with `tenant_crud.resolve()`), `kind`, `subject_dashboard`, `subject_kind`,
   `subject_ref`, `event_key`, `channel` (`cidi` or `email`), `state` (`queued`, `handed_over`,
   `failed`, `no_channel`), `title`, `body` (frozen plain text), `attempts`, `next_attempt_at`,
   `last_error`, `external_id`, `created_at`, `handed_over_at`, audit columns. Unique
   `(event_key, person_id, channel)`. Migration: the next free number.
4. **Platform API** `platform/resident_notices.py`: `queue(ctx, person, kind, event_key, subject,
   message=None, **params)`. Decides the channel from the municipality's policy and what the person
   has: policy `cidi_then_email` with a CUIL → `cidi`; no CUIL or `RecipientUnknown` later → falls
   back to `email` when the person has one (by queuing a second row, not by mutating the first);
   policy `email` → `email`; nothing available → one row `no_channel` (so the employee sees that
   nobody was told). Email goes through `email_templates.send` (queued in the outbox in the same
   transaction) and the row is `handed_over`. A suspended municipality is skipped by the delivery
   command, as `notify` does.
5. **Delivery command** `gobernar360 send-notices [--watch]` (CLI module as `send-email`):
   delivers `queued` `cidi` rows through `get_port()`; `Unavailable` retries with backoff,
   `RecipientUnknown` marks the row `failed` and triggers the email fallback when the policy allows.
6. **Settings, per municipality** (decided by the product owner: **each municipality adheres to
   CiDi itself**, so each one configures its own connection in the app). Configuración,
   `municipality_settings`, saved by its own `PUT .../settings/notices` like map settings, so
   `PUT .../settings` never touches them:
   - `resident_notice_channel` (`email` default, `cidi_then_email`, `cidi`);
   - `cidi_ordinance` (text up to 200, for example "Ordenanza 12.985", optional);
   - **the connection data** the municipality obtains when its adhesion is approved: a
     `cidi_connection` record with the fields the province's specification requires. Until that
     specification exists, the record is a generic set of named values, each marked secret or not
     (`system_name`, `publication_url`, `contact` are plain; anything like a key, certificate or
     token is secret), plus the state of the adhesion (`not_requested`, `requested`, `approved`,
     with the date and the file number the municipality types). Phase B fixes the actual fields;
     the storage, the screen and the rules below are built now.
   - **Secrets** are write-only: the API accepts them, never returns them (it returns "set" or
     "not set" and the date), they are **encrypted at rest** with a key from the environment
     (`GOBERNAR360_SECRETS_KEY`; refuse to save a secret if it is missing; use a vetted library,
     for example Fernet from `cryptography`, not hand-made crypto), they never appear in the audit
     log (the log records only that they changed), in error messages, in logs or in the export of
     a municipality (task 08 exports them as "not exported"), and no route outside the delivery
     command can read them decrypted. The platform operator can see the state but not the values.
   - Both channel settings and the connection are editable by the municipality's administrator and
     by the operator, audited, in the `emails` tab, section "Avisos a vecinos", with a sentence
     that explains the adhesion is done by the municipality with the Province and where the form is
     (`docs/cidi/adhesion-request.md`). A CiDi channel can be chosen only when the adhesion state
     is `approved` and the connection is complete; otherwise the screen says what is missing. The
     installation-wide `GOBERNAR360_CIDI_MODE` still decides whether CiDi is reachable at all (the
     API exposes `cidi_available`).
7. **Texts** (templates in Configuración like the others, keys `notice.complaint_resolved` and
   `notice.complaint_rejected`; defaults in the backend locale under `email.templates.<key>`; add
   them to `email_templates.Spec` with allowed variables `{{name}}`, `{{municipality}}`, `{{code}}`,
   `{{type}}`, `{{message}}` and required ones `{{name}}`, `{{municipality}}`, `{{code}}`; frontend
   `settings.templates.keys.<key>`). CiDi gets the plain text rendering.
8. **First use, Complaints.** When a complaint moves to `RESOLVED` or `REJECTED`, and its resident
   is a registry person, the transition handler calls `resident_notices.queue` with
   `event_key = "complaint:<id>:<state>:<event id>"`. The transition body accepts an optional
   `message_to_resident` (up to 500 characters) that is the only free text that reaches the
   resident; the internal `note` never does. Anonymous complaints notify nobody. The complaint
   detail returns `notices` (channel, state, dates; never the body) to editors and above. Complaints
   imports only `platform` (import-linter stays green).
9. **Screens.** The person form field with its error text; the notices section in Configuración; on
   the complaint page, an "Avisos al vecino" list for editors (state in words: "Entregado a CiDi",
   "Enviado por correo", "En cola", "Falló", "Sin medio para avisar") and the optional message
   field on the resolve and reject dialogs, with a counter. All copy in `es-AR.json` (see the
   suggested texts at the end).
10. **Docs and demo.** `README.md` and `CLAUDE.md` (a "Notices to residents" paragraph and the new
    command); the demo data gives two Noetinger residents a CUIL (made-up, with valid check digits)
    and `cidi_then_email` for Comuna Demo with mode `fake`; `docs/cidi/adhesion-request.md`, a **template** of
    the adhesion form (Documento III of `docs/cidi/source/documentos_cidi_2023_12_19.txt`) that a
    municipality fills in and files with the Province: system name "gobernar360 – <municipio>",
    scope "Enviar mensajería a través de CiDi – Mis Comunicaciones" only, and `(completar)` for
    what the municipality supplies (publication URL, responsible, address, signature of its top
    authority). The app offers it from the settings section pre-filled with the municipality's name
    and publication address (`APP_URL`); it is a document to print, not a form that sends anything.

### Phase B: the real connection (blocked until `docs/cidi/integration-spec.md` exists)

Do **not** start it from this document alone. When a person has written `integration-spec.md` from
the province's answers (`questions-for-province.md`, questions 10 to 16):

- `platform/cidi/live.py` implements `CommunicationsPort` as the spec says. It is built **per
  municipality** from that municipality's saved connection (decrypted only inside the delivery
  command), so two municipalities use different credentials in the same process; timeouts and
  retries are explicit. Fix the fields of `cidi_connection` to what the spec requires and migrate
  the generic record.
- Contract tests with recorded responses (saved under `backend/tests/cidi/recorded/`, made-up
  CUILs) and one skipped-by-default test that talks to the province's test environment.
- If the spec turns out to differ from the port (for example it cannot be idempotent), change the
  port and the Phase A tests in the same commit and write the reason in `docs/cidi/reference.md`.

If Phase B cannot be done, the task is closed as
`# Task 19: ... - PARTIAL (phase A done; live adapter waits for the CiDi technical spec)`.

## How to judge completion

Setup: database up, `uv run alembic upgrade head`, `uv run gobernar360 seed-demo --reset`,
`GOBERNAR360_CIDI_MODE=fake`, API and web app running.

Automated, all must pass (Phase A):

- `cd backend && uv run pytest` — includes tests for: a CUIL with a wrong check digit is rejected;
  `20-12345678-6` is accepted and stored as `20123456786`; a CUIL whose middle digits differ from
  the person's DNI is rejected; two people cannot share a CUIL in a municipality but two
  municipalities can; resolving a complaint of a person with a CUIL queues one `cidi` notice and
  `send-notices` marks it `handed_over` with the fake having received exactly its frozen text;
  running the transition handler twice for the same event creates one notice; a resident with no
  CUIL and an email gets the email row `handed_over`; a resident with neither gets one `no_channel`
  row; `RecipientUnknown` on CiDi creates the email fallback when the policy is `cidi_then_email`
  and does not when it is `cidi`; `Unavailable` retries with growing delay and fails after 20
  attempts; **the delivered text never contains the complaint's internal note or timeline text**
  (use a note with a unique marker and assert it is absent from `title`, `body`, the fake's messages
  and the outbox); an anonymous complaint notifies nobody; a viewer of Complaints never receives
  `notices`; municipality B cannot read or resolve municipality A's notices and a notice cannot
  point at B's person (isolation test per the project's convention); a suspended municipality's
  notices are not delivered; a secret is never in an API response, an audit entry, a log record
  (`caplog`) or an error body, is encrypted in the database (the column does not contain the
  plaintext), cannot be saved without `GOBERNAR360_SECRETS_KEY`, and a municipality cannot pick a
  CiDi channel before its adhesion is `approved`; two municipalities with different connections
  never use each other's; `GOBERNAR360_CIDI_MODE=off` queues nothing for CiDi and falls back
  per policy; `live` mode without a spec raises `CidiNotConfigured` and sends nothing; settings
  saves are audited and `PUT .../settings` does not change them; a dashboard registered only in the
  test can queue a notice (the contract is not complaints-specific).
- `cd backend && uv run pytest --cov` ≥ 95 % per file; `uv run ruff check . && uv run ruff format
  --check . && uv run lint-imports` (`platform/cidi` is platform code: no dashboard import).
- `cd frontend && npm test -- --run && npm run test:coverage && npm run lint && npm run build &&
  npm run e2e` — includes `e2e/resident-notices.spec.ts`: as the Comuna Demo admin, give a resident
  a CUIL, resolve their complaint with a message, run `send-notices`, and see "Entregado a CiDi".

By hand, as `admin@comuna-demo.test` with the fake:

1. Settings → Avisos a vecinos: choose "CiDi y, si no, correo" and type an ordinance. Reload: kept.
2. Create a resident with CUIL `20-12345678-6` and DNI `12345678`; try `20-12345678-7`: refused.
3. Resolve their complaint with a message to the resident and an internal note. Run
   `uv run gobernar360 send-notices`; `uv run gobernar360 cidi-fake-inbox` shows the message with
   the resident's message and **not** the internal note. The complaint page says "Entregado a CiDi".
4. Repeat the resolve on another complaint of a resident with only an email: "Enviado por correo"
   and the text appears in Mailpit (http://localhost:8025) after `send-email`.
5. A resident with neither: "Sin medio para avisar" is visible to the editor.
6. As `admin@noetinger.test` none of Comuna Demo's notices or CUILs are visible.

7. Connection: save a made-up secret, reload: the screen says "cargado" and shows no value;
   the audit log shows that it changed but not what; as the operator the value is not visible
   either; as `admin@noetinger.test` Comuna Demo's connection is not reachable.

Pass (Phase A): every command is green and the seven manual checks behave as described.
Pass (Phase B): additionally the recorded contract tests are green and a person has sent one real
communication to a test account in the province's test environment and seen it in "Mis
Comunicaciones".

## Other notes

- Copy suggestions (Spanish, put them in `es-AR.json`): "Avisos a vecinos"; "Medio para avisar a
  los vecinos"; "Solo correo", "CiDi y, si no, correo", "Solo CiDi"; "Ordenanza que respalda el
  uso de CiDi"; "CiDi no está conectado en esta instalación"; "Entregado a CiDi"; "Enviado por
  correo"; "En cola"; "Falló"; "Sin medio para avisar: el vecino no tiene CUIL ni correo";
  "Mensaje para el vecino (opcional)"; "Lo que escribas acá le llega al vecino. La nota interna no."
  Help text of the sent state: "Entregado a CiDi significa que el aviso se envió a la cuenta del
  vecino; no afirma efectos legales." Nothing else is claimed.
- The demo CUILs must be made up; compute valid check digits, do not copy real ones.
- Out of scope: reading CiDi to find whether a CUIL has an account, delivery or read receipts,
  attachments, notices for other dashboards (the contract allows them), sign-in with CiDi (task 24)
  and verified identity of residents (task 22).
