# 0015. Science engine: balancing, units, envelopes, the science seed and the process route

A pure `backend/app/science/` layer balances reactions on the server, normalises conditions with
pint and checks them against stage envelopes whose constants are cited claims. The science seed
stores processes, stages, reactions and compounds looked up in PubChem, served by `GET
/api/crafts/{slug}/process`.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [science.md](../contracts/science.md) |
| What amended part of it | [0152](0152-matter-read-once-and-the-science-seed-kept-true.md): The seed's deletions, tools and stage roles, and the kaolinite constant cited to a thermal-analysis paper |
| A reading outside its stage's range waits for a reviewer, who keeps it or takes a misreading off the view | [decision 0169](0169-mcp-follow-ups-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN 7 and 17 (day 4) ask for the science engine: reactions balanced by the server and never
taken from a model, conditions normalised with pint and checked against stage envelopes, each
physical constant its own cited claim, compounds looked up in PubChem, processes and stages
seeded from the seed claims, and `GET /api/crafts/{slug}/process` answering the contract of
decision 0014 (`docs/contracts/science.md`, `shared/science.process.golden.json`). The schema
had `Reaction` without a label or a claim link and no place for a condition reading tied to one
claim.

## Decision

1. **A `science` layer** (`backend/app/science/`): pure code, no database, no network. It may
   import `schemas`, `research` and `core` (`LAYER_IMPORTS`); `services` and `api` may import
   it. `services` still may not import `schemas` (the hygiene test pins that), so the service
   gathers rows into plain records (`science/records.py`) and the route hands them to
   `science/process_view.craft_process`, which builds the contract model. The contract's rules
   (`mhchem_equation`, `reaction_level`, `envelope_status`, `sources_differ`, `weakest_level`,
   and now `cited_source_ids`) are imported, never re-implemented.
2. **Balancing** (`science/balance.py`, `CHECKER_VERSION = "balance/v1"`). Formulas are parsed by
   `science/formula.py` (brackets, hydrate dots `·`, `•`, `.`, `*`, mhchem charges `^3+`, the
   electron `e^-`), the element matrix gets a charge row when any species is charged, and the
   integer null space is computed with sympy rationals. Balanced means exactly one null-space
   vector whose smallest integer form is all positive; otherwise the outcome is
   `NO_SOLUTION`, `NOT_UNIQUE` or `NOT_POSITIVE` and no coefficient is stored. Coefficients are
   written only by `science/reactions.check_reaction`, which takes species without
   coefficients, so a model's numbers cannot reach a row. ChemPy was not added: it is not a
   dependency and wraps the same sympy null space.
3. **Units** (`science/units.py`). One pint registry per process; readings are stored as stated
   (bounds and unit) and normalised when the answer is built, rounded to 6 decimals, so the
   stored value never drifts from the source and `CONDITION_UNITS` stays the one home of the
   target units. pH is not a pint unit: only `pH` is accepted. A unit of the wrong dimension,
   an unknown unit, missing or reversed bounds are refused.
4. **Envelopes and constants** (`science/envelopes.py`). The PLAN 7 envelopes, each naming the
   constants that bear on it. Each constant is a claim seeded through `claim_seed.seed_claims`
   from `app/data/science_seed.json`, quoting a pinned Wikipedia revision verbatim (checked
   against the revision text on 2026-11-16). PLAN 7's "kaolinite dehydroxylation 450–600 °C" has
   no single source that says it; the cited revision says dehydroxylation begins at
   550–600 °C, so the constant is 550–600 °C. Brass is cited for its melting range (900 to
   940 °C), the wording of the source. Quartz, kaolinite and beeswax claims attach to the
   existing terracotta and kalamkari concepts so they show on those crafts; water and brass get
   global `PROPERTY` concepts.
5. **Storage** (migration `0004_science_storage`). `ReactionCitation(reactionId,
   claimSourceId)` links a reaction to the citations that support it; `ProcessCondition`
   (owned by exactly one stage or reaction, `key`, `label`, `quantity`) and `ConditionReading`
   (one citation, the stated phrase, stated bounds and unit). Links are to a citation, not
   only a claim, because the golden file shows a reaction's or reading's claim with only the
   citation that supports it. `Reaction` gains `label`, `ordinal` and `deltaHClaimId`; its
   unused `conditions` JSON is dropped (conditions have one home) and `species` is a list.
   `quantity` is a string checked by the contract model rather than a new Postgres enum.
   `Material` is now unique by name within a concept, because the seed's material concepts are
   per craft and two crafts both have an "Alum (fitkari)"; the compound is what identifies the
   substance across crafts. The science tables moved to `models/science.py` and the evaluation
   tables to `models/evaluation.py`, which brings `models/knowledge.py` under budget.
6. **The science seed** (`services/science_seed.py`, run by `app/scripts/seed_claims` after the
   claim seed, so the deploy needs no new step). Stages stay those of the claim seed
   (immersive stage concepts with an ordinal). Materials come from the seed's stage `USES`
   material edges, one `Material` per material concept with the curated kind and role, and the
   edge's claim as `StageMaterial.claimId`. Reactions and readings are hand-curated with the
   seed claim and citation that support them: iron acetate (Ajrakh kut, Machilipatnam kasim),
   indigo reduction and air oxidation (Ajrakh), the alizarin–aluminium lake as species only
   (Ajrakh, Bagh, Machilipatnam), and the durations and concentration the claims state. The
   plan refuses a material without a kind, a reaction on a stage that is not seeded, a
   citation the claim does not have, and a reading whose phrase its claim or quote does not
   say. Science rows are upserted by derived id, so a corrected seed file corrects the rows;
   constants go through the claim seed, which only inserts.
7. **Compounds** (`services/compound_lookup.py`, `app/scripts/link_compounds.py`). The seed
   stores compounds by name and formula; the lookup finds each one through the existing PubChem
   adapter (a typed `PubChemAdapter.compounds` was added, no new client), by name and then by
   Hill formula, accepts only a record with the same element counts, and fills the CID,
   properties and a `COMPOUND_RECORD` source. Ions are not looked up.
8. **The route** (`GET /api/crafts/{slug}/process`, `api/routes/crafts.py`): signed in like the
   other craft routes, `MERGED` slugs answer with their target, 404 `NOT_FOUND_DETAIL`,
   `Cache-Control: private, no-cache`, built only from stored rows. Visible claims are fetched
   with `knowledge_view.claims_by_id`; a stage's and a material concept's claims only from
   concepts that are `OPEN`.
9. **Orders** the contract left open: claims by level (strongest first), then text, then id; a
   claim's citations quoted first, then by id (the profile's order); readings by their claim,
   then the stated phrase; conditions by quantity, label, key; reactions by ordinal, label;
   materials by name. A material's view id is its `StageMaterial` id; a condition's id is
   `<stage or reaction id>.<key>`. The golden file listed one claim's two citations in seed
   order; it now lists them in the profile's order, the only change made to it.

## Consequences

- The route reproduces the golden file from stored rows (DB test) and from records (DB-free
  test); the seed gives Ajrakh, Bagh and Machilipatnam reactions and readings, with the Bagh
  bhatti and curing durations and the Machilipatnam myrobalan bath flagged "Sources differ".
- Kaolinite has no reaction yet: the terracotta seed is sub-category mechanism chains, not a
  craft process, so there is no `FIRE` stage to hold it. Reactions and readings for the other
  crafts, a writer for researcher or model proposals, the review-queue listing of `OUTSIDE`
  readings and running `link_compounds` on the box are in the debt register.
- New dependencies: `sympy` and `pint` (latest, locked in `backend/uv.lock`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
