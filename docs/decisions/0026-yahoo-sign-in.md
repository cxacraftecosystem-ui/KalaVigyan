# 0026. Yahoo sign-in (and Microsoft, off): DR's OpenID Connect module, ported

Yahoo sign-in, and Microsoft switched off, is the designer portal's OpenID Connect module ported:
the server redeems the code with the client secret, the redirect URI is pinned, the nonce binds the
portal's digest to KalaVigyan's server nonce, and two-step and limits are as for Google. Every
provider shares one account path.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked for "Continue with Yahoo". The designer portal (DR) has shipped Microsoft and
Yahoo sign-in since 2026-10-10 (`backend/app/services/oidc_sign_in.py`, `frontend/lib/oidcSignIn.ts`,
`frontend/app/login/callback/route.ts`, DR `docs/SECURITY.md` 3.3A): an OpenID Connect
authorization code with PKCE (S256) and a nonce, redeemed by the backend with the client secret,
because Yahoo's token endpoint accepts only a client secret and answers no cross-origin request.
KalaVigyan already had Google sign-in with a single-use server nonce (`AuthNonce`), admission
through the access roster, the unverified-credentials rule and two-step challenges (PLAN 12). The
owner rules bind: reuse rather than invent, no comments, guards fail closed, no secret values
anywhere, web only.

## Decision

1. **Port, both providers.** `services/oidc_sign_in.py` keeps DR's providers, constants,
   redemption, issuer rules (Yahoo's fixed `https://api.login.yahoo.com`; Microsoft's per-tenant
   issuer bound to `tid` and `MICROSOFT_TENANT`), audience and `azp`, lifetime with a minute of
   leeway, nonce digest, verified-address rules (Yahoo `email_verified`; Microsoft personal tenant
   or `xms_edov`) and reason tags. A provider exists only when its client ID and secret are both
   set, so Microsoft is off. Adapted: `httpx` async instead of `requests` in threads (as
   `turnstile.py`), structured log extras, and the JWS checks (`RS256`/`ES256` only, refused
   before a key is read; key by `kid`, `use`, `alg`; keys cached an hour, refetched for an unknown
   key at most once a minute) moved to `services/signed_tokens.py` so both files stay inside the
   400-line budget. The key cache is one object with a single process-wide instance, the pattern
   of `core/rate_limit.SlidingWindow`.
2. **Nonce: DR's digest binding plus KalaVigyan's server nonce.** The browser asks
   `POST /auth/oidc/nonce {provider}` for a nonce (the `AuthNonce` table, purpose `OIDC_SIGN_IN`,
   10 minutes, stored hashed), sends the provider `base64url(sha256(nonce))` and returns the raw
   value with the code. The backend spends the nonce before it redeems anything, then requires the
   token's `nonce` to equal the digest. A token is accepted once, only from the tab that started
   the flow, and a forged login costs no call to Yahoo. The nonce store moved out of
   `google_auth.py` into `services/auth_nonces.py` now that two sign-ins use it.
3. **Redirect URI pinned.** DR accepts any `https` redirect URI and lets the provider compare it
   with the code. KalaVigyan accepts exactly `PUBLIC_WEB_URL` + `/login/callback`
   (`https://kalavigyan.vercel.app/login/callback`), the value registered with Yahoo, following
   PLAN 15 (`PUBLIC_WEB_URL` from config, never from the request).
4. **One account path for every provider.** Google's account logic in `api/routes/auth.py` became
   `sign_in_verified_mailbox(session, VerifiedMailbox)`, used by Google, Microsoft and Yahoo:
   roster admission before any write (unknown address: PENDING request; refused statuses: 403
   with `X-Access-Status`), the configured master admin, a never-verified account's password and
   two-step cleared and audited (`auth.unverified_credentials_cleared`), the roster `admitRole`
   adopted, `emailVerifiedAt` set. DR's provider rule now holds for all three: an existing
   account takes the new provider only while it is `LOCAL` without a password, and only Google
   sets the avatar. Before this change only `LOCAL` and `GOOGLE` existed, so Google behaves as it
   did. Sign-up policy is unchanged.
5. **Two-step and limits as for Google.** The login route challenges every account with two-step
   on, whatever the provider. The OIDC nonce route has Google's per-IP gate; the OIDC login also
   takes a per-IP sign-in attempt before redeeming and refunds it on a proved identity, as the
   password sign-in does, so failed codes count toward `SIGN_IN_ATTEMPTS_PER_IP`.
6. **Schema.** Migration `0010_oidc_sign_in` (after `0009_admin_role`) adds `MICROSOFT` and
   `YAHOO` to `AuthProvider` and `OIDC_SIGN_IN` to `AuthNoncePurpose` (`ENUM_ADDITIONS`, in an
   autocommit block). Its downgrade deletes `OIDC_SIGN_IN` nonces, turns `MICROSOFT` and `YAHOO`
   accounts back into `LOCAL` and recreates both types.
7. **Web.** `NEXT_PUBLIC_YAHOO_CLIENT_ID` draws "Continue with Yahoo"; blank draws nothing (no
   placeholder). `components/auth/OidcSignInButtons.tsx` holds DR's marks and buttons and
   `components/auth/useOidcSignIn.ts` the start (nonce, PKCE, `sessionStorage`) and the return.
   `/login/callback` is DR's route handler without the Android hand-off: KalaVigyan is web only,
   so an `app.` state no longer leaves the site. Refusal copy follows KalaVigyan's Google
   sentences ("Yahoo sign-in didn't work. Try again."). `/auth/config` reports `yahooEnabled`,
   `yahooClientId`, `microsoftEnabled` and `microsoftClientId` as it reports Google.
8. **No CSP change.** The browser only navigates to Yahoo (CSP does not govern top-level
   navigation) and never fetches from it; the backend redeems the code. A unit spec pins that the
   policy names no Yahoo host.
9. **Settings.** `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET`, `MICROSOFT_CLIENT_ID`,
   `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_TENANT` (backend) and `NEXT_PUBLIC_YAHOO_CLIENT_ID`,
   `NEXT_PUBLIC_MICROSOFT_CLIENT_ID`, `NEXT_PUBLIC_MICROSOFT_TENANT` (web). Deploy backend copies
   the backend names from GitHub into Parameter Store; `seed_secrets.py` sets a public client ID
   in Vercel only when the matching secret is stored. Registration and rotation are in
   `docs/RUNBOOK.md` (Yahoo sign-in).

## Consequences

- Nothing changes until the owner registers the Yahoo app and sets the three values.
- Tests: `backend/tests/test_oidc_sign_in.py` (token, address, redemption, redirect, schema and
  the DB-free routes), `backend/tests/db/test_oidc_sign_in_db.py` (marked `db`: admission, refusal,
  unverified address, a Master Admin's two-step challenge, nonce reuse, the Google account rule,
  the audited clearing), `frontend/e2e/oidc-sign-in-unit.spec.ts` (configuration, PKCE and nonce,
  storage, the callback route run as a handler, CSP). Expected values are derived by hand or from
  RFC 7636 appendix B, never from the code under test.
- The Settings card's "confirm it's you" step before a first password, inherited from DR, still
  has no backend in KalaVigyan for any provider (`docs/TECH_DEBT.md`). Cleared by decision 0028.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
