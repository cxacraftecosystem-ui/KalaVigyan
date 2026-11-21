# 0071. The craft page reads as a curated reference

The craft page reads as a curated reference from one route, in five tabs drawn only from what the
response holds, with no generator or research control for readers. All evidence is for Researchers
and above.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0100 The Kutch Ajrakh craft page is the hand-built monograph, served as built](0100-ajrakh-monograph-served-as-built.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| What amended it | [0081 Craft page contract version 2: a page whose structure is final at first paint](0081-craft-page-contract-v2.md): its sources-differ rows come heaviest first, not in the order served |
| What amended it | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): item 8, All evidence for researchers |
| The contracts it names | [craft-page.md](../contracts/craft-page.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner found the production craft page of Kutch Ajrakh poorly represented: hundreds of flat
sentences, filler, and places at state level only (`docs/plans/dataset-curation.md` section 1).
Decision 0053 imports curated dossiers and serves the whole page from stored rows as
`GET /api/crafts/{slug}/page` (`docs/contracts/craft-page.md`, fixture
`shared/craft.page.golden.json`). Plan section 9 says how readers see it: the overview with key
facts, pictures and tappable terms, sections by discipline, "Sources differ" rows, the process
with materials, timing and chemistry, the region at district level with its datasets, sources with
reliability, and All evidence for researchers. Until now the page read `/profile`, `/process` and
`/region` and drew claims as one list per facet, with Image and Video generators on every stage.

## Decision

1. **One route for the page, the region route beside it.** `lib/craftPageContract.ts` parses the
   response with the contract's shapes (unknown fields and values refused) and cross-checks it as
   the backend model does: every named claim listed once, every cited source listed, hypotheses
   never in a sentence and filed apart in All evidence, every claim filed once, an equation only
   on a balanced reaction. `GET /crafts/{slug}/region` still feeds the map's highlight and the
   district datasets (`lib/craftRegion.ts`). The page no longer calls `/profile` or `/process`.
2. **Five tabs, each drawn only from what the response holds.** Overview, Process (only when the
   response has stages or reactions), Region, Sources (only when a source is listed) and All
   evidence. Pure rules are `lib/craftPageView.ts` and `lib/craftPlaces.ts`; one claim index
   reaches every chip through `components/craft/CraftClaims.tsx`, and one source numbering per
   page, in reading order (lede, key facts, pictures, sections, the rows beside them, the process,
   places), then any listed source not yet cited, then the region route's sources.
3. **Overview.** The lede and key facts first, then pictures with author, licence and a link to
   their page (the explainer's `PictureView`), then the discipline sections (curated prose, or a
   list of stored claims for `STORED_CLAIMS`), then "Where sources differ": each row shows every
   side with its own citations, in the order served, never ranked. Open questions (their
   hypotheses and what would settle them), the glossary (a meaning only with its citations) and,
   for a `THIN` dossier, what was searched sit beside them. Sentences are the explainer's
   `ExplainerSentence`, so terms open the existing term sheet (`GET /terms/{key}`). A page with no
   lede or key facts shows the register's facts instead (category, kind, GI status, states); a
   craft with nothing stored shows only those, with no copy about what is missing.
4. **Process.** Stages numbered by the response's `order` only; stages without one are listed
   apart under their own heading, unnumbered. Each stage keeps its claims, materials and tools
   (local names, role and kind, chips), timing as stated, reactions (`ChemEquation` when
   balanced, the species row when a formula is known, otherwise the label with its chips) and the
   pictures tied to it. `StageCard`, `StageMaterials`, `ReactionCard` and `ProcessTimeline` were
   rewritten in place for the page's shapes; `ConditionList` is gone.
5. **No generator or research control for readers.** The Image and Video buttons and the generated
   media slot are no longer mounted on the craft page; the header keeps Ask and, while voice is
   offered, Talk. The term sheet's Ask is not offered here.
6. **Region.** The map fills the districts where the craft is made (places whose role is practised,
   origin, historic centre, migrated from or to, as decision 0053 maps them to `CraftLocation`) and
   the region route's highlight, and tags every named Indian district; places are listed once
   each with all their roles, at village, town or district level ("Village · Kachchh district,
   Gujarat"); people and groups with their place and honours; then the region route's district
   environment and datasets, as before.
7. **Sources** are grouped by reliability A to D (then unrated), each with its page number, kind,
   byline, host and licence.
8. **All evidence for researchers and above.** `permissions.canReadAllEvidence` is rank
   `RESEARCHER` or higher, the rank of the backend's researcher capabilities
   (`core/roles.py`). Every claim appears once, by discipline and subject, near-duplicates folded
   under the strongest in a disclosure, hypotheses in their own group, and each claim tagged
   Curated, Seed, From answers or Researcher, with its level when it is not provisional and a
   "Sources differ" mark.
9. **Shared vocabulary.** The page's tuples are pinned value for value to the backend in
   `e2e/backend-vocabulary-unit.spec.ts` (`research/craft_page.py`, `research/reactions.py`,
   `models/enums.py`, `curation/vocabulary.py`); `PLACE_ROLES` is imported from
   `lib/districtCraftsContract.ts` rather than defined twice. Frontend checks also run when those
   backend files change.
10. **Layout and motion.** Every grid holding text, equations or the map has a `minmax(0,1fr)`
    track or `min-w-0`, checked by `e2e/craft-page-drawing-unit.spec.ts`. Sections and stages rise
    in with the shared `guideMotion` factories, which collapse under either reduced-motion switch.
11. **Production E2E.** Craft Overview waits for the page route's own response, notes whether the
    craft is curated (version and coverage), and for a curated craft requires every lede sentence
    and every key fact on screen; Process requires a stage and Region the map, at all three widths.

## Consequences

- The before and after screenshots of Kutch Ajrakh come from the E2E production run once the
  backend with decision 0053 and this page deploy together.
- The term sheet still shows the term route's summary, not the dossier's meaning
  (`docs/TECH_DEBT.md`, "A curated glossary meaning does not reach the term route").
- Left open in `docs/TECH_DEBT.md`, section "Craft page rebuild (decision 0071)".

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
