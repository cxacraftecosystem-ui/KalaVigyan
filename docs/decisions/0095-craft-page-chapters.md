# 0095. The craft page becomes a monograph in chapters, public to read, built without a question

The craft page becomes a public monograph in ten chapters (schema version 3), built by fixed rules
without a question through the renderer answers use, with the generated explainer as its one model
use. Citations travel with each sentence, the page is cached per stamp, and a craft without a
dossier gets the chapters its rows support.

Date: 2026-11-18. Status: accepted. Specifies craft page schema version 3
(`docs/contracts/craft-page.md`); amends decisions 0071 (All evidence for researchers), 0079 (the
page's one role-dependent part), 0081 (the flat page) and, for display only, 0088 item 6.

| For | Read |
|---|---|
| What superseded part of it | [0100 The Kutch Ajrakh craft page is the hand-built monograph, served as built](0100-ajrakh-monograph-served-as-built.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| What amended it | [0097 Everything reads without signing in except asking](0097-public-reading-everywhere-but-asking.md): item 7, what on the page is public |
| What it amends | [0071 The craft page reads as a curated reference](0071-craft-page-rebuild.md): item 8, All evidence for researchers |
| What it amends | [0079 Craft, category, map and science pages read without signing in](0079-public-reading.md): the page's one role-dependent part |
| What it amends | [0081 Craft page contract version 2: a page whose structure is final at first paint](0081-craft-page-contract-v2.md): the flat page, now in chapters |
| What it amends | [0088 Reactions play step by step with their stage, conditions, colours and why; curated CIDs become compounds](0088-reactions-step-by-step-and-molecules.md): item 6, for display only |
| What built on it | [0096 Every piece built for a reader's question joins its craft's page, whoever asked](0096-reader-question-pieces-join-their-craft-page.md): craft page schema version 3 |
| What built on it | [0098 How the craft page chapters were built: the readings taken where the contract was open](0098-craft-page-chapters-build.md): the page builders, the snapshot store and the routes |
| The contract it specifies | [craft-page.md](../contracts/craft-page.md), schema version 3 |
| Every decision, by group | [README.md](README.md) |

## Context

The owner wrote on 2026-11-18: "add all the information that you have generated, including the
image and the other assets to the ajrakh page as well, all the information should be directly
accessible from there too, only the query part is to be guarded, the rest of the application is
going to be public only".

The answer engine builds rich pieces for an answer (decisions 0085 to 0090): the reaction player
with stages, conditions and colours, molecules, material cards, the process ladder, the timeline
with trade routes, the region story with its India locator and map layers, seasons, the supply
map, the zoom story, the what-if lab, the concept graph, market and GI, generated mechanism
explainers, sourced concept pictures, field voices and photographs and approved artisan
testimony. The craft page (schema version 2) shows only the dossier's facts as flat lists, so a
reader of Kutch Ajrakh sees none of these unless they ask, and asking needs an account. The
approved boards (the master board's Kutch Ajrakh monograph and the answer boards for chemistry,
place and time, reading and media, ask and research) draw these pieces on a monograph in
chapters, with pictures the curated dossier does not hold yet. Most answer builders let a model
choose among stored claims (which basin, which steps, which imitation claims); a page has no
question to choose for.

## Decision

1. **Schema version 3 adds fields only.** `masthead`, `lede`, `chapters` and `cite` are added, and
   `sources` entries gain their group, origin and the count of sentences they support. Every
   version 2 field keeps its meaning so today's screen still draws. The flat parts the chapters
   now carry (`tabs`, `overview`, `giCard`, `events`, `environment`, `sourcesDiffer`, `places`,
   `communities`, `process`, `pictures`, `openQuestions`, `sameFamily`, `voices`, `fieldPhotos`)
   are deprecated: schema version 4 removes them in the change that moves the screen to chapters,
   and no later than 2026-12-18. A screen that reads both is never built.
2. **Ten chapters in a fixed order**, each present only when it holds at least one piece: At a
   glance, How it is made, The chemistry, Why <place>, History and trade, Market and GI, What if,
   People and voices, Kin crafts and shared science, Sources. Curated overview sections join the
   chapter of their discipline. The masthead (the specimen label over the hero plate) and the
   lede open the page above the chapters.
3. **One renderer for answers and the page.** A chapter item is either an answer block, in the
   explainer's `Block` shapes unchanged, or a page part. Reused: `prose`, `process_ladder`,
   `reaction_player`, `molecule_3d`, `material_card`, the four signature figures, `zoom_story`,
   `simulation`, `images`, `region_story`, `climate_risk`, `seasons`, `supply_map`, `measure`,
   `timeline_map`, `market_gi`, `what_if`, `artisan_voice` and `concept_graph`. Not on the page:
   `expert_view` (model-composed takes), `quiz`, `compare`, `map_layer` (the region story carries
   the layers) and the declared kinds. Three block models gain optional fields, left out of the
   JSON when empty so every stored piece keeps its content hash, as decisions 0087 and 0088 did:
   the ladder's stage gains its local name, an unnumbered mark, the cloth after the stage with its
   stated colours, a one-line why, tools, its sources-differ rows and its pictures, and a material
   its botanical name, CID and local names; a reaction step gains `formulaBasis`; the climate block
   gains the yearly `series`. Answers may fill them too.
4. **Built without a question, by fixed rules.** Every model choice an answer builder makes is
   replaced on the page by a rule over stored rows (the contract's table): steps, rows, links,
   points and outcomes in dossier or stage order, a river only when a claim names it, imitation and
   meaning claims by fixed words, what-if outcomes in the offer order. The page builders are pure
   functions of the rows; they make no model, search or HTTP call, so a page can always be built
   on a cache miss.
5. **The one model use is the generated explainer**, built by a job, never on a reader's request:
   per craft and per curation version (per stored claim set for a craft without a dossier), one
   per mechanism concept of decision 0087 found over the whole craft, on the Expert explainer
   route, stored as a knowledge piece in the concept's slot so answers reuse it. A concept with no
   explainer gets its sourced concept pictures instead. A Professor or above can hide a page
   explainer (`HIDE_GENERATED`); a hidden one is never placed. Spend is recorded under a system
   principal with no cap (decision 0093). The job also does the lookups the builders may not
   (kept conformers, place points, concept pictures), so the route never does.
6. **Citations travel with the sentence.** Chapter sentences are `ExplainerSentence`s with their
   citations inline, as in answers; `claims` stays the index All evidence files. Sources are
   numbered once in chapter reading order and grouped for the Sources chapter (government records,
   scholarship, museums, web and press, field interviews, the family monograph, related monographs,
   the compound library, compound records), with datasets and picture credits beside them. The
   explainer's claim ledger (decision 0080) runs over the chapters in reading order, so a claim is
   rendered once per page and a sources-differ reading already shown is referenced, not repeated.
7. **Everything on the page is public.** All evidence is shown to every reader, so the
   `READ_ALL_EVIDENCE` capability and `without_evidence` are retired. The body differs by reader
   only in one licence term: a reader holding `READ_RESEARCHER_QUOTES` gets the `RESEARCHER`
   variant with closed-licence quotes (decision 0013); everyone else, signed in or not, gets the
   `OPEN` variant, byte for byte. Asking stays signed in: Ask, the page's questions, Talk and a term
   lookup that would research. The full transcript of a field recording (decision 0084) is public
   since decision 0097. Still signed in because they are personal data under their own consent
   terms, not reading: artisan conversation recordings (decision 0083, "Owner to confirm" item 4),
   testimony waiting for review (decision 0083 item 16), a reader's own records, and answers,
   which stay their asker's unless the asker shares a version by link (decision 0097); what an
   answer wrote back reaches the page through the stored claims and pieces.
8. **Cached per stamp, revalidated per body.** A stamp, read in one statement, covers the release,
   the curation versions of the craft and its family, and the count and latest change of every row
   class the page reads (including which field-voice streams are fresh). A snapshot per craft and
   variant is rebuilt when the stamp moves; the ETag stays the SHA-256 of the body as served
   (decision 0081 item 7). A nightly rebuild compares each snapshot with a fresh build under the
   same stamp and logs a difference as an error. The last page of each superseded curation version
   is archived and answered by `?version=N`, so Cite this monograph names an address that keeps
   its text.
9. **The dossier states what rules cannot.** Curation schema version 2 adds optional fields: a
   stage's cloth-after text and colours with the claim that states them, its why claim, a
   picture's placement, focal box, size and stand-in note, and the craft's own names with the
   claim that states each; pictures per dossier rise from 6 to 16. Every schema 1 dossier migrates
   by its version alone. The Kutch Ajrakh dossier version 2 adds the pictures the approved boards
   used, credited from their Commons pages, stand-ins saying what they show, with the stage
   fields. The category import stores a family dossier's reactions, so the Textiles family's
   indigo chain reaches the crafts whose materials it names, labelled as the family's.
10. **Balanced from compound records, marked Inferred.** A stored word reaction whose every
    species resolves to a compound record with a formula is drawn balanced by the science engine,
    with `formulaBasis` `COMPOUND_RECORD`, marked Inferred and citing those records. The stored
    reaction rows are unchanged, so decision 0088 item 6 holds for what is stored.
11. **A craft without a dossier gets the chapters its rows support** and never an empty heading:
    the typographic plate and the register's facts, its stored process and reactions, its region,
    its kin and its sources where they exist, and, with no stored claim at all, the three
    questions that start research.

## Consequences

- Two independent build tasks: CHAPTERS (the builders, the payload, the snapshot store and job,
  curation schema 2 with the Kutch Ajrakh dossier, the goldens and the client contract) and
  PUBLIC (every reading screen and route open, asking guarded, the route inventory test). The
  monograph screen that draws the chapters is the page lane of decision 0094; until it lands
  today's screen keeps drawing the flat parts.
- The payload roughly doubles while the flat parts remain; the contract test holds the served
  Kutch Ajrakh page to 250 KB gzipped.
- One migration adds `CraftPageSnapshot`, `CraftPageArchive` and `Compound.conformerKeptAt`.
- The first job run drafts about four explainers for each of the 29 curated crafts on Opus at its
  documented maximum output; at the settled cost of recent drafts (about 10,000 to 20,000 output
  tokens each) a full run costs in the order of tens of dollars, and later runs draft only for
  changed curation versions.
- Model-built explainers are now public. They keep the static check and sealed frame of decision
  0055, and a Professor can hide one.
- Anonymous reads of a whole monograph (the page, conformers, field images, layers) count against
  the per-address limit of decision 0079; PUBLIC measures one page view and sets the limit and the
  counting so that a campus behind one address can read.
- The owner decided both open exceptions of item 7 on 2026-11-18 (decision 0097): full field
  transcripts are public, and an asker may share a version of an answer by link, with the privacy
  notice and the portals' contract (decision 0084) changed with them.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
