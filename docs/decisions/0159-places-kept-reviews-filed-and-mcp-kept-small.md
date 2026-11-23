# 0159. A place abroad refuses only practice there, a reviewer files any researched fact, and the MCP server describes its kinds once

A live-research write-back keeps the craft its source names when a place abroad is only where a
material came from, where goods went, or a site of undivided India; the craft researched is never
named by a plain English word of its own name; a held write-back found again leaves the hold; the
review queue files a fact under a family's science, re-files and retracts the write-backs approved
before the gates, and the Review page says why a write-back is held; the MCP server enumerates no
component kind in its tools, writes its index from its registry, reads PubChem's synonyms and
screens the questions that become work for names, at night.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief, mcp-and-contributors lane, on
the lead's review of the filing report on production, 2026-11-23). It amends
[decision 0136](0136-write-backs-filed-by-their-source.md), items 1, 3 and 4 and the consequence that
a held write-back found again stays held; [decision 0144](0144-stored-passages-as-evidence.md), its
one-word rule, which now also binds the craft researched; [decision 0147](0147-time-market-and-figures-kept-true.md),
the 62 KB budget it gave `tools/list`; [decision 0111](0111-fewer-mcp-tools.md), its small schemas;
and [decision 0113](0113-questions-become-work.md), how a question is anonymised. The contracts are
`docs/contracts/research.md` (The writer and the coverage job), `docs/contracts/knowledge-writes.md`
(The research write-back), `docs/contracts/review-queue.md` (Decisions; The Review page),
`docs/contracts/knowledge-api.md` (Small schemas; Source tools), `docs/contracts/open-work.md`
(Privacy; the index) and `docs/contracts/nightly-upkeep.md` (step 5b).

| For | Read |
|---|---|
| The filing ladder it amends | [decision 0136](0136-write-backs-filed-by-their-source.md) |
| The one-word rule it extends to the craft researched | [decision 0144](0144-stored-passages-as-evidence.md) |
| The tool list budget it restores | [decision 0147](0147-time-market-and-figures-kept-true.md) and [decision 0111](0111-fewer-mcp-tools.md) |
| How questions become work | [decision 0113](0113-questions-become-work.md) |
| The filing rule as it stands | [research.md](../contracts/research.md), The writer and the coverage job |
| Reviewing and filing a fact | [review-queue.md](../contracts/review-queue.md), Decisions |
| Every decision, by group | [README.md](README.md) |

## Context

The lead read the filing report (`python -m app.scripts.write_back_filing`) on production and found
good facts it would refuse: Ajanta's blue imported from Badakhshan in Afghanistan, the Indus bead
workshops at Chanhu-daro in Pakistan for Agates of Cambay, and Cambay carnelian found in Sudan. A
place abroad refused a sentence wherever it stood in it, though the sentence was about the craft's
material or history. The same report listed 33 write-backs approved automatically on 2026-11-17
that the queue would not retract ("No proposed or researched fact has the id"), a chemistry fact
(dehydroxylation of clay minerals) the report filed under the clay family that a reviewer could not
file there, and a general sentence about slip casting filed under Metal Casting because casting is a
word of its name. The MCP debt left over: `tools/list` grew by two enumerations of every component
kind, so decision 0147 raised its budget; the index was written by hand; PubChem's synonyms were
never read; questions were anonymised by rules alone; and three curation tooling duplicates.

## Decision

1. **A place abroad refuses only practice there.** `PlacesAbroad.read(text)` gives the places a text
   names as where something is practised and those it keeps: a place within three words after a
   word of origin (from, imported, mined, quarried, sourced, brought, obtained, procured) or of trade
   and finds (exported, traded, shipped, sold, reached, excavated, unearthed; been, was or were
   found) with no clause word between (`data/abroad_cues.py`), and the present country of a
   historical site or culture of undivided India the same text names. Only practised places refuse;
   a kept one lets the next level of the ladder decide, and a sentence no level files is held for a
   reviewer naming the place, never given to the family. Answers' off-question screen reads the same
   rule.
2. **The sites come from Wikidata.** `data/places_abroad.historical_sites.json` vendors, with its
   query and date, the items that are part of the Indus Valley Civilization or Gandhara in Pakistan,
   Afghanistan or Bangladesh and the archaeological sites and ancient cities of Pakistan and
   Bangladesh, with their labels, aliases and country (CC0); names under four letters or made only
   of English words are left out. A hand list would have been shorter and unprovable.
3. **The craft researched is not named by an English word of its name.** Its anchors and its index
   names follow decision 0144's rule for other crafts: a one-word Latin name that is an ordinary
   English word names it only as its full name. Distinctive words (Bidri, Ajrakh, Khurja) still do.
4. **A held write-back found again leaves the hold.** A filed write-back that meets its held twin
   (the same dedupe id, `DRAFT`, live research) moves it to the switch's status with a
   `ReviewEvent` by `live_research`.
5. **The queue decides any researched fact.** No backfill was needed: every write-back has carried
   `Claim.origin` `LIVE_RESEARCH` since the writer was built. What refused the 33 was the queue's
   test for gate checks. A fact of that origin is now decided whether or not it has checks; approving
   with `craft` or the new `family` (a category slug, chemistry, physics and materials only, filed as
   the write-back files family science) also moves an approved fact, which stays approved.
6. **The Review page shows the hold.** `FactReview.held {reason, suggestedCraft}` is read from the
   hold's `ReviewEvent` note, whose form `claim_writer.HELD_NOTE` also parses; no column was added.
   A File under picker offers every reader craft and each family's science and sends `craft` or
   `family` with Approve.
7. **The kinds are described once.** `mcp_schemas.compact` drops an `enum` that is exactly the piece
   kinds; `list_components` describes its `kind` by example and `edit_draft`'s component points to the
   kind schemas. The server still validates every kind. The budget is 60 KB again.
8. **The index is written from the registry.** `api/mcp_index.index_text` lists every tool, prompt
   and resource by its registry title; `tools/mcp_index_build.py` writes `data/contributor/index.md`
   and a test fails when the two differ. It is a generated file because the resource registry cannot
   import the tool registry that serves it.
9. **PubChem's synonyms are their own field.** `PubChemAdapter.synonyms` reads the first 12;
   `lookup` gives them as `pubchemSynonyms`, beside KalaVigyan's own `synonyms`, so neither is
   mistaken for the other. A contract test runs the production `LookupStore` over recorded replies.
10. **Questions are screened for names at night.** After the rules, the cheapest route
    (`AiTask.UNDERSTAND`) lists each kept question's people, 40 a call; a question about a person is
    dropped, a listed name is masked, a name the question does not hold drops it, and a question the
    screen could not read waits for the next night. Nothing runs at request time.
11. **Curation tooling.** The district seed reads the LGD register through `data/district_register`,
    which now refuses an unknown state or a repeated name; `tools/atomic_write.py` is the one atomic
    writer of the tools; `extract` takes `max_chars`, and curation reads up to 8,000,000 characters.

## Consequences

- The three production cases file under their crafts once the report is re-run; Khorezm, the
  Nigerian porcelain study and any sentence about practice abroad are still refused. "Porcelain from
  China" is now held for a reviewer, not refused.
- The 33 older write-backs can be retracted or re-filed by id in the queue; the lead reviews them with
  the filing report. No stored row changes until a reviewer acts.
- A component card's title follows the answer's language; its kicker and link stay English until
  reviewed interface words exist (`docs/TECH_DEBT.md`).
- The map layer dataset proposal over MCP is not in this record; its debt entry stays.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/write_back/test_places_abroad_kept.py`, `test_filing_names.py`,
`test_write_back_names.py`, `backend/tests/db/test_held_write_backs_db.py`,
`test_review_queue_refile_db.py`, `test_answer_gaps_db.py`, `backend/tests/review_queue/test_review_queue_rules.py`,
`backend/tests/mcp/test_tool_budget.py`, `test_skill_references.py`, `test_lookup_store_live.py`,
`test_lookup_references.py`, `backend/tests/research/test_question_names.py`,
`backend/tests/test_district_seed.py`, `tools/tests/test_atomic_write.py` and
`frontend/e2e/review-queue-unit.spec.ts`.
