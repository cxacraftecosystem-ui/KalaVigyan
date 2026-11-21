# 0051. Curation tooling: the dossier model, fetch, verify and check

Curation has one shared dossier model with its rules as pure functions beside it, reading through
the app's own extraction, an independent quote verifier and a checker that writes the index. Its
wave 1 changes, after the pilot, refined how numbers and hedges match and when the index is written.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contracts it names | [curation.md](../contracts/curation.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner approved dataset curation by Claude Code (`docs/plans/dataset-curation.md`) with every
recommendation of its section 14, and started the pilot. Curators need one definition of a
dossier, a way to read a source exactly as it will be verified, an independent quote verifier
and an offline checker that CI runs on every dossier, before any craft is curated. No paid model
or keyed API may be called; Claude Code is the only model.

## Decision

1. **One model, shared.** The dossier is a Pydantic model in a new package `backend/app/curation/`
   (`dossier.py` with `parts.py`, `entities.py`, `records.py`, `overview.py`), so the tools and the
   later importer (`app.scripts.import_curation`) read the same definition. The package may import
   `research`, `models` and `data` (`tools/hygiene/layers.py`). Stored vocabularies come from
   `models/enums.py` through `research/vocabulary.py`; curation-only ones (place kinds and roles,
   community kinds, environment factors, source sub-kinds and access) live in
   `curation/vocabulary.py`; limits from the plan in `curation/limits.py`. The JSON Schema
   `shared/curation.dossier.schema.json` is generated from the model and pinned by a test.
2. **The rules are pure functions beside the model** (`claim_rules`, `entity_rules`,
   `source_rules`, `overview_rules`, `coverage`, `references`, `check_file`), returning
   `Problem(where, message)`; `checks.dossier_problems` runs them, so the importer can refuse a
   dossier with the checker's own lines. Unresolved references stop the remaining rules, since
   they cannot be read meaningfully.
3. **Reading reuses the app's extraction.** `tools/curation/reading.source_text` is the one
   extraction and normalisation used by `fetch.py` and `verify.py`: HTML through
   `app.fetcher.extract` (the trafilatura settings and hidden-element removal the live fetcher
   uses), PDF through `app.fetcher.pdf.pdf_text` with curation's larger page cap (GI journal
   issues run to hundreds of pages), then `research/quotes.normalise_quote_lines`, a new
   line-keeping form of the existing quote normalisation (`normalise_quote_text` now joins its
   lines; behaviour unchanged, checked against the old function on 200,000 random strings).
4. **Matching folds case** as the plan says (`curation/matching.quote_found`), otherwise it is the
   answer engine's quote rule (`research/quotes.occurs_in_key`, split out of `quote_occurs` so a
   long source text is normalised once): whitespace, hyphenated line breaks, NFKC, typographic
   quotes and dashes, hyphens between letters, word boundaries and no match inside a number.
5. **Plain HTTP with a browser-like user agent**, as the plan asks: redirects followed, one
   request per host at a time with 1.5 s between requests, a 40 MiB cap that refuses rather than
   truncates. robots.txt is not read: these are single, human-paced reads of pages a curator
   chose, not crawling. A refused live page falls back to the dossier's `archivedUrl`, else the
   latest status-200 capture from the Wayback Machine's CDX index (more reliable than the
   availability API), read in its raw `id_` form.
6. **Freshness by content, not file times.** "The check file is newer than the dossier" is read as:
   the check file's digest of every source URL and quote equals the dossier's, its `checkedAt` is
   not before `curatedAt`, and it was made by the current verifier version. Git checkouts reset
   file times, so a time comparison would be meaningless in CI. Prose and structure edits keep
   the check file; any source or quote edit needs a new verify.
7. **One role per place entry**, as the plan's `role`: a place with two roles (Dhamadka, practised
   and a historic centre) is listed once per role, each entry with the claims that state it.
8. **GI authorised users are a count.** `authorisedUserCount`, not names: the registry's list
   names private artisans, and decision D6 admits named people only as master artisans with name,
   honours and place.
9. **Relationship sentences** are found by graph leftovers (a demonstrative without its subject,
   seed filler, relation names in capitals, arrows) and bare triples (one relation phrase, at most
   six words a side, no qualifying word, digit or punctuation). Calibrated on the seed: of 557
   edge sentences, 303 are refused by this rule or the eight-word minimum, and 4 of 1,357 other
   seed sentences, each of them `X uses Y` or a stage without its subject. The remaining edge
   sentences state something a reader learns; the critic judges them.
10. **The index** (`backend/app/data/curation/index.json`) is regenerated by every `check.py` run
    from every dossier in the folder, written atomically so parallel curators never leave it half
    written, with no generation time so it changes only with the dossiers. CI runs
    `check.py --check-index`, which writes nothing and fails on a stale index. The tools' tests run
    in the existing tools step of Backend checks (`tools/pyproject.toml` now puts `backend` on the
    path); the model's and rules' tests run with the backend's DB-free tests.

11. **Districts are named as the LGD register names them**, pending districts included
    (`data/district_register.py`). `district-shapes.json` holds geometry by LGD code only, so a name
    can only be checked against the register; a shape is not required, because 34 register
    districts have none yet (Balotra, a Rajasthan printing centre, among them) and requiring one
    would force an outdated parent district.

## Consequences

- A curator runs `fetch.py`, writes the dossier, then `verify.py` and `check.py` until both pass
  (`docs/RUNBOOK.md`, How to curate a craft); the contract is `docs/contracts/curation.md`.
- CI refuses any dossier, check file or index that breaks the contract, with no network.
- The importer, the critic's brief and the pilot dossiers are next (plan sections 7, 8 and 10).
- `services/district_seed.py` still reads `lgd_register.json` itself for the seed;
  `data/district_register.py` is the name lookup the checker uses (`docs/TECH_DEBT.md`).

## Wave 1 changes

Date: 2026-11-18. After the wave 0 pilot (its critics raised 80 problems, 41 must-fix) and before
wave 1:

1. **Numbers** (`curation/figures.py`): a leading zero no longer separates two numbers
   (`5 May 2008` matches `05-05-2008`; a dotted date part by part; a decimal keeps its zeros), and
   a letter-spaced run in a quote (`2 0 1 8` on a report's title page) counts with its digits
   closed up, while a table row's pipes keep its numbers apart. The answer engine's
   `research/quotes.unsupported_figures` is unchanged.
2. **Hedges in Hindi, and in both directions** (`curation/hedges.py`): Hindi words of doubt and
   approximation (शायद, संभवतः, कहा/माना जाता है कि, लगभग, करीब before a number, ...) are recognised;
   a Hindi word of doubt in a quote sources an English hedge in the claim, and, new for both
   languages, a claim whose every quote hedges must hedge too. In a quote, may, might and could
   do not count (as often a month, a permission or an ability), nor `कहा जाता है` without `कि`
   ("is called"), nor करीब without a number ("near"); a capital `May` inside a sentence is the
   month. Calibrated on the pilots, where it flags nothing once those readings are excluded.
3. **Tables** (`tools/curation/tables.py`): each row of a page's data tables that trafilatura
   dropped is added after the text as one line, ` | ` between cells, so the GI registry's
   applicant, status and dates can be quoted; a page without a data table reads exactly as before
   (tested against the previous pipeline). The verifier became `kalavigyan-curation-verify/2`,
   which made the pilot check files stale; re-verified, all 64 sources were read and all 707
   quotes passed.
4. **The index is written on request**, superseding item 10's "every run": `check.py` writes
   nothing by default, `--write-index` regenerates `index.json` (the lead, once per batch), and
   CI's `--check-index` is unchanged, so parallel curators no longer write one shared file.
5. **Rubric**: a page a named organisation publishes about its own work (Khamir about its
   programmes, a cooperative about its members) is C, author named or not; shop and sales pages
   stay D. The rating stays the curator's; the checker reads it and infers nothing.
6. **A curator checklist** in `docs/contracts/curation.md` turns the must-fix problems into rules
   a first draft meets before the checker and the critic see it.
7. **Crafts the portals added** (`backend/app/data/portal_craft_register.json`): seven crafts the
   portal sync stores under their own slugs with no master serial (Dabu Hand Block Printing,
   Ghurni Clay Doll Craft, Krishnanagar Terracotta, Meghalaya and Mysuru Stone Carving, Bishnupur
   Terracotta Craft, and Cane and Bamboo, which is merged into Cane & Bamboo Craft). The checker
   accepts an active one like a master craft and refuses a merged one with the craft to curate
   instead. The import finds a craft by slug in the database; a register craft the database does
   not hold yet (a fresh CI database, before the portal sync) is reported `WAITING`, not refused,
   and the preview builds it with the id the sync gives it (`seed_uuid("c", slug)`).
8. **One scope field for crafts, families and categories** (`curation/scope_rules.py`,
   `data/curation_scopes.py`): `CRAFT`, `FAMILY` (catch-all rows and crafts practised across All
   India, 81 crafts) and `CATEGORY` (one dossier per master category in `categories/`). The scope
   is declared in the dossier and checked against the master list and the register, so a curator
   cannot pick the looser rules: a family or category may name centres by state or region and has
   no GI record; a category covers every sub-category with a cited sentence or an open question
   saying no source was found, links member crafts by slug, has a section per discipline its
   sources support, holds up to 250 claims and has its own coverage targets. One slug field per
   scope (`craftSlug` or `categorySlug`) runs through the dossier, the check file (a craft check
   file is written exactly as before) and the index, which became schema 2 with the scope of each
   craft and a separate `categories` list. The craft importer reads only the top folder, so
   categories are curated now and imported when the category page is built (`docs/TECH_DEBT.md`).
9. **The pilots under the new rules**: re-verified, then checked with no problem. Kutch Ajrakh's
   three Khamir exhibition pages, rated D by the pilot critic for want of an author, are C under
   the new rubric (Khamir's own annual exhibition, no shop links); the craft page golden follows.

## How this record is kept true

Its Wave 1 changes of 2026-11-18 record what followed the pilot. Beyond that it is not edited except
to mark it superseded: a later choice is a new record that names this one, and the table above links
the two both ways. It records the choice as taken on 2026-11-17; what the code does today is in
[ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
