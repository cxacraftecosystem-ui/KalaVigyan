# 0155. The roster offers what its guards allow, a recovery code may add a first password, roles sort and cap by rank, and a stopped share's files leave the bucket

Each access roster row carries the actions its viewer may take, computed by the routes' own guards;
a first password takes a recovery code for the two-step code; users sort by rank; a role a stored
cap map does not name reads its own default; and the files a share's readers were given are
recorded and deleted when the share stops.

Date: 2026-11-23. Status: accepted (the lead's round 7 debt brief, accounts and sharing lane). It
amends [decision 0024](0024-admin-role.md) (the roster screen), [decision
0028](0028-first-password-provider-proof.md) (item 5, "Two-step stays `two_factor.step_up`") and
[decision 0097](0097-public-reading-everywhere-but-asking.md) (the shared files). The contracts are
`docs/contracts/backend.md` (Auth, Access roster, Manage users, Settings),
`docs/contracts/frontend.md` (roles) and `docs/contracts/learning.md` (Share links).

| For | Read |
|---|---|
| The admin role and the rank rule it keeps | [decision 0024](0024-admin-role.md) |
| The first-password proof it amends | [decision 0028](0028-first-password-provider-proof.md) |
| The share links whose files it deletes | [decision 0097](0097-public-reading-everywhere-but-asking.md) |
| No AI cap by default | [decision 0093](0093-no-caps-for-now.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Six debt entries of `docs/TECH_DEBT.md` were open in this area on 2026-11-22.

- **The roster screen judged an entry by its own role.** `accessEntryOffers`
  (`frontend/lib/accessRoster.ts`) hid actions by the entry's `admitRole`, while the routes also
  refuse when the account at the address ranks at or above the viewer, so an Admin saw Update and
  Suspend on an entry saying PROFESSOR whose account had been made ADMIN, and got a 403.
- **Sorting users by role followed the enum.** `UserRole` lists `ADMIN` and `ARTISAN` after
  `STUDENT` (Postgres appends a new value), so `GET /users?sort=role&dir=desc` ran Artisan,
  Admin, Student, Researcher, Professor, Master Admin.
- **A role cap map could lack a role.** `PUT /settings/ai-budget` already merged the sent roles
  into the stored map (`app_settings.budget_changes`), but a stored map saved before a role existed
  (Admin came with migration 0009, Artisan with 0028) still lacked it, and `Ceilings.role_cap`
  gave a role it did not find the Student's cap.
- **A recovery code was offered for a first password but not taken.** The Settings card lets an
  account with two-step on type a recovery code before its first password; the route checked it with
  `two_factor.step_up`, which takes only an authenticator code, and a lock answered as a wrong code.
- **First-password proof not yet seen running.** Its route tests and unit spec run on every push;
  only a person's round trip through Google or Yahoo in a browser is missing.
- **A stopped share's files stayed in the bucket** until the `exports/` rule removed them (7 days).
  The app's IAM user could not delete under `exports/` at all.

## Decision

1. **The roster row carries its offers.** The three access guards are pure functions in
   `services/access_guards` (`bar_refusal`, `change_refusal`, `reinstate_refusal`, each from the
   actor, the entry and the account at its address, answering the refusal sentence or `None`); the
   routes answer a refusal as 403 with that sentence, and `GET /access/roster` sends each row's
   `offers {update, suspend, admit, refuse}` from the same functions (`entry_offers`), reading the
   page's accounts in one query (`accounts_at`). The web draws exactly the row's `offers`, and none
   when a row has none; `permissions.canManageAccessEntry` is gone. The other choice, sending the
   account's role on each row for the web to judge, would keep a second copy of the guards in
   TypeScript.
2. **A recovery code may add a first password.** The first-password route checks the code with
   `check_second_factor(..., allow_recovery=True)`, so a recovery code is taken and spent, and a
   second factor locked by wrong codes answers 429 before the provider proof is spent (the lock of
   the code's own budget is read first; a lock taken meanwhile is also 429). The other choice was
   to drop the recovery code from the card. A recovery code already signs in and turns two-step off
   (`two_factor.disable` takes one), so refusing it here would protect nothing an attacker holding
   one could not reach another way, while a person who lost their authenticator could not add a
   password. The key and settings step-ups and the Google link stay authenticator-only.
3. **Users sort by rank.** `sort=role` orders by `CASE role WHEN ... THEN ROLE_RANK[role]`, so
   `dir=desc` runs Master Admin, Admin, Professor, Researcher, Artisan, Student. Recreating the enum
   type in rank order was the other choice; it needs a migration of five columns and breaks again
   with the next role.
4. **A stored role cap map is laid over the defaults.** `spend_settings.stored_spend_value` lays a
   stored `AI_ROLE_DAILY_USD` map over the default (every role, no cap); `load_spend_settings`,
   `app_settings.load_all`, `app_settings.get_value` and `Ceilings.from_settings` read through it,
   so the budget, `/usage/me`, the settings screen and the next merge all see every role. A role the
   map still does not name (none of `ROLE_RANK`) reads the lowest role's cap, as daily allowances do.
   Refusing a map that does not name every role was the other choice; it would break the partial
   updates the screen sends.
5. **The files of a share are recorded and deleted when it stops.** The shared PDF and lesson-file
   routes wrap the bucket in `shared_files.SignedKeys`, which notes each key a link is signed for,
   and record the keys against the share's token (`SharedExportFile`, migration
   `0079_shared_export_files`; a key recorded again moves to the newer token). Every path that stops
   a share (the owner's stop, deleting a lesson, suspending, refusing or deleting an account, a role
   losing `BUILD_LESSONS`) takes the bucket as `objects` and calls
   `shared_files.drop_stopped_share_files` in its transaction: the recorded files no live share
   holds are deleted from the bucket (at most 200 a call) and their records removed. A file the
   bucket refuses to delete keeps its record for the next sweep and is logged. A file recorded after
   its share stopped is deleted at once. The keys stay under the neutral owner id, so the IAM grant
   (`AppStoppedShareFiles` in `infra/terraform/iam.tf`) allows `s3:DeleteObject` under
   `exports/00000000-0000-0000-0000-000000000000/` only; the owner's own exports stay put-and-read.
   Keying each share's files by its own prefix and listing it at the stop was the other choice; it
   needs the token at every stop and a wider delete grant.

## Consequences

- An object is deleted before the stop commits: if the commit fails, the share is still on and its
  next reader rebuilds the file, since every link checks the object first.
- Until `AppStoppedShareFiles` is applied, every stop logs that its files are kept for the next
  sweep, and the `exports/` rule removes them as before. The RUNBOOK's Terraform section says how to
  apply it.
- `apply_role_change`, `withdraw_shares`, `bar_account`, `unshare_answer`, `unshare_lesson`,
  `delete_lesson`, `upsert_password_account` and the E2E provisioning functions take `objects`
  (the bucket, or `None` when no bucket is configured and so no shared file can exist). The routes
  and the operator scripts pass `media_bucket()`.
- The roster list makes one more query per page, for the accounts at its addresses.
- Tests: `backend/tests/test_access_guards.py`, `backend/tests/test_ai_budget_settings.py`,
  `backend/tests/db/test_admin_role_db.py` (the role sort and the roster offers),
  `backend/tests/db/test_role_caps_db.py`, `backend/tests/db/test_first_password_db.py` (a recovery
  code, a locked second factor), `backend/tests/db/test_share_links_db.py` (the files of a stopped,
  late, refused and re-shared share), `backend/tests/learning/test_share_links.py` and
  `frontend/e2e/permissions-unit.spec.ts`. Expected values are written by hand.
- What is left of the first-password proof is a person's round trip in a browser after a deploy
  (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
