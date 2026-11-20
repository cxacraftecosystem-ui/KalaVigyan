# Dossier export and the curation write path (decision 0101, item 6)

The database is the source of truth for curated knowledge. The dossiers in
`backend/app/data/curation` (`docs/contracts/curation.md`) become its versioned export: a backup
in git, a diff against what the database holds, and the way to bulk import. New facts are written
through the Knowledge API (`docs/contracts/knowledge-writes.md`), where they pass the four gates;
`tools/curation/propose.py` sends a working dossier's new facts there. The curation skill
(`.claude/skills/kalavigyan-craft-pages`) keeps the method and says which change goes which way.

Last reviewed: 2026-11-19.

Code: `services/dossier_export.py` (the run, the git file it compares with, the report),
`services/dossier_export_store.py` (the stored rows it reads), `services/dossier_export_records.py`
(the read model), `services/dossier_export_assembly.py`, `dossier_export_claims.py`,
`dossier_export_parts.py`, `dossier_export_overview.py`, `dossier_export_market.py` (the dossier
rebuilt from those rows), `services/dossier_diff.py` (what differs from git),
`curation/dossier_text.py` (the file text), `scripts/export_dossiers.py` (the command);
`tools/curation/propose.py` and `tools/curation/proposing.py` (the client).

## The promise

Exporting a dossier the import stored, then importing the export, changes nothing: the same
claims, quotes, sources, concepts, stages, materials, reactions, pictures with their placement and
focal box, GI, price and workforce records, overview pieces and page index. When the dossier in git
is the version the database holds, the export is that file byte for byte, except a file laid out
by hand (`LAYOUT`, below), whose content is the same. Tested on every curated dossier through the
import's own plan (`tests/curation/test_dossier_export.py`) and through the database
(`tests/db/test_dossier_export_db.py`: Kutch Ajrakh exports as its file; exporting every dossier
and importing the export changes no row and writes no review event, apart from the stored file
digest of a dossier laid out by hand).

## What it reads

| Dossier part | Read from |
|---|---|
| header | `CuratedCraft` or `CuratedCategory` `page` (version, `curatedAt`, coverage, searched); scope `FAMILY` when the craft register names the craft a family, else `CRAFT`, or `CATEGORY` |
| claims | the page's `claimOrder` (a category: its `CuratedCategoryClaim` claims not `SUPERSEDED`); `Claim` text, field, level (`HYPOTHESIS` is `hypothesis: true`), sensitivity; the key and discipline from the curated marker; the subject from the concept's `originRef` (`curation:<slug>:<key>`), a place's concept back to the place the page names, a discipline concept back to `CRAFT` |
| quotes | `ClaimSource` rows found by `curation`, with their locator and quote |
| sources | `Source` rows the dossier owns (`externalIds.curation` `<slug>:<key>`), with `archivedUrl`, `language` and `access` from `externalIds`, `subKind` from `evidenceKind`, `retrievedAt` as a day |
| places, communities, materials, tools, environment, glossary, conflicts, open questions, native names, key facts | the page index |
| stages | the page index (order, local name, timing, `after`, why, claims) with `ProcessStage` name and type and `StageMaterial` uses split into materials and tools |
| reactions | the page index (a category's keep the stage git gives them) |
| pictures | the page index (caption, claims, placement, focal box, size, stand-in) with `MediaRef` address, page, author and licence |
| overview | the stored `KnowledgePiece` prose of the lede and each section |
| market | `CraftGiRecord`, `CraftPrice` (its place found by name and id) and `CraftWorkforce` |

## What the dossier in git still gives

The export reads the dossier in git, when there is one, only for what the database does not keep.
Each such use is listed in the report's `keptFromGit`.

- Order: claims follow the page's claim order, then git's; quotes within a claim, a stage's
  material and tool uses, sources, prices and workforce rows follow git's order, then their keys.
- Layout: keys in git's order, the empty parts git writes, git's indent. Without a git file the
  text is two-space JSON without the parts left at their defaults.
- A source cited through another dossier's stored source of the same DOI: kept as git gives it.
- An overview sentence the import's prose validator dropped, when git holds the same version and
  `curatedAt`: kept where git has it.
- A category's places, communities, stages, materials, tools, environment, native names, market
  and its reactions' stages, which the category import does not store. A category is therefore
  exported only beside its dossier in git, of the version and `curatedAt` the database holds.

## Refusals

A dossier is refused, and the others still exported, when its slug is neither a craft of the
register nor a category; it has no stored dossier; its page index no longer meets its model; a
claim has no curated key; a record cites a claim the dossier does not hold; a quote cites a source
that is neither the dossier's own nor one git names by its DOI; a stage has no stored process
stage; a picture has no media record; a price names a place the dossier lacks; a category has no
dossier in git, or git holds another version; or the git file does not parse.

## The command

From `backend`: `python -m app.scripts.export_dossiers (--diff | --out <folder>) [--slug <slug>
...] [--git <folder>]`. `--git` is the folder of dossiers to compare with and to take order and
layout from (default `app/data/curation`). `--out` writes `<slug>.json` and
`categories/<slug>.json` there, only the files whose text differs; `--out app/data/curation`
refreshes the export in git. It never writes check files: a written dossier whose `checkFile` is
not `CURRENT` needs `tools/curation/verify.py` before the import will take it.

It prints one JSON report: `exportedAt`, `exported`, `changed`, `refused [{slug, problem}]`,
`written` (with `--out`), and per dossier:

| Field | Meaning |
|---|---|
| `file`, `slug`, `version` | the exported dossier |
| `status` | `SAME` (the git file, byte for byte), `LAYOUT` (the same content, laid out otherwise), `CHANGED`, `NEW` (no git file) |
| `checkFile` | `CURRENT` (git's check file still verifies the export), `STALE`, `MISSING` |
| `changes` | what differs from git: `version: 2 in git, 3 stored`; per part with ids `claims: added C144; removed C12; changed C13 (text, quotes)` or `reordered`, at most 12 ids then `and N more`; `market: changed` for a part without ids; `the dossier is not in git yet` |
| `keptFromGit` | each thing taken from git, above |
| `quotesFailingRecheck` | the dossier's quotes whose stored check is no longer `PASS` |
| `reviewed` | claims a person's review moved off `APPROVED`, as `C12: RETRACTED`; the dossier keeps them, and the import never undoes a review |

Exit 2 when a dossier is refused; with `--diff`, 1 when any is `CHANGED` or `NEW`; else 0.

## Proposing new facts (`tools/curation/propose.py`)

From the repository root: `python tools/curation/propose.py <working dossier> [--stored <file>]
[--api <origin>] [--receipt <file>] [--only <claim id> ...] [--dry-run]`.

- **New facts** are the working dossier's claims that the stored dossier (`--stored`, by default
  the export in git) holds neither by claim id nor by the same wording (case, surrounding space and
  final stops folded, as the duplicate gate folds them).
- **Each becomes one `FactProposal`**: subject `{kind: craft, slug}` (a category dossier's
  `category`), `field` the claim's discipline, `statement` its text, and per source, in the order
  the quotes first cite it, `{url, title, licence, quotes [{text, locator}]}`.
- **Not sent**, with the reason: a hypothesis, a fact that is not `OPEN`, more than 5 sources,
  more than 6 quotes of one source, or a proposal the model refuses (length, personal data).
- **Sent** with `Authorization: Bearer <token>` to `POST <origin>/api/knowledge/facts`, one at a
  time. The reply's outcome is printed per fact: `PUBLISHED, claim <id> (<status>, <level>)`,
  `WAITING for review, claim <id> (...)`, or `REFUSED at <gate>: <reasons>`. A 422 or 503 is
  printed as not stored and is not recorded, so a later run sends it again. A 401 or 403, or an
  unreachable API, stops the run.
- **The receipt**, `<slug>.proposals.json` beside the working dossier: `{schemaVersion 1, slug,
  proposals {<claim id>: {digest, outcome, claimId, status, message}}}`. A fact whose proposal
  (its SHA-256) is unchanged since a recorded reply is not sent again; editing the fact sends it
  again.
- **Token and address**: the token is read from `KALAVIGYAN_TOKEN` and is a signed-in session
  token of a Researcher or above (the `accessToken` that `POST <origin>/api/auth/login` returns,
  or the site's session cookie; it lives as long as the session). An MCP OAuth access token is
  for `/api/mcp` only: an agent there proposes through `propose_fact`. The address is
  `KALAVIGYAN_API` or `--api`, the API origin (`PUBLIC_API_URL`), not the site, which refuses a
  write that does not come from its own pages.
- `--dry-run` needs neither and prints what would be sent. Exit 0 when every new fact got a
  reply, 1 when any was not sent or not stored, 2 for a usage problem or a stopped run.

The API and the MCP server also take structure (`propose_structure`: a stage's `after` or why,
native names, reactions, botanical names, glossary, conflicts, open questions, the GI record), new
sources for held facts (`propose_source`), components and whole page bundles (`knowledge-writes.md`,
`open-work.md`), and the curation skill sends every change it can that way. The placements of
open-licence pictures from elsewhere and a new craft's first dossier still enter through a bulk
import: a new dossier version, verified and checked, committed by the lead and imported on deploy,
after which `--diff` reports `SAME` for it.

## Versioning

The export writes dossier schema 2 and changes with it. The report and the receipt are tools'
output, not served contracts; a change that removes or renames a field of either updates this
page in the same change.
