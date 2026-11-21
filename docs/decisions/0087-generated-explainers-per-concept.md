# 0087. A generated explainer, or a picture, for every concept that needs one

A concept that needs one gets a generated explainer, chosen by fixed rules and resting on statements
and stored reactions as well as figures, within stated limits. A concept with no explainer gets a
picture.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

The owner's Expert answer on Kutch Ajrakh showed no interactive explainer, and the production E2E
recorded "the builder chose no concept" for the indigo question. The builder of decision 0055 had
five gates: it asked no model when the section's quotes stated no figure, a block needed at least
one figure value, the model chose the concept itself and could answer `build: false`, the draft
was capped at 12,000 characters inside a 60 s wait, and reused sections never ran it. Mechanisms
such as indigo's reduction and oxidation, the alum and alizarin lake or the iron black rest on
statements and balanced equations, not on quoted numbers, so the first two gates stopped them
before any call.

## Decision

1. **Concepts are chosen by fixed rules** (`science/mechanisms.section_concepts`): the craft's
   stored reactions whose claims are facts, grouped when they share a compound or a species word,
   and each stage's resist materials; a section takes a concept when one of its sentences cites
   the concept's claims or names its species or materials. The model is told the concept and is
   asked to build it.
2. **A generated explainer may rest on statements and stored reactions.** `SimulationBlock` gains
   `grounds` (the cited passages it acts out) and `reactions` (stored reactions as the science
   engine wrote them), both left out of the JSON when empty so every stored explainer keeps its
   content hash; `values` may be empty when either is present. The static check's data includes
   the coefficients of the reactions used, so an equation may be shown with its coefficients and
   with no other figure. On reuse a stored explainer that plays reactions is placed only while each
   still matches its stored row.
3. **Limits:** 1 explainer per answer at Basic, 2 at Detailed, 3 at Expert, one per concept, at
   most one per section, each drafted within the answer's optional headroom; the draft may hold
   40,000 characters (12,000 before), the builder waits 150 s and `BUILDER_WAIT_MAX_SECONDS` is
   180 s (60 s before). The model is the answer's explainer route (decision 0089).
4. **A concept with no explainer gets a picture.** The explainer's builder searches a picture for
   each other concept of its section (at most three), and for its own concept when the draft is
   declined or fails twice, by the concept's compound or material names; each is its own `images`
   block (`BuilderEntry.adds_pictures`, the only builder allowed to return one), so the claim
   ledger's rule of one picture per images block, never repeated, never from a blocked site,
   holds unchanged.

## Consequences

- A section with a generated explainer finishes its built blocks only when the draft settles, so
  its reaction player and cards can arrive up to 150 s after its prose.
- Each Opus draft reserves its full output cap (18,000 tokens, about $0.36) from the optional
  headroom ($1.25 of an Expert cap of $2.50), so three drafts fit beside each other with their
  inputs; when other optional builders hold headroom too, a draft can be refused and its concept
  then falls back to its picture.
- `shared/explainer.simulation-mechanism.golden.json` fixes a mechanism explainer (the iron
  acetate of kut, no figure values) that both sides parse; the phase C golden is unchanged.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
