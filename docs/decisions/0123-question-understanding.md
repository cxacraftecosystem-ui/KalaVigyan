# 0123. A question is understood honestly before any evidence is read

The understanding step no longer narrows an answer the question did not narrow. A question about no
single craft keeps every candidate offered, a glitch in the model's reply drops only the field it
broke, every answer is searched with one English rendering of its question, each field the question
asks about gets an expert of its own, budget left by early sections reaches later ones, and a failed
lookup keeps the crafts it had already found.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21, on the review of the answer pipeline: "is
there any other fault in our existing RAG pipeline?", then "yes, run all five lanes"). The contracts
are `docs/contracts/research.md` (craft resolution, the retrieval plan, understanding the question,
the answering service, translation), `docs/contracts/explainer.md` (the understood event, how the
server fills the sections) and `docs/contracts/answer-eval.md` (the seats).

| For | Read |
|---|---|
| The understanding step and its reply | [research.md](../contracts/research.md), Understanding the question |
| The answer flow and the stored-only answer | [research.md](../contracts/research.md), The answering service |
| The seats and the field each must cover | [answer-eval.md](../contracts/answer-eval.md) |
| The understanding step as first decided | [0031](0031-understanding-and-depth.md) |
| Every decision, by group | [README.md](README.md) |

## Context

A review of the answer pipeline, verified in the code by the lead, found eight faults in how a
question is understood and planned:

1. On an ambiguous craft the model's empty `craft` (the prompt's "none of them, several, or crafts
   in general") was overridden by the top candidate, and because a craft was then chosen the crafts
   the model named were never looked up. "Which crafts of Gujarat use alum?" was answered from one
   craft.
2. One bad value in the reply (an empty field list, a short craft name, an unlisted slug) dropped
   the whole reply. The answer then had no fields, so it was one `OVERVIEW` section with no experts,
   and Expert answers were not widened because widening required a model reply. The depth's minimum
   sections were neither stated to the model nor enforced.
3. A question in another script had no English rendering on the plan request; each section's plan
   call made its own and discarded it, and the seat search, the component catalogue, the simulation
   and what-if builders and the lede all searched the question as written (the lede paid a TRANSLATE
   call of its own).
4. A question in Latin script counted as English, so Romanised Hindi was searched word for word.
5. With spend refused, a question the router could not render had no full-text terms, every stored
   claim ranked zero and the first fourteen by evidence level were streamed as the answer.
6. A seat the model chose filled the seat limit before the question's own field had one.
7. The depth's live budget was split evenly before coverage was known; a section never took more
   than its share, so with four queries over six sections the last two had none while budget an
   earlier section returned sat idle.
8. A failed embedding in the craft resolver lost the crafts the name match had found.

## Decision

1. **No single craft is honoured.** On `AMBIGUOUS` the model's pick stands; its `""` keeps any
   craft with every candidate offered; the top candidate is used only when there is no reply about
   the craft. Crafts the model names that are not among the candidates are then looked up.
2. **A reply is read field by field.** `parsed_reply` leaves out only the values the schema refuses,
   logs which fields lost values, and treats a reply that keeps nothing as no reply.
3. **Fields always exist.** Without the model's fields, the fields are those the question's words
   name (`QUESTION_CUES` over every field, the craft's own name left out, read from the English
   rendering when there is one). The understanding then tops them up to the depth's `min_sections`
   with the fields the craft holds cited claims in, never with a field that has nothing behind it,
   and `OVERVIEW` only when there is no field at all. A `RESOLVER` understanding may now carry
   fields and seats, and Expert answers are widened on either basis. The prompt gives the
   `Sections` range.
4. **One English rendering per answer.** The understanding reply carries `englishQuestion`, stored on
   `Understanding.englishQuestion`. Without it, a question in another script is rendered once by
   TRANSLATE, and a question in Latin script stands for English only when the answer is in English.
   The base plan request and the lede read that rendering.
5. **The stored-only answer never streams an unranked list.** When the question cannot be rendered or
   holds no full-text term, the answer is `not_enough_evidence`.
6. **Each field of the question is seated first**, by a seat the model chose that speaks for it, else
   by its lead, in the question's order; the model's other seats follow within the limit.
7. **A section takes a fair part of what is left.** `ResearchLedger.take_section` grants the
   section's share plus a fair split, among the sections not yet started, of what is left above
   their shares. When the sections start in order this is at least the larger of the share and a
   fair split of what is left, as the review asked; when they do not, a section that starts early
   still never takes the share of one still waiting.
8. **A failed embedding keeps the name match.** A semantic step that fails other than by a spend
   refusal is logged and the lexical resolution stands.

## Consequences

- `Understanding` gains `englishQuestion` (left out when absent) and loses the rule that a resolver
  understanding names no field; stored rows of either shape still validate, so the schema version
  stays 1.
- The understanding schema requires `englishQuestion`, and its message gains the `Sections` line.
- A question in another script whose understanding gives no rendering costs one TRANSLATE call before
  research, which the lede no longer repeats.
- Ranking the stored-only answer by meaning when the question has no terms needs an embedder and the
  retriever in the answer store's wiring (`services/answer_store.py`); until then such an answer is
  `not_enough_evidence`.
- Seat research and the fresh retry still take budget with `ResearchLedger.take` and
  `take_fresh`, which grant at most what they ask for.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/planner/test_understanding.py`, `backend/tests/planner/test_understanding_fields.py`,
`backend/tests/planner/test_field_seats.py`, `backend/tests/research/test_coverage_seats.py`,
`backend/tests/research/test_answer_fields.py`, `backend/tests/research/test_understanding_contract.py`,
`backend/tests/answering/test_english_rendering.py`, `backend/tests/answering/test_answer_flow.py`,
`backend/tests/answering/test_section_blocks.py` and `backend/tests/test_craft_resolver.py`.
