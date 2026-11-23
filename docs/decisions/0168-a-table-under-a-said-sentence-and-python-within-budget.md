# 0168. A quantities table is drawn under a sentence the answer already said, and the Python files are split along what they do

A quantities row whose sentence the answer already said keeps its quantity and its citation and
points to the sentence that said it, which every reader of the answer then reads once; the four
Python files over budget are split along their responsibilities with their callers' paths kept or
moved, the long and wide functions outside the other lanes' areas are cut into named steps, and
the initial migration stays one file by choice.

Date: 2026-11-23. Status: accepted (the lead's final clean-up brief of 2026-11-23, within the
owner's go-ahead of 2026-11-22 to clear the register "not just for this round, also for all
time"; the lead chose the table's way, which [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md)
left to the lead). It amends [decision 0147](0147-time-market-and-figures-kept-true.md) (item 1,
the table drawn with each sentence under its rows, and its consequence that the table repeats the
prose) and [decision 0134](0134-each-sentence-once-in-a-block.md) (what the judge reads). It is
the third record of limits kept by choice after [decision 0137](0137-limits-kept-by-choice.md)
and [decision 0163](0163-limits-kept-by-choice-and-a-register-that-only-shrinks.md). The
contracts are `docs/contracts/explainer.md` (One claim, one rendering; Each sentence once; the
`quantities` kind), `docs/contracts/answer-eval.md` (The judge) and `docs/contracts/voice.md`
(Listen).

| For | Read |
|---|---|
| The quantities table and the rubric's shown sentences | [decision 0147](0147-time-market-and-figures-kept-true.md) |
| A sentence once in a block, and the judge reading what a reader sees | [decision 0134](0134-each-sentence-once-in-a-block.md) |
| The run that found the table dropped, and the choice left to the lead | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| A reading that points to the sentence already showing it (`DifferRead.shownIn`) | [decision 0098](0098-craft-page-chapters-build.md) |
| The earlier records of limits kept by choice, and the earlier splits with their import paths kept | [decision 0137](0137-limits-kept-by-choice.md), [decision 0163](0163-limits-kept-by-choice-and-a-register-that-only-shrinks.md) |
| What is still below standard | [TECH_DEBT.md](../TECH_DEBT.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Run 45112746194 of answer-quality (release 1ab422fe, 2026-11-23) built decision 0147's
quantities table once, in the water and climate answer's PROCESS section, and the claim ledger
dropped it: every row's sentence was the text of a ladder stage sentence the section had already
shown, and a story block never repeats a sentence said word for word. Showing it meant either
letting the table repeat those sentences, which the judge marks down as repetition, or drawing its
rows under the sentence already said without saying it again; decision 0165 left the choice to
the lead, who chose the second.

The debt register's "Python code over budget" listed six files over 400 lines, 36 functions over
40 lines and 9 with more than five positional parameters. Four of the files were this lane's:
`services/two_factor.py` (703 lines), `etl/crafts/aliases.py` (535), `tests/db/test_db_flows.py`
(473) and `data/craft_master_loader.py` (433). `etl/crafts/seed_claims.py` belonged to the
pictures lane, and the initial migration is never rewritten.

## Decision

### A row said above keeps its quantity and its citation

1. **The ledger points to the sentence that said it.** `QuantityRow.shownIn` (optional, left out
   when absent) is the id of the first sentence of the answer whose text, or English original, is
   the row's sentence. Only the claim ledger sets it (`ledger_payloads.quantity_rows`, from the
   text keys it already records, now mapped to the id that showed each first); a row so said is
   never left out as a repeat, any other row follows the story rule as before, and a stored or
   reused table's `shownIn` is set afresh by each answer's ledger. The rows of one sentence say
   where it is shown together or not at all.
2. **Its sentence is not shown again.** `QuantitiesBlock.shown_sentences` leaves out a row's
   sentence that carries `shownIn`, so everything that reads what a reader sees reads it once,
   where it is said: the judge and the rubric (`coverage_answers.shown_field_sentences`), the
   stored answer sentences (`answer_rows`) and Listen, whose blocks now read their shown sentences
   rather than every cited one (`voice/narration`). The judge's figures block still lists every
   row's quantity.
3. **The view draws the rows with the sentence's citation.** For such a row group the client draws
   the rows, with the sentence's citation cluster glued to the last row's stated words, which carry
   the sentence's anchor for the margin notes and light when the cluster opens, and the table body
   is described by the sentence it points to (`aria-describedby`); the sentence is not written
   again. The web shape accepts `shownIn` as optional, so a page from the release before reads the
   same.

We chose an id over a flag, as `DifferRead.shownIn` does for a reading the page already shows: it
ties the rows to their sentence for assistive technology and lets a test check where it points.

### The files over budget, split

4. **Two-step verification** keeps its sign-in challenge and turning it on and off in
   `services/two_factor`, which re-exports, for the routes and tests that call `two_factor.<name>`,
   the parts now in `two_factor_codes` (TOTP codes, the authenticator URI and QR, recovery codes),
   `two_factor_keys` (the secrets' encryption keyring) and `two_factor_attempts` (attempt budgets,
   lockouts and checking a code). About twenty modules call it as one service, as the routes did
   before.
5. **The master list** keeps its seed plan in `data/craft_master_loader`, built from one function
   per kind of row; the DB-free catalogue in the designer portal's fields, which only tests read,
   moved to `data/craft_master_catalogue` with its three test callers.
6. **The alias merger** (`etl/crafts/aliases.py`) keeps its sources and the merge, reading
   `alias_entries` (an alias entry, the trust order and deduplication), `alias_scripts`
   (romanisations and transliteration) and `alias_codes` (cross-portal codes mapped exactly or
   by a fuzzy score of at least 90 leading its rival by 5); `merge` takes its optional sources by
   keyword. Only its tests imported the moved names, and they import them from their new homes.
7. **The flows' database tests** are three modules by what they prove: `test_db_flows` (the schema,
   the owner's keys, routing, usage and suspension), `test_signup_db` and `test_router_db`. The
   owner the first module set up, signing in and turning on two-step verification once, is the
   session fixture `owner` in `tests/db/conftest.py`: a session fixture defined in two modules runs
   twice, and its second run would find the owner already set up.

### Long and wide functions

8. The long and wide functions outside the other running lanes' areas are cut into named steps in
   their own modules, behaviour unchanged, and wide ones take their optional parameters by keyword:
   the access, usage and users routes (FastAPI handlers keep their query, body and dependency
   parameters after a leading `*`; the roster's filters and sorts moved to `api/access_filters`,
   since the access routes would otherwise pass 400 lines), the Anthropic, Gemini and OpenAI
   adapters' requests, failures and results, the adapter registry, the app factory, the catalogue's
   reads, the craft seed and a task's routing state, the geo ETL's load and its row writers (a
   row's unit and a layer's variable, depth, unit and statistic by keyword), the crafts ETL's paced
   JSON read, the secrets seeding script and the craft-pages skill's gaps report. What is left (the
   seed claims, in the pictures lane's files, and one knowledge reader in the contributors' lanes')
   stays in the debt register until those lanes have merged.

### The limit kept

| Limit | Why it is kept | What would change it |
|---|---|---|
| `backend/migrations/versions/0001_initial_schema.py` is one file of 2,853 lines and its `_create_tables` one function of 2,383. | A migration is never rewritten: the schema it made is the one every database already holds, and a rewrite could change what a fresh database gets. | Nothing in the code: a squash of the migration history, if the owner ever asks for one, would replace it. |

## Consequences

- No migration. The quantities payload gains an optional field that only an answer's ledger sets;
  pieces store the builder's table without it.
- A table whose every row restates the ladder is now shown, so the judge's figures part can see
  the numbers it carries; `rubricMean` stays at 0.82 until the lead's next answer-quality run
  measures it (the register's entry says so).
- Listen reads a sentence two items of one block share once, as the page shows it.
- The hygiene baseline falls by the files and functions cleared here.

## How this record is kept true

It is not edited after acceptance except to mark a row superseded: a later choice is a new record
that names this one, and the table above links the two both ways. It records the choices as taken
on 2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/contracts/test_explainer_quantities.py`, `backend/tests/ledger/test_ledger_kinds.py`,
`backend/tests/research/test_shown_sentences.py`, `backend/tests/voice/test_narration.py`,
`frontend/e2e/quantities-unit.spec.ts` and, for the splits, the tests of each moved module, which
are unchanged but for their imports.
