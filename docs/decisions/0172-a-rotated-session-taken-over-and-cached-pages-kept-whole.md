# 0172. The web takes over every session the API rotates, a cached reading page fails rather than drops a part, and sign-in and the shells settle once

Every write under `/api/auth` goes through the web's own route handlers, and whatever session
token the API answers becomes the cookie and never reaches page JavaScript; a week-cached reading
page fails its render rather than keep a page without its field voices or languages; the login page
resolves where to go once; the shells keep one frame above a page; a token issued after its
account's sessions were cut off is live; and the users list filters on the access it shows.

Date: 2026-11-23. Status: accepted (the lead's adversarial review of 2026-11-23, auth and web lane).
It amends [decision 0082](0082-catalogue-v2-and-server-fetch.md), item 8. The contracts are
`docs/contracts/frontend.md` (Transport and session; First paint from the server; Two route groups;
the Microsoft and Yahoo sign-in) and `docs/contracts/backend.md` (Headers the web client must read;
Manage users).

| For | Read |
|---|---|
| Server fetch and its typed failures, whose fallback rule item 4 narrows | [decision 0082](0082-catalogue-v2-and-server-fetch.md) |
| A first password and the change-password token | [decision 0028](0028-first-password-provider-proof.md) |
| The Microsoft and Yahoo sign-in | [decision 0026](0026-yahoo-sign-in.md) |
| How the web reaches the API | [frontend.md](../contracts/frontend.md), section 1 |
| Every decision, by group | [README.md](README.md) |

## Context

The review confirmed six faults.

- **Two-step on or off signed the user out.** Both routes raise the account's `tokenVersion` and
  answer the new token in `X-Session-Token` and as `accessToken`. The web took over a rotated token
  only for change-password and sign-in, each named in `proxy.ts`'s `SESSION_ROUTES`; enable and
  disable went through the plain rewrite, which never sets the `__Host-session` cookie and handed
  the bearer token to page JavaScript. The two-step card's next reads (`refreshMe`, `load`) used
  the dead token, `apiFetch` ended the session and left for `/session-ended`, and the recovery
  codes, shown once, were gone. A Professor, Admin or Master Admin meets this on the required
  two-step gate. Once the cookie is right, a second fault shows there: the card read the account at
  once, the account said two-step on, and the gate swapped the card and its codes for the app.
- **Microsoft and Yahoo sign-in lost the return address.** The provider returns to `/login` with no
  `?next`, so the address lives only in `sessionStorage`, which `takeSignInReturn` reads and
  removes. The sign-in's own navigation and the page's effect each asked, and the second, later,
  answered `/ask`, so a reader connecting an MCP client from `/oauth/authorize` lost the request.
- **A failed secondary read was cached for a week.** The craft page is kept 604,800 s. Its
  document and record throw on any failure but 404, so Next keeps the last good page; its field
  voices and page languages answered `null` on any failure, so a timeout during a regeneration
  cached a page without "In the artisan's words", "From the workshops" or its language versions.
- **The shells drew their page twice.** `ReadingShell` returned `ShellFrame` without an account and
  `AccountGate > ShellFrame` with one, and `AppShell` drew `/ask` the same way before and after the
  account was known; the root type changed, so React mounted the page again once `/me` answered.
- **A sign-in that clears never-verified credentials returned a dead token.** Clearing sets
  `sessionsValidFrom` to the microsecond, the same request then issues a token whose `iat` was cut
  to the whole second, and `token_matches_user` refuses an `iat` before the cut-off.
- **The users list filter disagreed with its label.** The configured Master Admin is shown `ACTIVE`
  whatever the roster says, but the filter read the roster row, which the Master Admin has none of.

## Decision

1. **One rule for a session the API rotates.** The proxy hands every write under `/api/auth`
   (`apiProxy.isAccountWrite`) to the web's route handlers; reads there are rewritten as before.
   Sign-in and two-step verify keep `handleSignIn`, which sends no session; logout clears it; every
   other write goes to `app/api/auth/[...path]` (`handleAccountWrite`), relayed with the session.
   Both pass the answer through `takeOverSession`: a token in `X-Session-Token`, or else as
   `accessToken` in a JSON body, of a successful answer becomes the cookie with a new marker and
   `x-session-rotated: 1`, and `X-Session-Token`, `accessToken` and `tokenType` are taken out of
   what the page reads. The alternatives were another entry for each route (the list had grown one
   route at a time and missed two), relaying every write through a function (uploads and streams
   would meet the function's body limit and duration), and an API that does not rotate (the
   contract bumps the version on any two-step change, which ends stolen sessions). The API answers a
   new session only from a write under `/auth`, which `backend/tests/test_session_rotation_routes.py`
   pins: change-password, two-step on and two-step off.

   | Route that raises `tokenVersion` | Whose | New token | Covered by |
   |---|---|---|---|
   | `POST /auth/login`, `/auth/two-factor/verify` (clearing never-verified credentials, adopting the roster role, the Master Admin's role) | the one signing in | `accessToken` in the body | `handleSignIn` |
   | `POST /auth/change-password` | the caller | `X-Session-Token` | `handleAccountWrite` |
   | `POST /auth/two-factor/enable`, `/disable` | the caller | `X-Session-Token` and `accessToken` | `handleAccountWrite` |
   | `POST /auth/set-password` (an emailed link) | the link's account, signed out | none | sign in afterwards |
   | `PATCH /users/{id}` (role, a required password change), `POST /users/{id}/suspend`, `/sign-out-everywhere`, `DELETE /users/{id}/two-factor`, `DELETE /users/{id}` | another account; the caller's own only through a required password change, which the web never offers | none | the target's sessions end, as meant |
   | `POST /access/roster`, `/access/roster/{id}/decision`, `PATCH` and `DELETE /access/roster/{id}` | the entry's account; the guards refuse the caller's own but a Master Admin barring their own entry | none | the entry's sessions end, as meant |

2. **The recovery codes stay until they are put away.** The two-step card (`lib/twoStepFlow`)
   reads the account again when turning two-step off and when the codes are put away, not when they
   appear, so the gate (`lib/accountGate.accountStepFor`) keeps the card on screen. Until then the
   account facts on Settings still say two-step is off.
3. **A token's `iat` is the moment it was issued.** `create_access_token` writes the full-precision
   timestamp, as the OAuth and upload-link claims already do, so a token issued after the cut-off in
   the same second is live and one issued before it is not. The alternative, comparing the cut-off
   at whole seconds, would leave tokens issued just before it to the version check alone.
4. **A cached reading page's reads are absent only on 404.** `serverFetch.bodyOrAbsent` is the one
   rule for the document, the record, the field voices and the page languages: a 404 is absent and
   any other failure throws, so Next keeps the last good page. Item 8 of decision 0082 still holds
   for pages that are not kept (the landing's count).
5. **The login page lands once.** `sessionReturn.signInReturnOnce` resolves the return address the
   first time the page leaves and every later way out goes to the same place.
6. **One frame above a page.** `readingFrame` and `appFrame` always draw `AccountGate >
   ShellFrame` (and `GuardedRoute` for the signed-in pages), with the gate asking nothing of a reader
   not yet known; only the navigation changes when the account arrives.
7. **The users list filters on what it shows.** One SQL expression gives the access a row shows and
   the access it is filtered on, the configured Master Admin `ACTIVE` with or without a roster row;
   the one-user read uses it too.

## Consequences

- A write under `/api/auth` is a function call on Vercel rather than an edge rewrite. These are the
  sign-in, password and two-step forms, small JSON bodies.
- A token's `iat` is now fractional. Nothing reads it but `token_matches_user`; a reader that needs
  an integer floors it.
- A craft or category page whose field voices or languages cannot be read on its first render shows
  the error page until the API answers, as a failed document read already did.
- The smoke API answers the later-backend craft's field voices with an empty page.
- No migration, and no register entry: these were review findings, not entries.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `frontend/e2e/session-rotation-unit.spec.ts`,
`frontend/e2e/oidc-sign-in-unit.spec.ts`, `frontend/e2e/reading-prerender-unit.spec.ts`,
`frontend/e2e/account-shell-unit.spec.ts`, `backend/tests/test_session_rotation_routes.py`,
`backend/tests/test_security_and_core.py`, `backend/tests/db/test_two_step_session_db.py`,
`backend/tests/db/test_oidc_sign_in_db.py` and `backend/tests/db/test_user_access_filter_db.py`.
