# 0024. Admin role

An Admin role (rank 50) sits between Professor and Master admin and holds inviting professors,
changing roles, disabling users, usage, the audit log and datasets, while keys, routing and quotas
stay with the master admin. An admin acts only on accounts ranked below its own and needs two-step
verification.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The roster's offers from the routes' guards, and users sorted by rank | [decision 0155](0155-accounts-and-sharing-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked for a role between Professor and Master admin, so that people management can be
shared without handing over keys, routing or spend. Until now only the master admin held
INVITE_PROFESSORS, CHANGE_ROLES, DISABLE_USERS, VIEW_USAGE, VIEW_AUDIT_LOG and MANAGE_DATASETS,
so the routes behind DISABLE_USERS (suspend, restore, two-step reset, delete) never checked the
target's rank: the only caller could manage everyone. The designer portal already has `ADMIN` at
rank 50, and the portals are meant to merge.

## Decision

1. **Rank and label.** `ADMIN` ranks 50, between `PROFESSOR` (40) and `MASTER_ADMIN` (60), as in
   the designer portal; its label is "Admin". `shared/roles.json` records the five ranks and
   labels, and a backend test and a frontend spec each check their side against it.
2. **Capabilities.** The minimum role of INVITE_PROFESSORS, CHANGE_ROLES, DISABLE_USERS,
   VIEW_USAGE, VIEW_AUDIT_LOG and MANAGE_DATASETS drops to `ADMIN`, so an admin holds everything
   a professor holds plus these six. MANAGE_KEYS, MANAGE_ROUTING, MANAGE_QUOTAS and
   MANAGE_CEILINGS stay with the master admin: keys are secrets and the other three spend money.
   Usage and the audit log are read-only oversight an admin needs to manage people.
3. **Only below Admin.** An admin acts only on accounts and roster entries ranked below its own,
   through the existing rank rules: `assignable_roles` gives an admin Professor, Researcher and
   Student, and `may_manage_target` refuses an Admin or Master admin target. Only the master
   admin assigns `ADMIN` or `MASTER_ADMIN`, and only it creates, changes, suspends or removes an
   Admin or Master admin account or roster entry. To make that hold everywhere:
   - two shared guards in `core/deps.py`, `refuse_unless_assignable` and
     `refuse_unless_manageable`, now run on every Manage users change (role, name, suspend,
     restore, sign-out everywhere, two-step reset, delete). Before, a role change did not check
     that the new role was assignable, and suspend, restore, reset and delete did not check rank;
   - on the access roster any change to an entry, not only to its role, and any decision on an
     entry that is not barred, is refused when the entry's role or its account's role is at or
     above the actor's. Adding an address checks the role it will join with, the default role
     included, so only the master admin may add the address named by `MASTER_ADMIN_EMAIL`
     (which joins as Master admin);
   - the default sign-up role (`DEFAULT_SIGNUP_ROLE`) can never be `ADMIN` or `MASTER_ADMIN`; it
     falls back to Student.
4. **Two-step verification** is required for admins, as for professors and the master admin.
5. **Allowances.** 3600 voice seconds, 100 images and 20 videos a day, the owner's numbers, inside
   the global monthly ceiling and media cap. The owner did not name a daily AI spend; the role
   cap is $10, twice the professor's $5, because the allowances are twice the professor's. The
   master admin can change it in `AI_ROLE_DAILY_USD`. Without an `ADMIN` key in the stored map an
   admin would fall back to the student's $0.50, so the migration adds it.
6. **Migration `0009_admin_role`** (after `0008_media_jobs`) adds the enum value inside an
   autocommit block, because Postgres cannot use an enum value in the transaction that added it
   and the same migration seeds rows with it; it then adds the three `QuotaPolicy` rows and the
   `ADMIN` key of `AI_ROLE_DAILY_USD`. Postgres cannot drop an enum value, so the downgrade does
   what `0002_portal_alias_source` does: it recreates the type without `ADMIN` and retypes the
   six `UserRole` columns, turning any `ADMIN` into `PROFESSOR` (one rank down, still with
   two-step verification, fewer rights), after deleting the admin quota rows and cap. The value
   is appended to the type, as `ENUM_ADDITIONS` records and the schema test expects, so ordering
   by the enum puts Admin after Student; only `GET /users?sort=role` orders by it, and the web
   client never sends that sort.
7. **Web client.** `lib/permissions.ts` adds the rank and label. The settings hub and Usage open
   to admins; API keys and AI routing stay master-only. Each admin nav item is shown by its own
   route guard (`routeAllows`) and the hub lists the areas whose guard admits the viewer, so nav,
   hub and guard cannot disagree. Manage users offers role changes, suspension, restore and
   two-step reset to admins for accounts below them. The access roster shows only the actions the
   viewer may take on each entry (`accessEntryOffers`), judged by the entry's role; the server
   also checks the account's role. Nothing is drawn disabled with an explanation. The admin view
   toggle stays with the master admin; it is now `hasAdminView`, so the old `isAdmin` no longer
   reads as the new role, and an admin sees its admin areas without a toggle. The unused
   `canProvisionAccounts` and `provisionableRoles` are deleted.
8. Refusal sentences name "admins" where an admin now qualifies.

## Consequences

- When the audit-log and dataset routes are built they must use `require(Capability.VIEW_AUDIT_LOG)`
  and `require(Capability.MANAGE_DATASETS)`, so admins get them without another change.
- Professors are held to the same rank rule on the roster: they no longer see or use actions on
  entries at or above Professor, and cannot restore a refused or suspended entry (that needs
  DISABLE_USERS, as the backend already required).
- The access roster screen hides actions by the entry's role only; an entry whose account holds a
  higher role than the entry still shows them, and the server refuses with a sentence.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
