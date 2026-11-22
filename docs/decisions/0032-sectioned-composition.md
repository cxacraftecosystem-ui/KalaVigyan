# 0032. Sectioned composition: research per field, blocks per section

Each section of an explainer is a field, researched within the depth's budget and composed by one
composer, with live research when stored claims compose nothing. A model chooses and the server
fills, every block is checked again, and a failure stays in its section.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| The budget by asked field, and a late failure rewritten once | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` (owner-approved, section 8 final) turns an answer into an
explainer: per open facet, plan and research within the depth budget (2.3 steps 3 and 4), compose
each section in parallel with Claude Sonnet first and Gemini next (step 5), check every block and
regenerate once, then drop it with a note of what was searched (step 6), and translate checked
blocks (step 8), streaming `section_started`, `block`, `section_done` and the trail as each part
finishes. Decision 0030 fixed the events and blocks; 0031 the understanding and depth. Finding
8a.1 of the production run: Claude Sonnet answered 400 to the compose schema, the adapter dropped
the format and the free-text reply lost every sentence. Finding 8a.2: an answer whose stored
claims composed nothing ended "not enough evidence" without researching live. Until this lane the
answering service composed one answer and streamed `section` and `sentence` events.

## Decision

1. **A section is a field.** The sections are the understanding's disciplines in its order of
   importance, at most the depth's `max_sections`, `OVERVIEW` when it names none
   (`research/sections.section_specs`); titles are app labels per discipline
   (`DISCIPLINE_TITLES`), since `section_started` goes out before anything is composed and a title
   cannot change afterwards. Fewer fields than the depth's minimum are not padded with unrelated
   sections.
2. **Research per section, within the depth.** Each section runs today's planner with a `focus`
   (its field, a `Section` line in the plan call), the understanding's `seats` (an `Experts`
   line: "extended with the expert seats") and a `share` of the depth's query, native-query and
   document budget, split evenly with the remainder to the most important fields
   (`split_share`); `request_limits` takes the smaller of the share and the mode and depth limits,
   so the depth's budget is never exceeded. A ledger (`services/research_ledger`) takes each
   share and gets back what a section did not use. Sections run in parallel, at most
   `SECTION_CONCURRENCY` (4) at once to keep the search, fetch and database load bounded.
3. **Live research when stored claims compose nothing (8a.2).** A section that shows no block
   after a plan that ran no live query, in a mode that allows live queries, researches once more
   with `fresh` (live queries even for covered facets) and what the ledger has left, at least one
   query and `FRESH_MIN_FETCHES` (2) documents; with nothing left it ends `EMPTY`.
4. **One composer, two reply forms.** `ComposeRequest.focus` switches `ModelComposer` to the
   section form (`SECTION_SYSTEM_PROMPT`, `section_schema`): sentences, follow-ups and, for a
   `PROCESS` section of a known craft, the ids of the stored stages to show. The checks, the one
   regenerate of failing sentences and the not-enough path are the existing ones, so "regenerate
   once" is the composer's regenerate, which runs the same rules the block checks apply. A second
   composer was rejected: it would copy the retry and regenerate loop.
5. **A model chooses, the server fills, and every block is checked again.** The ladder's stages
   are an enum of the stored stage ids; the server builds each stage from the science tables
   (stage claims as stored, materials and readings with their own citations, the reactions) and
   `ladder_problems` refuses a ladder holding any stage, sentence, material, condition or reaction
   that is not a stored row of that stage. A prose block takes each passing sentence with the
   visible citations of its stored claims and is refused whole when one sentence cites nothing,
   is not a fact, or states a figure no cited claim or quote holds (plan 2.1: "a block with an
   uncited fact is dropped"). These are data checks after the write-back, which no model call can
   repair, so a refused block is dropped and logged rather than regenerated a second time; a
   section left empty says what it searched (`searched_note`, the same parts as the
   not-enough message).
6. **Schemas every route accepts (8a.1).** Structured-output schemas use only `type`, `enum`,
   `items`, `properties`, `required` and `additionalProperties: false`, with every property
   required (`schema_problems`, tested for every schema the router sends: plan, understand,
   compose, section, regenerate, translate); counts and lengths are prompt lines checked on our
   side. The Anthropic and Gemini adapters never drop a schema: a refused format is a provider
   failure of kind `error`, logged, so the router moves to the next route. A format "learned" as
   refused before is ignored, since the learned flag is what produced free text in production.
   The OpenAI-compatible adapter followed in decision 0038.
7. **The trail streams per source.** The planner reports merged hits (`found`) and each read
   document (`read`) through a `ResearchTrail`; the section adds the stored sources of its stored
   claims as `FOUND`, and after `section_done` marks `QUOTED` the live keys its sentences quoted and
   the stored sources its blocks cite that the trail knows (and a ladder's). A key only moves
   forward, once per answer.
8. **Per-block translation.** Section titles are translated in one call before the sections
   start, each checked block in its own call as it is sent (stage names and a condition's
   `stated` stay as stored, since `stated` must stay the source's words), and the follow-ups at
   the end. Citations are copied; claim sentences use the translation cache.
9. **Stream and storage.** Sources are sent before the first block citing them, once per
   answer, behind one lock, so parallel sections cannot send a source twice or a block before
   its source. The stored-only answer (spend refused) streams the same events, one `prose`
   section per concept heading, so the explainer view draws both. `section` and `sentence` stay in
   the vocabulary but are no longer sent. The `Answer` row is written when the answer starts, each
   section's write-back on its own, and at the end the plans (`AnswerPlans`, one per section and
   attempt, migration `0014_sectioned_answer_plans` wraps the older single plans), the claims
   shown and the explainer document (`Answer.payload.explainer`, which Listen reads).
10. **Failures stay in their section.** A section whose research or composition fails ends
    `EMPTY` with a fixed note and the others still answer; when every section fails the first
    failure is the answer's `error`; a spend refusal anywhere stops every section and is shown in
    its own words.

## Consequences

- An Expert answer makes one plan call and one compose call (two with a regenerate) per section;
  the per-answer caps of 0031 bound everyone but Master Admins.
- The same document can be fetched by two sections; the adapters' caches absorb repeated
  searches, not repeated reads (debt).
- Step 7's pictures and term spans are called after the blocks are built (decision 0039); its 3D
  molecules and simulations come with later phases. Step 9's knowledge pieces are called too (lane
  0033: `pieces.reusable` before planning, `pieces.keep` after the answer).
- Items left below standard are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
