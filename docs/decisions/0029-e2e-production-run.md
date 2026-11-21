# 0029. E2E against production, on dispatch, as one Researcher account

The production app is driven end to end on GitHub Actions, on dispatch only, signed in as one
Researcher password account, at every screen. Its known-answer questions are checked on the wire,
and its reports and screenshots are named by `lib/naming`.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What built on it | [0076 The release gate looks at what the reader sees](0076-release-gate-that-sees.md): the Professor and Admin screens it left not covered |
| Every decision, by group | [README.md](README.md) |

## Context

The owner's rule is to drive the real app on GitHub Actions against production at every width
before trusting a release, because green fixtures have shipped broken screens. Frontend checks run
the smoke specs against a local build with no API. PLAN section 0 asks for one or two known-answer
questions on demand. Two-step verification is mandatory for Professor, Admin and Master admin, and a
headless run cannot pass it without a TOTP secret in CI.

## Decision

1. **One password account, `e2e-researcher@kalavigyan.example`, role RESEARCHER.** No two-step,
   Deep allowed, so the run covers what a learner and a researcher see. The API's address checks
   accept the reserved `.example` domain, so no mail can reach a person.
   `app/scripts/provision_e2e_account` creates or resets it: role, ACTIVE roster row, verified
   email, two-step off, sessions ended, no consent records. It reads the password from stdin.
   The account upsert it shares with `seed_admin` is `services/password_accounts`.
2. **`.github/workflows/e2e-production.yml`.** It is dispatch only and runs only in the deploy
   repository. It drives the Playwright projects `production-desktop` (1440x900),
   `production-tablet` (834x1194) and `production-phone` (390x844).
   - The projects exist only when `E2E_PRODUCTION=1`, so neither CI on push nor a plain
     `playwright test` can reach production.
   - Traces, videos and failure screenshots are off on them, because a trace records typed values,
     the password included. Screenshots are taken on purpose instead.
   - Sign-in goes through the deployed login form, proxy and CSP.
3. **Every screen is checked.** A screen fails on any of these:
   - a console error;
   - a failed same-origin request, except a 401 before sign-in, the 404 page's own document and an
     aborted request;
   - sideways scroll;
   - text spilling out of its box or off the screen;
   - an error alert;
   - gap copy outside cited content.

   On every signed-in screen the menu must list exactly the role's entries, name the role and
   carry no admin link. On Ask, the navigation bar and the Mode choice must match the role too.
4. **Questions are checked on the wire.** An init script tees the page's own `/api/answers/stream`
   response, so the run sees every event, heartbeat and arrival time the app received. The page
   alone cannot prove the answer: the client drops uncited sentences and treats a closed stream as
   done.

   A question passes when all of these hold:
   - one stream opened, and it ended with `done`;
   - at least one sentence is cited, and every sentence is cited;
   - every cited source arrived as a source event;
   - a sentence names alum;
   - the page shows the same sentences, each with a chip;
   - in Hindi, each sentence is either Devanagari marked translated with its English original, or
     an English fallback (decision 0023).

   Each question may take 10 minutes, and fails after 150 seconds without a byte, heartbeats
   included.
5. **Reports and screenshots are named by `lib/naming` as `Eval-Run` files.** Their golden rows are
   `evalRunFiles` in `shared/naming-golden.json`. They are uploaded as artifacts that carry the run
   id, and the global teardown writes the summary tables to the step summary.

## Consequences

- `E2E_EMAIL` and `E2E_PASSWORD` are GitHub secrets only; the box and Parameter Store never need
  them.
- A run with questions writes two `Answer` rows. It spends two Hybrid answers, one of them
  translated, within the Researcher daily cap.
- Professor, Admin and Master admin screens are not covered; covering them needs a TOTP secret in
  CI.
- The pure checks (stream parsing, answer rules, gap copy, nav labels, file names, summary) have
  unit specs in `frontend/e2e/production-checks-unit.spec.ts`, which run on push.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
