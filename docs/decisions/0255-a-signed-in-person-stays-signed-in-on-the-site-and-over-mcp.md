# 0255. A signed-in person stays signed in, on the site, in admin view and over MCP: a site session lasts a year and is renewed while it is used, an MCP connection lasts a year from its last refresh, and `review` lasts as long as the connection

A person who signs in once is not signed out while they keep using KalaVigyan. A site session lives
a year and the web renews it at most once a day while the site is used, for every role, Admin and
Master Admin and admin view among them; an MCP connection's refresh token lives a year from its last
use and rotates on every refresh; the review scope lasts as long as the connection. Sign-out now ends
the session on the server, and a suspension, refusal or removal from the access roster, a role,
password or two-step change, Sign out everywhere, Revoke on Connected apps and a replayed refresh
token still end it at once.

Date: 2026-11-28. Status: accepted (the owner, 2026-11-28: "If the user has signed in once, even in
admin view, they should not be logged out so frequently, this is a very shitty hassle, elongate it as
much as possible, for normal as well as admin users, even for mcp login, if they are logged in once,
store it for as long as possible"; the lead's lane brief `long-sessions`). It amends
[decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md), items 1 and 2 (`review`
given only within 15 minutes of a sign-in, its 15-minute tokens and its end 8 hours after the
consent). The contracts are `docs/contracts/backend.md` (What every route shares; Auth),
`docs/contracts/frontend.md` (A session lasts while it is used) and `docs/contracts/mcp-oauth.md`
(Authorization; Tokens; Scopes and roles); `docs/RUNBOOK.md` (Sign-in lifetimes) holds the settings.

| For | Read |
|---|---|
| The review scope, given fresh, its short tokens and staged decisions a person confirms | [decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) |
| A staged batch confirmed in the person's own MCP client | [decision 0243](0243-a-staged-decision-confirmed-in-the-person-s-own-mcp-client.md) |
| The web taking over a rotated session in its cookies | [decision 0172](0172-a-rotated-session-taken-over-and-cached-pages-kept-whole.md) |
| A code bound to its approver's sessions, as a connection is | [decision 0185](0185-a-code-bound-to-its-approver-robots-rules-without-backtracking-and-a-cap-on-inflated-bodies.md) |
| Every decision, by group | [README.md](README.md) |

## Context

What signed people out, verified on 2026-11-28:

1. **The site session lived seven days, used or not.** `JWT_EXPIRES_MINUTES` defaulted to 10080
   minutes. Production sets no value: `/kalavigyan/env/` in Parameter Store holds 58 names and
   `JWT_SECRET` is the only `JWT_` one, GitHub holds no such secret or variable, and `backend/.env`
   holds only `JWT_SECRET`. A token was minted at sign-in, at a password change and when two-step
   verification was turned on or off, and never on use; the web set the cookies' `Max-Age` from the
   token's own expiry (`apiProxy.tokenLifetimeSeconds`). So everyone, Admins included, was signed
   out seven days after signing in, however much they used the site.
2. **Sign-out was stateless.** `POST /api/auth/logout` answered `{ok: true}` and the web cleared its
   cookies; the token itself stayed good to its expiry. A week's gap then; a year's with a year's
   token.
3. **MCP.** Access tokens lived an hour, 15 minutes when they held `review`; refresh tokens 30 days,
   moved on at every refresh, so a connection used monthly already stayed. `review` ended 8 hours
   after the consent (`live_scopes`): the next refresh left it out and the admin tools vanished. It
   was given only when the site session's `iat` was under 15 minutes old.
4. **What the owner met.** Production's connections of 2026-11-22 to 2026-11-28, read without
   writing: every re-authentication of the owner's clients (Claude Code at 06:58 UTC on 2026-11-28,
   claude.ai at 08:30 on 2026-11-24 and 20:40 on 2026-11-25, ChatGPT alongside) came minutes after a
   refresh made more than 8 hours after the consent, which dropped `review`; the person connected
   again, which also asked for a fresh site sign-in to give `review`. No connection was revoked for a
   replayed refresh token.
5. **Nothing else.** No idle timeout exists. Admin view is a toggle kept in the browser
   (`AdminViewProvider`), with no window. Key and setting changes ask a code per change, answered
   401 with `X-Two-Factor-Required`, which the web does not take as the end of a session. The web
   ends a session only on a 401 from the session check (`apiFetch` with a marker, `AuthProvider`'s
   `/me`), which is the right answer to an ended session; renewal could not help a token already
   expired. Google, Microsoft and Yahoo prove the person at sign-in and are never asked again. No
   Android or portal client holds these tokens: the portals reach KalaVigyan through the signed
   cross-portal feed.

## Decision

1. **A year, for every role.** `JWT_EXPIRES_MINUTES` defaults to 525600 (a year) and is refused
   above 576000: browsers cap a cookie's life at 400 days (RFC 6265bis), the only hard limit found,
   so a year fits under it. Admins, Master Admins and admin view get the same.
2. **Renewed while used, at most about once a day.** The web asks `POST /api/session/renew` when the
   account is known and whenever a tab becomes visible, at most once an hour, with a plain `fetch`
   that never ends a session. That route (same-origin only) leaves a token issued less than a day ago
   alone and asks nothing of the API; an older one, or one without a session id, goes to
   `POST /api/auth/renew`, which mints a fresh year for the same session. The cookies are written
   again with the same marker, `HttpOnly`, `Secure` and `SameSite=Lax` as before. An untouched
   session ends a year after its last renewal. A refused renewal changes no cookie.
3. **A site session is a record.** Sign-in opens a `SiteSession` row (migration
   `0126_long_sessions`) whose id the token carries as `sid`. Every request reads the row with the
   account (`core/site_sessions.site_session_live`): it must be the token subject's own and not
   ended. Sign-out sets `endedAt`, so that token and every token renewed from it answer 401 at once,
   and the person's other sessions go on. A password or two-step change keeps the changer's session
   id and ends the others through the token version.
4. **Nobody is signed out by the release.** A token minted before it has no `sid`; it stands until
   its own expiry, at most seven days, and the first visit renews it into a session with an id. Until
   then such a token, signed out, is only dropped from the browser, as before.
5. **MCP connections last a year from their last use.** `MCP_REFRESH_TOKEN_SECONDS` (a year) bounds a
   connection and its refresh token, moved on at every refresh; every refresh rotates, and a spent
   refresh token presented again, however late, revokes the whole connection, its newest tokens with
   it. Access tokens stay an hour (`MCP_ACCESS_TOKEN_SECONDS`): every MCP call reads the token's row,
   so a revocation holds at once whatever the lifetime, and the client renews them without the person
   seeing it; a longer access token would only lengthen the use of one that leaks unnoticed. A
   connection made before the release keeps its expiry and gains the year at its next refresh.
6. **`review` lasts like the other scopes.** Decision 0170 gave `review` only within 15 minutes of a
   sign-in so that "a session left open on a shared machine cannot give it", and shortened its tokens
   and its life to a working day. With sessions of a year the window would force a sign-out and
   sign-in before every review connection, and the 8-hour end caused the re-authentications the
   owner met. Both go, with the 15-minute token: `REVIEW_SIGN_IN_SECONDS`,
   `REVIEW_ACCESS_TOKEN_SECONDS`, `REVIEW_GRANT_SECONDS`, `live_scopes`, `access_token_seconds` and
   the consent's read of the session's `iat`. What stays: `review` only for an Admin or Master Admin
   with two-step verification on, read on every call; nothing the AI stages applies until a person
   confirms it on the Review page or in their own client's form (decision 0243); a role, password or
   two-step change, a suspension or Sign out everywhere ends the connection. `review` reaches nothing
   an Admin's site session cannot already do on the Review page, so its window guarded nothing the
   session itself did not.
7. **What still ends a session at once**, each tested both ways: Sign out (that session and every
   token renewed from it; `tests/db/test_long_sessions_db.py`); a suspension, a refusal or removal
   from the access roster, a role change, Sign out everywhere and a password reset (every session of
   the account, renewed ones included, through `tokenVersion` and `sessionsValidFrom`; the same file,
   one case each); a password change (every other session, the changer's kept; the same file); Revoke
   on Connected apps (that connection; `tests/db/test_oauth_db.py`); a replayed refresh token (the
   whole connection, months later too; `tests/db/test_long_mcp_connections_db.py`). No page lets an
   Admin revoke another person's connection; Sign out everywhere and a suspension end them all.
8. **Settings.** The three lifetimes are settings with their defaults in `core/config.py`. Production
   set none of them, so no value was written to Parameter Store, GitHub or `backend/.env`; a value
   set later goes into all three at once and shortens only tokens minted after it.

## The security trade-off

Longer sessions widen the window in which a stolen token can be used. A site cookie copied out of a
browser, or a refresh token copied out of an AI client's store, now works for up to a year rather
than a week or a month, and whoever holds it can keep it alive by using it. Rotation, reuse detection
and revocation therefore carry more of the weight: sign-out now ends a session on the server; every
request reads the session and the account's token version; an MCP refresh token rotates at every use
and a replayed one revokes the whole connection; Sign out everywhere, a password change, a two-step or
role change and a suspension end every session and connection of the account at once. The cookie
stays `HttpOnly`, `Secure` and `SameSite=Lax`, so page script cannot read it and other sites cannot
send it. What this leaves: a stolen site session used while its owner never signs out, changes their
password or asks an Admin for Sign out everywhere stays good, and a person cannot yet list their own
site sessions to end one from another device.

## Consequences

- Migration `0126_long_sessions` adds `SiteSession` (row-level security on, no grants to `anon` or
  `authenticated`) after `0125_section_proposals`.
- Each signed-in request reads one more row by its primary key.
- One row per sign-in accumulates; nothing deletes ended or lapsed rows yet. The nightly upkeep could
  delete rows renewed more than a year ago; that is left open.
- The branch for a token without `sid` serves nobody once the last such token expires, seven days
  after the release; it can then be removed.
- Rotating `JWT_SECRET` still signs every site session out.
- No screen changed, so the design skill had nothing to say; the consent screen's words for `review`
  come from `research/oauth_contract.SCOPE_TEXT` and no longer name a time.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-28; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/test_long_sessions.py` (the settings and their bounds, the session id in a token, the
per-request session check and a token from before), `backend/tests/test_long_sessions_migration.py`,
`backend/tests/db/test_long_sessions_db.py` (renewal, expiry, sign-out and every revocation),
`backend/tests/db/test_long_mcp_connections_db.py` (a year from the last refresh, rotation and a late
replay, a connection from before), `backend/tests/db/test_review_scope_db.py` and
`backend/tests/mcp/test_oauth_rules.py` (`review` without a time limit, still Admin and two-step
only), `backend/tests/db/test_staged_reviews_db.py` (a review connection a year old still only
stages) and the web's `frontend/e2e/session-renewal-unit.spec.ts` (the renewal, its cookie and its
pace).
