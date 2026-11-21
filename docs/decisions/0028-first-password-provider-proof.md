# 0028. A first password needs a fresh provider proof: DR's rule, ported

An account with no password sets its first one only with a fresh proof from Google, Microsoft or
Yahoo: the designer portal's rule, ported and made stricter in four ways. One service holds the
rule, and the rest of change-password is unchanged.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

The Settings card `frontend/components/settings/ChangePasswordCard.tsx` came from the designer
portal (DR) with a "confirm it's you" step: an account with no password signs in again with
Google, Microsoft or Yahoo and sends that proof with its first password to
`POST /auth/change-password`. KalaVigyan's route took no proof fields: without two-step it always
refused ("Use a set-password link"), with two-step it took the code alone. The step therefore
always ended in a refusal (`docs/TECH_DEBT.md`, Yahoo sign-in). DR's rule (DR `docs/SECURITY.md`,
"A FIRST password on a provider-only account"): a Google ID token verified as at sign-in, or a
Microsoft or Yahoo code redeemed and verified as at sign-in; issued within five minutes; the
verified address is the account's own; refused 400 with `X-Confirm-Provider` and nothing written;
with two-step on, the code too. DR does not bind the proof to a server nonce: its Google button
sends no nonce and its Microsoft and Yahoo nonce is made in the browser, and it remembers a
redeemed proof in process memory so a wrong code can be retried. KalaVigyan's sign-ins all spend a
single-use server nonce (`AuthNonce`, decisions 0026 and PLAN 12). The other choice in the debt
entry, a set-password link mailed to the verified address, needs mail to be configured and leaves
the card's step unused.

## Decision

1. **Port DR's provider proof.** `ChangePasswordRequest` takes `googleIdToken` or the five `oidc*`
   fields; the five fields and their all-or-none rule now live once in `schemas/auth.OidcCodeFields`,
   shared with `LoginRequest` (`has_oidc_login` became `has_oidc_code`). Both proofs at once is a 422.
2. **Stricter than DR, in four ways.**
   - The proof must come from the account's own provider (`authProvider` `GOOGLE`, `MICROSOFT` or
     `YAHOO`); DR accepts any of them for a matching address. A `LOCAL` account without a password
     is told to use a set-password link, as before.
   - The proof spends a server nonce of the new purpose `FIRST_PASSWORD`, bound to the signed-in
     account: `POST /auth/first-password/nonce` (no body) answers `{nonce, expiresAt, provider,
     clientId}` for the account's provider, 409 when the account has a password, 400 without a
     provider, 404 when that provider is off. Google's ID token must carry the nonce
     (`google_auth.verify_with_nonce`); Microsoft and Yahoo send its digest to the provider as at
     sign-in. A sign-in or link nonce, or one issued to another account, confirms nothing.
   - Microsoft and Yahoo: the nonce is spent before the code is redeemed (`oidc_sign_in.prove_once`,
     now also the path of the OIDC sign-in), so a replayed proof costs no call to the provider. A
     proof from another provider is refused before anything is spent or redeemed.
   - No process-memory cache of confirmed proofs (DR's `_CONFIRMED_PROOFS`): module state is
     against `backend-practices`, and the nonce already makes a proof single use. Instead the route
     asks for a missing two-step code before it spends the proof; a wrong code spends it, and the
     card then asks the user to confirm again.
3. **Freshness as DR.** `iat` within `PROOF_MAX_AGE_SECONDS` (300) before now and at most
   `PROOF_LEEWAY_SECONDS` (60) after; a token with no numeric `iat` is stale. The address is
   compared trimmed and lower-cased, as the sign-ins store it.
4. **One service.** `services/provider_proof.require_fresh_proof(session, account, proof)` holds the
   rule and raises `ProofRefused(provider, reason)`; the route turns every refusal into 400 with
   `X-Confirm-Provider` naming the account's provider and DR's sentence ("That Google sign-in didn't
   match this account or has expired..."), never a 401, which would sign the web client out.
   No proof at all answers DR's "To add a password, first confirm it's you by signing in with
   Google again." Refusals are logged with the provider and a reason tag only. Both routes live in
   `api/routes/password_change.py`, moved out of `api/routes/auth.py`, which is over its file
   budget; `auth.code_grant` builds the `CodeGrant` for the OIDC login and the proof alike.
5. **The rest of change-password is unchanged.** The per-account sign-in budget is taken first and
   refunded on success; a password account still needs its current password and proof fields do
   nothing for it; success bumps `tokenVersion`, revokes outstanding links, answers a fresh
   `X-Session-Token`, mails the owner, and records `auth.password_changed`, now with detail
   `{firstPassword: true, provider}` for a first password. Two-step stays `two_factor.step_up`.
6. **Schema.** Migration `0011_first_password_proof` (after `0010_oidc_sign_in`) adds
   `FIRST_PASSWORD` to `AuthNoncePurpose`; its downgrade deletes those nonces and recreates the type
   with the three values before it.
7. **Web.** `ConfirmItsYou` moved out of the card into `components/settings/ConfirmItsYou.tsx`. Its
   Google button gets a confirmation nonce through `useGoogleNonce(fetcher)`; its Microsoft and Yahoo
   button asks `fetchFirstPasswordNonce` before leaving (the browser made its own nonce before). The
   `pw.` state still brings the provider back to `/settings`, where `confirmReturn` turns the
   fragment into the five fields (`OIDC_TAB_LOST` moved to `lib/oidcSignIn.ts` for it).
   `setFirstPassword` builds its body with `firstPasswordBody`. `MIN_PASSWORD_LENGTH` is now 10,
   the minimum of every password route of the API (it said 8, so a nine-character password passed
   the form and was refused by the server).
8. **CORS** exposes `X-Confirm-Provider` with the other headers the web client reads.

## Consequences

- An account that signs in with Google, Microsoft or Yahoo can add a password in Settings.
- Tests: `backend/tests/test_provider_proof.py` (the rule with a fake nonce store, a fake Google
  verifier and the fake IdP: Google and Yahoo accepted; another address, another provider, a reused
  nonce, a sign-in or another account's nonce, a stale token, an unverified Google address and no
  proof refused; the freshness bounds; the body; the migration), `backend/tests/db/test_first_password_db.py`
  (marked `db`, the routes end to end on GitHub Actions, including the password account and the
  two-step order), `frontend/e2e/first-password-unit.spec.ts` (the nonce request, the round trip
  back to `/settings`, the fields sent). Expected values are written by hand.
- The card offers a recovery code for the two-step code, but `step_up` takes only an authenticator
  code (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
