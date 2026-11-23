# 0147. Quantities given in prose are also a table, the timeline lists undated history and places what the register holds, and market and measure readers read what sources state

A section whose cited facts state three or more quantities shows them as a cited quantities table;
the rubric counts each shown sentence once and the judge is told each figure's kind and the
quantities it shows; the timeline places a name the district register or curation holds before it
asks Wikidata and, as version 2, lists the section's undated history; region readers read a
district's other names; a price is read from a claim stating one price, year and district; and the
curation checks every GI and price date at its own precision.

Date: 2026-11-22. Status: accepted (the lead's debt-clearing brief, lane "time, market, measures and
figures", 2026-11-22). It amends [decision 0054](0054-phase-c-contract.md) (the timeline's version
1 fields), [decision 0057](0057-zoom-story-and-timeline-map.md) (timeline places through Wikidata
only), [decision 0062](0062-phase-d-contract.md) (the phase D kinds), [decision
0066](0066-local-measures-and-market-gi.md) (prices from curated rows only; `per` after "per" or "/";
regions by register spelling) and [decision 0134](0134-each-sentence-once-in-a-block.md) (the rubric
still counting every copy). The contracts are `docs/contracts/explainer.md` (the phase C and D
blocks and builders) and `docs/contracts/answer-eval.md` (the rubric, the judge and the floors).

| For | Read |
|---|---|
| The timeline's version 1 | [decision 0054](0054-phase-c-contract.md) and [decision 0057](0057-zoom-story-and-timeline-map.md) |
| The phase D kinds and their builders | [decision 0062](0062-phase-d-contract.md) and [decision 0066](0066-local-measures-and-market-gi.md) |
| A sentence once in a block | [decision 0134](0134-each-sentence-once-in-a-block.md) |
| The evaluation and its floors | [decision 0133](0133-the-evaluation-scores-what-answers-read.md) |
| The blocks as built | [explainer.md](../contracts/explainer.md) |
| The component kinds are no longer enumerated in the tools, and the 60 KB budget is restored | [decision 0159](0159-places-kept-reviews-filed-and-mcp-kept-small.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Run 44994632550 of answer-quality scored the judge's figures part 2.8 of 5: the Ajrakh indigo, the
Jaipur safe-handling and the Bandhani tie-and-dye answers gave dip times, kiln temperatures, tying
days and lengths only in prose, and the judge was told only how many figures a field had. The
rubric counted every copy of a sentence a block carries while the judge read each once. The
timeline placed places through Wikidata labels only (Ajrakhpur, Dhamadka and Kutch stayed
unplaced) and offered no undated claim. "A seer of Kutch" named no region, "Rs 1,500 a metre"
showed no unit, a price claim could be said twice in one market block, a curated GI date was
checked by its year only and a price date not at all, and "1500 people" was offered as a year.

## Decision

1. **A quantities table.** A new phase D kind `quantities` `{rows[QuantityRow] (3-12)}`,
   `QuantityRow {stated, low, high?, unit, measures, sentence}`, built for every field by
   `services/quantities_builder` from the amounts of the section's cited facts
   (`research/stated_amounts`: a number or range before a unit of temperature, time, mass, length,
   area, volume, concentration or share, a local unit, or "pH" before a number; two-character
   symbols matched as written). Three rows at least, so a section stating fewer quantities shows
   none; feet, inches, yards, miles and square feet stay with `measure`, which converts them. The
   client draws one table, the rows of a sentence as one table body with the sentence once under
   them. Migration `0072_quantities_kind` widens the piece and proposal kind checks.
2. **The judge sees what each figure shows.** `judge_message` adds an untrusted block listing each
   figure by field with its kind and the labels it shows that state a number; the judge's figures
   criterion names it. The rubric's sentence counts read `shown_field_sentences`, so a sentence
   five supply links share counts once. The rubric floor is re-based to the lowest mean the new
   count can give on that run's answers (0.872, since a consulted field keeps one sentence and only
   a field with a figure loses copies), less 0.05: 0.82. The lead raises it after the next run.
3. **Timeline version 2.** A timeline adds `undated[{place?, sentence}]` (the section's fact
   claims that state no year, at most 6, each with the first listed place it names or a register
   district it names) and `places[].districtLgd`. Places are placed first by the district register
   and its other-names table at `AdminDistrict.centroid` (`services/place_register`), then by a
   Wikidata id the craft's curation stores on a place of that name (its `WikidataPoint`), and only
   then by the Wikidata label search. A block carrying neither undated sentences nor register
   places stays version 1, so stored and golden version 1 blocks read as before; version 1 refuses
   both. Supply maps keep their own rule: their contract places only with Wikidata coordinates.
4. **Other names read as their district.** `stated_names.register_places_named` returns the
   register spelling for a name `data/district_other_names.json` lists, so every region reader
   (`measure_regions.stated_region`, component places, the timeline) reads "Kutch" as Kachchh. The
   prose and heading checks still test only names written as the register spells them, but accept
   any spelling of the place in the supports.
5. **Market readers.** `per` is read after "per", "a", "an" or "/", never after a quantity word
   ("a few") nor before "ago"; "each" is left out because nothing after it names a unit. A claim of a
   price row is never a GI sentence. A craft without curated price rows reads its claims naming a
   price and keeps one stating exactly one price, one year and one LGD district
   (`market_store.stated_price_offer`); anything less certain waits for a curated row.
6. **Dates checked at their precision.** The curation reports a GI `filedOn` or `registeredOn` and
   a price `date` that no quote of its claims states at its own precision
   (`stated_dates.states_date`). Tikuli Painting's 2018 price, whose only date is the letter-spaced
   "2 0 1 8" of a survey's cover, is removed from its dossier; the builder never showed it.
7. **Counts are not years.** A numeral before an irregular counted noun (people, men, women,
   children, folk, cattle, sheep, feet, geese, teeth, workmen) is not offered as a year.

## Consequences

- Migration `0072_quantities_kind` (down revision `0080_stream_stamps_differs_on`) only widens two
  check constraints; its downgrade deletes quantities pieces.
- A history answer's timeline may now arrive as version 2; clients read both versions.
- The new kind joins the piece-kind enums of two MCP tools (`list_components`, `edit_draft`),
  which took the tools list's input to 61,450 bytes, 10 over its 60 KB budget; the budget is now
  62 KB (`tests/mcp/test_tool_budget.py`, `docs/contracts/knowledge-api.md`) rather than leaving
  the kind out of a filter that reads stored pieces.
- The quantities table repeats sentences the section's prose already says, as `measure` does; the
  claim ledger keeps each fact once in prose.
- The rubric's scores can only fall with the shown-sentence count, never rise.
- The production run asks two more questions (a materials and a history one) and passes them only
  when a zoom story and a timeline arrive.
- Left in `docs/TECH_DEBT.md`: the judge's measurement of the table, the derived-figure rule that
  waits on the owner, curation of regional units, prices, GI records and cited districts, the
  dossier field for imitation, and the sentence-once leftovers.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/contracts/test_explainer_quantities.py`, `backend/tests/research/test_stated_amounts.py`,
`backend/tests/research/test_shown_sentences.py`, `backend/tests/retrieval/test_eval_floors.py`,
`backend/tests/journey/test_timeline_undated.py`, `backend/tests/journey/test_timeline_map.py`,
`backend/tests/answering/test_section_blocks.py`, `backend/tests/answering/test_measure_builder.py`,
`backend/tests/answering/test_market_builder.py`, `backend/tests/answering/test_stated_price_offers.py`,
`backend/tests/research/test_gi_registry.py`, `backend/tests/curation/test_dossier_checks.py`,
`frontend/e2e/quantities-unit.spec.ts`, `frontend/e2e/timeline-undated-unit.spec.ts` and
`frontend/e2e/production-kinds-unit.spec.ts`.
