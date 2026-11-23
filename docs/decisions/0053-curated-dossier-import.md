# 0053. Curated dossiers are imported on deploy and served as one craft page

Curated dossiers are imported into the app's own tables after the seeds on every deploy, with
deterministic ids, writes only on change, supersession instead of deletion, and the seed's edge
sentences withdrawn. One route serves the whole curated craft page, with a preview that needs no
database.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What built on it | [0108 An approved structure proposal becomes a curated fact of its dossier](0108-structure-proposals-become-curated-facts.md): the database as the source of truth and the dossiers as its export |
| The contracts it names | [craft-page.md](../contracts/craft-page.md) |
| The seed rows of a curated craft retired, a removed dossier retired by name, the curated glossary meaning stored as the term's summary | [decision 0142](0142-curated-crafts-read-only-curated-rows.md) |
| An import that never undoes approved structure, and a sources-differ flag kept while a live pair holds it (amends item 4) | [decision 0171](0171-imports-keep-approvals-and-differences-settle.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Curators now write checked dossiers (decision 0051; three pass: Kutch Ajrakh, Bastar Dhokra,
Tikuli Painting). The plan (`docs/plans/dataset-curation.md` sections 8, 9 and 11) asks for a
deploy-time import into the app's own tables, the seed's 557 edge sentences withdrawn from every
reader, and a craft page built from the imported rows. Nothing about it may call a model or a keyed
API; vectors stay with the nightly `embed_knowledge`.

## Decision

1. **One import, after the seeds.** `app.scripts.import_curation` runs as the fourth module of the
   seed step in `infra/deploy/blue_green.sh` (after `seed_districts`, because places reference
   districts) and in Backend checks after the database tests. It withdraws the seed edge
   sentences, then imports each dossier whose checks pass (`curation.files.checked_dossier`, the
   checker's own rules and the check file), each inside its own savepoint, so a dossier is imported
   whole or not at all. A refused dossier is reported with its problem lines and the script exits
   2, which stops a release like a failed seed; CI's `check.py --check-index` refuses such a
   dossier before any deploy.
2. **Deterministic ids, writes only when something changed.** Every row id is
   `uuid5(ID_NAMESPACE, "curation:<slug>:...")` (claims and sources exactly
   `curation:<slug>:<id>`, as the plan says). The writer reads the stored row, compares it with
   the planned one and writes only differences, so a second import writes nothing and reports an
   empty `changed` for every dossier. A DOI already held by another `Source` row (the table's
   unique DOI index) is cited through that row.
3. **Mapping.** Sources → `Source` (`IMPORT`, `EXCERPT`, reliability kept, `externalIds.systemActor`
   `curation`, the verifier's text hash in `sha256`). Claims → `Claim` (`PROVISIONAL`, or
   `HYPOTHESIS` for hypotheses; `APPROVED`; `sourcesDiffer` from conflicts; one `ReviewEvent` per
   change with `systemActor` `curation`) and `CuratedClaim` (the dossier key and the claim's
   discipline, the marker that tells curated claims from seed and answer claims); quotes →
   `ClaimSource` (`PASS`, the check file's `checkedAt`). Every dossier subject becomes a `Concept`
   owned by the craft so retrieval scopes it as before: stages `PROCESS_STAGE`, materials
   `MATERIAL`, tools `TOOL`, places `ENVIRONMENTAL_CONDITION` (one concept per place however many
   roles it has), communities `TRADITION`, glossary terms `CONCEPT`, and claims about the craft
   itself one concept per discipline typed so the planner's facet search finds them
   (`curation_keys.DISCIPLINE_CONCEPT_TYPES`). Places where the craft is made (`PRACTISED`,
   `ORIGIN`, `HISTORIC_CENTRE`, `MIGRATED_FROM`, `MIGRATED_TO`) in India become `CraftLocation`
   rows at `DISTRICT` precision with the district's and state's LGD codes (a village in its
   district), or `STATE` for a state, with the new `role` column; material sources, markets and
   places abroad stay page facts only, so the region route, the map and the region story keep
   meaning "where the craft is made". Process → one `Process` (variant `curation`), `ProcessStage`
   with the new `ordered` flag (unordered stages take ordinals after the ordered ones),
   `Material` rows for materials and tools, `StageMaterial` (tools with role `TOOL`), and
   `Reaction` with `ReactionCitation` balanced by the science engine (`science.reactions.
   check_reaction`); a reaction without formulas is kept as text. Pictures → `MediaRef`
   (provider `curation`, inline under their open licence) and `MediaRefClaim`. Glossary → `Term`
   (inserted only when the key is new, so the seed glossary keeps its rows; a comma list of
   spellings is label then aliases), `TermCraft`, `TermConcept`. GI and market → `CraftGiRecord`,
   `CraftPrice`, `CraftWorkforce`. The overview → one `prose` `KnowledgePiece` for the lede
   (facet `OVERVIEW`) and one per section, Expert depth, no answer id, topic as answers compute it
   (`piece_topics.facet_topic` over the craft's districts), sentences checked by the answer
   engine's prose validator (`section_blocks.prose_problems`; a failing sentence is dropped and
   reported) and marked with the dossier's glossary. Everything else the page needs and no table
   holds (key facts, conflicts, open questions, the place and stage details, picture captions,
   the overview's piece ids) is the `CuratedCraft.page` index, a typed model
   (`services/curated_index.CuratedPage`) of references, never claim text.
4. **Supersession, never deletion.** A curated claim missing from a new version becomes
   `SUPERSEDED` (a new `ClaimStatus`, hidden like `RETRACTED`) and keeps its citations, so old
   answers still resolve. A claim a person raised above provisional or retracted is never lowered
   or reopened; a superseded claim that returns is shown again. Replaced overview pieces are
   superseded by the new piece, dropped ones marked stale. Structure rows of the curated process,
   curated locations, dropped quotes of kept claims and stale market rows are replaced.
5. **Seed edges withdrawn at the source.** The seed's `EDGE` claims (557) become `WITHDRAWN`, a
   second new hidden status, with a review event each; their `ConceptEdge` rows and the stage,
   material and reaction rows built from them stay. Every reader already drops
   `HIDDEN_CLAIM_STATUSES` (retrieval scope, `claims_by_id`, the media claim set, the term route,
   embedding), and the stale-piece trigger now lists both new statuses, so pieces resting on an
   edge sentence are no longer reused. Filtering by status rather than in each view keeps any
   future reader correct by default.
6. **One craft page route.** `GET /api/crafts/{slug}/page` answers `CraftPage`
   (`research/craft_page.py`, contract `docs/contracts/craft-page.md`): rows are read by
   `services/craft_page_records`, the page is built by the pure `services/craft_page`, and no model
   or HTTP call is made. A curated craft shows its curated overview, key facts, places, process,
   glossary, pictures, "Sources differ" rows and open questions; any craft shows All evidence:
   every visible claim once, grouped by discipline and subject, near-duplicates folded under the
   strongest (curated, then researcher, then from answers, then seed) by the checker's own
   duplicate rule, hypotheses apart, with each claim's provenance. A craft with no dossier gets
   overview sections built from its own claims. `/profile` and `/process` stay until the page is
   rebuilt on this route.
   All evidence is gated on the server: a reader without the capability `READ_ALL_EVIDENCE`
   (Researcher and above) gets `evidence` null and only the claims and sources the page's parts
   cite (`research/craft_page.without_evidence`), so a Student's browser never receives the claims
   the page hides.
7. **A preview without a database.** `services/curation_preview` builds the same records from a
   dossier alone; `python -m app.scripts.import_curation --preview <slug> --out <file>` writes the
   page, which is how `shared/craft.page.golden.json` is generated, and a DB test checks the
   served page's curated parts equal it.
8. **Layers.** `services` may import `curation` (`tools/hygiene/layers.py`), so the importer reads
   the same dossier model and rules as the checker (decision 0051).

## Consequences

- Migration `0017_curated_dossiers`: `ClaimStatus` gains `SUPERSEDED` and `WITHDRAWN` (the
  downgrade maps both to `RETRACTED`), the stale-piece trigger is recreated with them, and the
  tables `CuratedCraft`, `CuratedClaim`, `CraftGiRecord`, `CraftPrice`, `CraftWorkforce` and the
  columns `CraftLocation.role` and `ProcessStage.ordered` are added, with row-level security.
- Kutch Ajrakh gains district places in Kachchh (449) and Barmer, so the region story's
  `place_offers.mapped_districts` finds it.
- Imported claims and pieces have no vectors until the nightly `embed_knowledge`; until then
  answers find them by keywords.
- Left open: `docs/TECH_DEBT.md`, section "Curated import and craft page (decision 0053)".

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
