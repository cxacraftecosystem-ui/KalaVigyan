# 0003. Crafts from both portals, synced through a new peer route

Every craft added in the designer or documentation portal reaches KalaVigyan through one signed peer
route both portals serve, `GET /api/cross-portal/peer/crafts`, keyed by slug into one row. The
master list always wins, a colliding rename becomes an alias, and a portal that fails is reported
while the other is still applied.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contracts it names | [portal-craft-feed.md](../contracts/portal-craft-feed.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner wants every craft either team added in the designer portal or the documentation portal
to be present in KalaVigyan, not only the 455 master crafts (PLAN section 0). PLAN 5.1 (P1a)
foresaw a designer-portal peer route and an upsert by slug. Neither portal serves one: the
catalogue route needs a signed-in user and returns normalised aliases, and the existing peer
routes search records. KalaVigyan may not edit the portal repositories.

## Decision

1. **Route.** One identical peer route in both portals, `GET /api/cross-portal/peer/crafts`,
   specified in `docs/contracts/portal-craft-feed.md`. It reuses the portals' peer mechanism
   (bearer, nonce, signed answer) and the shared `CROSS_PORTAL_TOKEN`, behind its own flag so it
   does not depend on the identity flag or the Aadhaar key. One unpaged answer: the list is small.
   The name differs from PLAN's `/cross-portal/crafts` because the peer prefix is what the
   portals' signing (`peer_path`) and their `/peer` routers are built around.
2. **Adapter.** `services/portal_peer.py` is the one adapter for both portals; it signs and checks
   exactly as the designer portal's `cross_portal.sign` does (a test pins a signature computed
   with that function). The feed is validated on load (`services/portal_craft_feed.py`) and
   tolerates unknown fields, so a portal can add fields within version 1.
3. **Identity.** A craft is keyed by slug, matched else by normalised name in the same
   sub-category, so the same craft added in both portals becomes one row. A new row's id is
   `seed_uuid("c", slug)`, the master list's rule, so ids are stable across environments and
   reruns. Matching by the portals' own ids was rejected: the two portals have different ids
   for the same craft.
4. **Master list wins.** The sync never changes a master craft's name, columns or status; it
   only records `extraMetadata.portalSources` and adds the portal's names as aliases. A portal
   merge of a master craft is recorded, not applied, so the master list stays whole.
5. **Several portals, one row.** Columns of a portal-only craft come from the portal that first
   brought it (`portalOrigin`; designer portal first when both arrive together), so a run
   without that portal never flips them. Status is the most visible of the portals' statuses:
   `ACTIVE` if any lists it active, else `MERGED` (followed to the end of the chain, refused on
   a loop), else `LEGACY`. A craft no portal lists any more becomes `LEGACY` and is not deleted,
   because claims and answers may point at it.
6. **Renames that collide.** A rename onto a name another craft holds in the same sub-category
   keeps the stored name, adds the new one as an alias and is reported (`nameConflicts`), rather
   than failing the whole run on one row.
7. **Alias sources.** Designer-portal names keep the existing `DR_SYNC`; documentation-portal
   names get a new `AliasSource` value `FR_SYNC` (migration `0002_portal_alias_source`). The
   schema tests now read `ENUM_ADDITIONS` from later migrations, so a value added after the
   initial migration is checked the same way.
8. **Failures.** A portal that cannot be reached, answers unsigned, or sends a feed that breaks
   the contract is reported by name and its recorded sources are kept; the other portal is
   still applied, and the script exits 1. On deploy this is a warning (the release must not
   wait for a portal), in the daily workflow a red run. A master craft missing from the database
   stops the sync, because the planner would otherwise insert master slugs as portal crafts.
9. **Runs.** After the seeds on every deploy, and daily on the box through SSM (the box already
   holds the settings; the runner holds none).
10. **Shared pieces.** `alias_norm` and `SCRIPT_LANG` moved from `etl/crafts/aliases.py` to
    `app/data/craft_text.py` (second caller), with `alias_lang`. The two private `_chunks`
    helpers became `itertools.batched`, and the two `_ids_by_slug` copies became
    `craft_seed.ids_by_slug`.

## Consequences

- Until both portals ship the route, every run reports `not_found` for each portal and changes
  nothing; deploys print a warning and the daily workflow fails (`docs/TECH_DEBT.md`).
- The portals need `CROSS_PORTAL_CRAFT_FEED_ENABLED=true` on both boxes, in their GitHub
  secrets and box `.env`, when the route ships.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
