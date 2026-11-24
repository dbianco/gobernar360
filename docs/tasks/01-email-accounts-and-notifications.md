# Task 01: Accounts by email, notifications and single sign-on - DONE

## Task description

Today an administrator creates a user, types a password for them and hands it over by
some other channel. There is no way to recover a forgotten password, and nobody is told
when something needs attention. This session gives gobernar360 outgoing email and builds
the three things that depend on it, plus sign-in through an external identity provider.

The centre of the work is a delivery pipeline that can be trusted, not the screens:

- **Outbox.** Every email is first written to an `email_outbox` table in the same
  transaction as the change that caused it, and a worker command
  (`gobernar360 send-email`) delivers it over SMTP with retries and backoff. A failed
  SMTP server never loses a message and never sends one twice.
- **Invitations.** Adding a user sends a link instead of asking for a password. The link
  carries a single-use token that expires, is stored only as a hash, and lets the person
  choose their own password. Accounts are shared between municipalities, so inviting an
  email that already has an account adds the membership and sends a notice, without
  letting the inviting administrator learn anything about or take over that account.
- **Password recovery.** "Forgot my password" answers the same way whether or not the
  email exists, is rate limited per address, and signing in with a new password closes
  every other session of that user.
- **Notifications.** A scheduled command (`gobernar360 notify`) emails the people
  responsible when a project milestone is overdue and when a dashboard has no status
  light for the month that just ended. Each notification is sent once per event: running
  the command twice must not send a second email. Users can turn each kind off in their
  account page.
- **Single sign-on.** Sign-in through a generic OpenID Connect provider (authorization
  code flow with PKCE, `state` and `nonce` checked), configured by environment
  variables. It only signs in people who already have an account with that verified
  email; it never creates one.

Email texts are in Spanish and live in the locale files like every other text.

## How to judge completion

Setup: `docker compose up -d` now also starts a local mail catcher (Mailpit, web inbox
on `http://localhost:8025`) and a local OpenID Connect provider. Then migrate, seed and
start the API and web app as in the README.

Automated, all must pass:

- `cd backend && uv run pytest tests/platform` — includes tests for: token is single
  use, token expires, token is not stored in clear, recovery response is identical for
  known and unknown emails, rate limit, other sessions closed after a reset, outbox row
  survives an SMTP failure and is delivered on retry, `notify` run twice sends once,
  single sign-on rejects a wrong `state` and an unverified email.
- `cd backend && uv run ruff check . && uv run lint-imports`
- `cd frontend && npm test -- --run && npm run lint && npm run build`
- `cd frontend && npm run e2e` — includes a spec that reads the invitation email from
  the mail catcher's API, follows the link and signs in.

By hand:

1. Sign in as `admin@noetinger.test`, add a user with a new email. No password is asked.
   The invitation appears in the Mailpit inbox. Open the link, choose a password, sign in.
   Opening the same link again shows that it is no longer valid.
2. On the sign-in page use "forgot my password" with an unknown email and with a known
   one: the screen says the same thing both times; only the known one produces an email.
3. Stop the mail catcher, add another user, start it again and run
   `uv run gobernar360 send-email`: the invitation arrives exactly once.
4. Run `uv run gobernar360 notify` twice: the overdue-milestone email from the demo data
   arrives once.
5. "Sign in with single sign-on" signs in a demo user through the local provider.

Pass: every command is green and the five manual checks behave as described.

## Other notes

- No real mail service or Google credentials are used: SMTP and the identity provider
  are local containers. A real provider (Google included) is configuration only.
- Depends on nothing else. Task 05 (monthly report) can later reuse the outbox to send
  the report.
- Out of scope: email templates designed for marketing clients, SMS, in-app notification
  centre.
