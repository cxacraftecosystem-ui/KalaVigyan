# 0055. Generated explainers: built from cited figures, checked, stored, reused and hidden

A generated explainer is built by a registry builder from figures the server offers, in one model
call and one redraft and then nothing, and is stored once keyed by its claim set and concept. It is
reused before any call, and a professor can hide it.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Plan section 2.6 and decision 0054 fixed the generated explainer (`simulation`): its fields, the
static check `research/sandbox.sandbox_problems` with its escape-attempt corpus, the frame, the
piece slot `concept:<slug>` and the hide route. Nothing built one, stored one or let a professor
hide one. This lane builds the server side; the renderer is lane 0059, and the kind joins
`BUILT_BLOCK_KINDS` on both sides only when both exist.

## Decision

1. **A builder in the registry.** `services/simulation_builder.SimulationBuilder` is the
   `simulation` entry of `BLOCK_BUILDERS` for the mechanism fields (process, chemistry, physics,
   materials, geography and water, geology and soil, climate), waiting the registry's ceiling of
   60 s because it writes code. It spends through the builders' compose model, so only from the
   answer's headroom (decisions 0046, 0050), Master Admins uncapped, and the `COMPOSE` routes
   apply (Opus at medium effort first, decision 0052).
2. **The server offers the values; the model only chooses.** Each plain number a quote of the
   section's fact-level claims states is offered once per claim with its own citation and its
   stated words, three words either side stopping at a clause mark, so `stated` always occurs in
   the quote (`research/simulation_draft.offered_values`). The model picks the offered refs, names
   their keys, labels and the concept and title, and may decline (`build: false`). A unit is kept
   only as words the stated words hold. Dataset-row values, which the contract allows, are not
   offered yet (debt entry).
3. **One call, one redraft, then nothing.** The checks run in order: values (`VALUE`), the
   static check over the data object (`SIZE` to `NUMBER`), the block's validators (`BLOCK`). On any
   problem one redraft is asked with every failed check listed; a second failure adds nothing and
   logs the rules that failed. The static check is the contract's parser-based one, used as is.
4. **The reply names its model.** `StructuredReply` gains `model`, the route's model id from
   `RouterResult.model`, so a generated explainer is labelled with the model that wrote it; a
   route that names none fails the build rather than guess.
5. **Reuse before any call, by claim set and concept.** Before asking a model the builder reads,
   in one short session closed before the call (decision 0040), the stored simulation pieces of
   the section's facet whose claims are all among the section's checked claims
   (`claimIds <@`). One that passes the reuse rule for its own concept and the asked depth, with
   its claims still visible as cited, is placed with its reuse mark: the most claims, then the
   newest. "The claim set offered for that concept" is read as every claim the stored values rest
   on being offered again as cited; requiring the offered set to equal it would rebuild an
   explainer whenever a section gained an unrelated cited claim. A reused section gets its
   stored explainer the same way, beside its region story (`piece_reuse.with_simulation`).
6. **A builder may place a stored piece.** `BuilderEntry` gains `places_pieces`; only such an
   entry may return a block with a reuse mark, and `piece_store.storable` refuses a placed block,
   so a reused explainer is never stored a second time under the new answer (which would also
   have left a hide aimed at the original piece ineffective).
7. **Supersession follows the key.** A newer simulation piece supersedes an older one only for
   the same concept and the same claim set (`CLAIM_KEYED_KINDS`), so two crafts' explainers of
   one concept from different claims do not keep superseding each other.
8. **Hiding.** `HIDE_GENERATED` (Professor and above), `PUT /api/answers/{answerId}/simulations/
   {blockId}/hidden` (`api/routes/simulations`, `services/simulation_hiding`) and migration
   `0019_hidden_generated_explainers` (`hiddenAt`, `hiddenById`). The route finds the block in the
   asker's kept explainer, marks the piece it was stored as or reused from, and audits a change
   (`explainers.simulation_hidden`, `explainers.simulation_shown`). `KnowledgePiece` gains
   `hiddenAt`; `reuse_refusal` refuses `HIDDEN` after `SUPERSEDED`. A draft whose concept and
   claim set are a hidden piece's adds nothing, and the hidden concepts on offer are named to the
   model (inside untrusted blocks) so it chooses another. `with_hidden_marks` marks a read-back
   explainer's hidden simulations `hidden: true` for the phase D read-back routes.
9. **`stored_explainer` moved** from `voice/listen_store` to `services/answer_store`, beside
   `EXPLAINER_PAYLOAD_KEY`, so the hide service reads a kept explainer without a sideways import.

## Consequences

- Nothing a reader sees changes until `simulation` joins the built kinds with its renderer;
  until then `from_registry` starts no simulation builder and no piece of the kind can be stored.
- The tests drive the builder with replies written to the published structured-output shape:
  every corpus escape attempt is refused for its stated rule through the builder, every accepted
  one is kept, a numeral absent from the data object and a fragment one byte over the cap are
  refused, a stored explainer offered again is placed with no model call (also across two whole
  answers), and the route refuses Students and Researchers. Database tests (marked `db`) cover
  the stored pieces query, the reuse of a kept explainer with its section, hiding, showing again
  and the 404 cases.
- Debt is in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
