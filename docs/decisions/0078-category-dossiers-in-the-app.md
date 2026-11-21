# 0078. Category dossiers are imported keyed to their category and served as public category pages

Category dossiers are imported into two new tables keyed by the dossier's slug, by the same writers
and deploy-time import as crafts, and served as public category pages. They have their own contract,
and goldens built from a fixture.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contracts it names | [category-page.md](../contracts/category-page.md), [curation.md](../contracts/curation.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Curators now write one cited master dossier per craft category
(`backend/app/data/curation/categories/<CategorySlug>.json`, scope `CATEGORY`, decision 0051 and
`docs/plans/dataset-curation.md` section 3.16), checked and verified like a craft's. Until now the
importer read only the top folder, so nothing a category dossier holds reached a reader. The owner
chose on 2026-11-18 that category, craft, map and science pages are readable without signing in,
and that curated content goes live daily as data. Build task CAT asks for the import (only
dossiers whose checks pass, hooked into the deploy-time import), `GET /api/categories` and
`GET /api/categories/{slug}` as public routes with ETags, goldens both sides check, the contract
page and DB tests for idempotence and supersession, with at most one migration in the run.

## Decision

1. **Two new tables, the craft tables untouched.** Migration `0026_curated_categories` adds
   `CuratedCategory` (the category's version, coverage, digest and page index, like
   `CuratedCraft`) and `CuratedCategoryClaim` (the mark that a claim is the category's, like
   `CuratedClaim`), both keyed to `CraftCategory.id`, with row level security and no grants to the
   Supabase roles. Making `CuratedCraft` and `CuratedClaim` hold either a craft or a category was
   the alternative; it would have loosened a non-null craft key that the craft page, comparison
   and saved re-checks read, for no gain.
2. **The same writers, keyed by the dossier's slug.** The row builders and writers of the craft
   import now take the dossier's slug (`Dossier.slug`, the craft or category slug) and an owner
   instead of assuming a craft: `concept_plan(dossier, *, craft_id, name)`,
   `curated_claim_rows(dossier, owner_column, owner_id)`, `write_claims(session, marked, ...)`
   with the select of the owner's marked claims, `write_evidence(..., marker=)`,
   `write_media_and_terms` (pictures and glossary, shared by both imports), `overview_pieces(dossier,
   cited, *, craft_id, districts)`, `placed_overview`, the `index_*` builders and `plan_views`.
   For a craft dossier every id and row is what it was; the craft goldens did not change. Ids are
   `curation:<categorySlug>:...`, and a test pins that no category slug is a craft slug.
3. **What a category stores.** Sources, claims and quotes as for a craft; subjects as `Concept`
   rows with neither a craft nor a sub-category, so no craft's retrieval scope reaches them and a
   question asked without a craft can; pictures as `MediaRef` and `MediaRefClaim`; the glossary as
   `Term` and `TermConcept`; the overview as `prose` knowledge pieces with no craft, through the
   answer engine's prose validator. Places, stages, materials, tools, market and environment
   entries stay claims and concepts: `CraftLocation`, `Process` and the market tables belong to
   crafts. The page index records which sub-categories and member crafts each kept overview
   sentence names, keyed by the stored piece's sentence ids.
4. **One deploy-time import.** `app.scripts.import_curation` imports the category dossiers right
   after the craft dossiers, in the same session, and reports them under `categories`. A
   category dossier whose checks or check file fail is refused like a craft's and exits 2, which
   stops a release; CI's `check.py` refuses it first. A second import writes nothing; a new
   version supersedes a dropped claim and keeps its citations.
5. **Public routes with the public reading pattern.** Both routes take `api/public_deps.
   public_reader` (anonymous readers rate limited by address) and `cached_read` (an ETag that is
   the SHA-256 of the body, 304 on a match, `public, max-age=300` without a session and
   `private, no-cache` with one). Nothing on a category page depends on a role.
6. **Its own contract.** `research/category_page.py` is versioned apart from the craft page
   (which is changing to its second version), reusing only the shared citation, source, media,
   term and sentence shapes. Sources are numbered 1 to N by first citation in reading order, on
   the server, so a number never differs between parts of the page. A sub-category shows the
   first overview sentence that covers it and the open question that names it; member crafts run
   curated, then GI-registered, then by name, catch-all rows last and outside the counts. Labels
   and palettes come from `data/craft_families.json`.
7. **Goldens from a fixture.** The curated golden is built from
   `backend/tests/curation/fixtures/categories/Leather-Craft-Category.json`, a THIN subset (21
   claims, 13 sources) of the verified Leather dossier with a check file the tests regenerate
   from, so curators editing the real dossier never move the golden.

## Consequences

- Readers see a category page as soon as its dossier is pushed and the import runs; until then
  the page shows the register: sub-categories, member crafts and counts.
- Category claims and pieces get vectors from the nightly `embed_knowledge`, like a craft's.
- `docs/contracts/category-page.md` is the contract; `docs/contracts/curation.md` describes the
  import of both scopes.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
