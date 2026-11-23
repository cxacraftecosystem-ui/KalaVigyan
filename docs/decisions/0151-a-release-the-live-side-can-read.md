# 0151. A release is one the live side can read: the web ignores a field it does not know, every migration reads under the release before, and the first stage's fusion is measured before it is weighted

The production web ignores payload fields it does not know while its specs refuse them, the
goldens show every field a served payload can carry, every migration stays readable and writable by
the release before it, the claim fusion is weighted by a measured file, and the question writer asks
once more when a question copies its fact.

Date: 2026-11-23. Status: accepted (the lead's round 7 brief, platform and retrieval lane, from
release 77ca8661 on 2026-11-22 and the debt register). It amends
[decision 0132](0132-a-ranking-votes-with-its-first-thirty.md) (the fusion's weights) and
[decision 0133](0133-the-evaluation-scores-what-answers-read.md) (the evaluation's modes and the
question writer). The contracts are `docs/contracts/frontend.md`, `docs/contracts/infra.md`
(Migrations) and `docs/contracts/retrieval.md` (Ranking, The generated questions, Evaluation).

| For | Read |
|---|---|
| The fused order's voting depth, now weighted | [decision 0132](0132-a-ranking-votes-with-its-first-thirty.md) |
| The evaluation and the generated questions it extends | [decision 0133](0133-the-evaluation-scores-what-answers-read.md) |
| The journal name whose arrival broke the pages | [decision 0143](0143-lessons-exports-and-follow-ups-kept-true.md) |
| How a release migrates, seeds, checks and switches | [infra.md](../contracts/infra.md), Migrations and Seeds |
| How the web parses a response | [frontend.md](../contracts/frontend.md) |
| The golden field check leaving out what the web never parses | [decision 0168](0168-a-table-under-a-said-sentence-and-python-within-budget.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **The web refused a field the backend added.** Every release ships the backend first: Deploy
  backend fires the Vercel hook at its end, so for the minutes the web build takes the old web reads
  the new API. Release 77ca8661 began sending `containerTitle` on a source (decision 0143); the shape
  kit's `object` refused unknown keys, so every craft page citing a journal paper (Block Printing of
  Akola) answered 500 from about 17:15 to 17:39 UTC, until hotfix 15139bb3 taught `sourceRefShape`
  the field.
- **Every check had passed.** The craft page goldens are built by the backend's own preview, but no
  curated source carries a journal name, so no golden showed the field, and the web's strict parse of
  the goldens could not miss it.
- **A stopped release ran the old code on the new schema.** A release migrates and seeds before its
  retrieval check; when the check stopped round 7's release (2026-11-22, decision 0132), the live
  release's models read `AiProvider` and `AiTask` as closed lists and raised `LookupError` on
  'VOYAGE' and 'RERANK', which broke the admin route-order save, and migration 0061's renamed stamp
  hid every vector not yet renewed from its vector search.
- **The fused order is weak on paraphrases.** On release db09b9e7 the fused order scored recall at 5
  of 0.414 on the 58 generated English questions against 0.987 reranked: the full-text and
  named-concept rankings, finding words the question shares with many facts, outvote the vector
  ranking, which places the expected fact in its first three for 52 of 55 of them.
- **The question writer kept few questions.** Run 44993519051 dropped 580 of 727 sampled facts'
  questions for reusing their fact's distinctive words.

## Decision

1. **The production build ignores an unknown field; everything else refuses it.**
   `frontend/lib/shape.ts` reads `BUILD_UNKNOWN_FIELDS` from `NODE_ENV`: `ignore` in the production
   build (server and client, where Next inlines it), `refuse` in the development server, the unit
   specs and the browser runs. `parseShape(shape, value, policy)` sets the policy for one synchronous
   parse, and a parse inside it keeps it. Ignoring drops the field; every known field is still
   parsed as strictly, and a value outside a vocabulary (`oneOf`, `tagged`) or a dictionary's keys is
   still refused, as are the drawing elements and held-text marks of a component spec, which are
   rendered markup. A union over object shapes must be told apart by a tag, never by refusing a
   field.
2. **The built site proves it.** The smoke run starts one API stub for the whole run
   (`frontend/e2e/smokeApi.ts`, Playwright's global setup when `E2E_SMOKE=1`, shared with the native
   monograph smoke), which serves Farrukhabad Prints' page with a field added to every object, and
   `later-backend.smoke.spec.ts` asks the built site for it and expects the page.
3. **The goldens show every field a served payload can carry.**
   `backend/tests/contracts/test_golden_fields.py` lists each JSON golden with the model it
   validates as, walks each golden beside its validated model, and fails while any field of any model
   reachable from a served payload (the craft page, the category page and list, the catalogue, the
   compare screen, the explainer) appears in no golden, so a field the backend adds, even one sent
   only sometimes, fails the pull request until a golden carries it, and the web's strict parse of
   that golden then fails until its shape knows it. The 174 fields no golden showed on 2026-11-23 are
   listed in `tests/contracts/unshown_fields.json`, which the test holds exact, so it only shrinks;
   the catalogue's records, served only to the MCP tools, are kept out by name. `frontend/e2e/golden-files-unit.spec.ts` fails
   while a golden in `shared/` is read by no unit spec and is not listed as read only outside the web.
4. **Every migration stays readable and writable by the release before it.** Every PostgreSQL enum
   is declared through `models.base.pg_enum`, an `OpenEnum` that reads a label it does not list as
   its text, so a label may be added once a release that reads it has shipped; a required column the
   release before does not map has a default or is filled by a `BEFORE INSERT` row trigger; a renamed
   value keeps its old form current until the switch. The probe found one on its first run: migration
   0074 made `McpToolCall.clientName` required, and production's release records MCP calls without
   it, so a stopped round 7 release would have failed every call it recorded; migration
   `0075_mcp_call_name_filled` fills a missing name from the grant's client, as 0074's backfill does. Backend checks, after `alembic upgrade head`, the seeds, the database tests and the
   curated import, checks out the release before (`main`, or the push's previous head on `main`) and
   runs `tests/db/previous_release_probe.py` under its models: every mapped table is loaded whole,
   every enum label the database holds must be listed or read as later, and every required column
   without a default must be mapped. The same probe runs under this release's models. The retrieval
   check stays after the migration, since a check before it would run new code on the old schema.
5. **The claim fusion is weighted by a measured file.** `fusion.reciprocal_rank_fusion` takes a
   weight per ranking (`weight / (k + rank)`), and the claim rankings read `k` and the lexical,
   vector and entity weights from `app/data/eval/fusion.json`, equal (k 60) as before.
   `eval_retrieval --fusion` reads each hand-written and generated question's three rankings once,
   read-only, fuses them under 60 weightings in memory, and picks the one that scores the generated
   English questions best without lowering the hand-written ones; `--out` writes it. The weights
   change, and the fused floors rise, only with the lead's production run.
6. **The approved Kutch Ajrakh page includes the ground figure, and every release compares all of
   it.** The "why here" figure the API places in Kutch Ajrakh's why chapter (`with_why_here`, a
   round 7 lane) is part of the approved page by the owner's word of 2026-11-23. The Monograph parity
   run after each deploy compares the text, the chapters, the first citation and figure, and the
   borrowed components (it compared the borrowed components only), so any later difference from the
   approved page fails the release's parity run. Until the approved page carries the figure through
   its own update path (a fragment, its content entry and the build), the text and chapter
   comparisons report the figure's lines and the chapters below it.
7. **A copied question is asked again once.** The facts whose question reused their distinctive
   words are sent back in one more call naming the words reused (`REWRITER_SYSTEM_PROMPT`); a question
   kept then counts as `rewritten`, one copied again as copied. The run reports the facts asked, the
   English questions kept and their share.

## Consequences

- The live web shows what it knows of a newer payload and drops the rest until its build lands; a
  newly allowed value of a closed vocabulary still fails, so a backend adds a value only after the web
  that reads it.
- A golden must hold an example of every field: a new optional field needs a golden that carries it
  in the same change.
- An enum label added while production's models are closed fails Backend checks until the release
  that carries `OpenEnum` has shipped; after it, a label added fails nowhere, and the old release
  reads it as text.
- The default first stage is unchanged until the lead commits a measured `fusion.json`; the sweep
  embeds the questions it asks (cents) and calls no rerank or judge.
- A copied fact costs one more batch call per batch that had one.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/shape-unknown-fields-unit.spec.ts`, `frontend/e2e/later-backend.smoke.spec.ts`,
`frontend/e2e/golden-files-unit.spec.ts`, `backend/tests/contracts/test_golden_fields.py`,
`backend/tests/test_release_compatibility.py`, `backend/tests/db/test_previous_release_db.py`,
`backend/tests/db/test_mcp_call_name_fill_db.py`,
`backend/tests/retrieval/test_fusion_weights.py` and `backend/tests/retrieval/test_question_rewriting.py`.
