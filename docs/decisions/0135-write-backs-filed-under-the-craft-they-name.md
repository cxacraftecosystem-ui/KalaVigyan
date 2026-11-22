# 0135. A write-back is filed under the craft it names, every stored text is storable, and an answer records its cost

Live research files a fact under a craft only when the fact or its quote names that craft, sends
general material science to the craft family's science, refuses facts about places outside India,
stores every text it keeps free of NUL and control bytes, and records each answer's cost and
latency on its row.

Date: 2026-11-22. Status: accepted (the lead's round 7 brief, write-back lane, from the live research
test of answer 504968ea-49cc-469c-88f9-205a2ea90e8a on production, 2026-11-22). It amends
[decision 0124](0124-live-research-write-back.md), item 6. The contracts are
`docs/contracts/research.md` (Retrieved text is untrusted; The writer and the coverage job; the
answering service) and `docs/contracts/knowledge-writes.md` (The research write-back).

| For | Read |
|---|---|
| The write-back rules it amends | [decision 0124](0124-live-research-write-back.md) |
| The family science a craft's answers read | [decision 0122](0122-evidence-reach.md) |
| The craft resolver whose names it matches | [decision 0004](0004-craft-resolver.md) |
| How a fact's craft is chosen | [research.md](../contracts/research.md), The writer and the coverage job |
| The write-back's gates | [knowledge-writes.md](../contracts/knowledge-writes.md), The research write-back |
| Every decision, by group | [README.md](README.md) |

## Context

An EXPERT question about Khurja Pottery, a craft with no stored facts ("How is the clay body of
Khurja pottery prepared and fired, and what gives its glazes their blue and turquoise colours?"),
answered in 285 s with 48 cited sentences from 13 sources and wrote back 19 facts, all `IN_REVIEW`
under the RESEARCH `AUTO` switch. Three faults showed.

- **A PDF could not be stored.** One expert seat's live research failed with `psycopg.DataError:
  PostgreSQL text fields cannot contain NUL (0x00) bytes` on `INSERT INTO "Chunk"` for a paper whose
  text CORE returned with NUL and `\x03` bytes, so the seat stayed on stored evidence. The fetcher
  already cleans what it reads, but an adapter's own text (CORE's `fullText`) reached the store
  through `sources/adapter.build_document` as it came.
- **Facts were filed under a craft they do not name.** Every written fact went to Khurja Pottery's
  concept, because outside a comparison a sentence always stayed with the craft researched
  (`write_back_crafts.craft_filing`). Among them: "In Khorezm practice, clay is kneaded thoroughly by
  hand ..." (Khorezm is in Uzbekistan), "In a Nigerian porcelain study, the 43.2 wt.% Si2O in the
  feldspar ...", "Porcelain is made by heating refined kaolinite clay in a kiln at temperatures
  between 1200 °C - 1400 °C ...", "A kiln-schedule guide likewise says damp or thick-walled work needs
  a longer candle ..." and "It adds that synthetic and polymer clays offer greater consistency,
  durability, and ease of use." Decision 0124 said a fact is filed under "the section's field and the
  craft they name", but only a comparison read the names.
- **The answer row kept no cost.** Answer 504968ea has `costUsd` 0 and `latencyMs` null although it
  made many model calls. No path wrote either column: the API's streaming answer and the evaluation
  (`app/scripts/eval_answers.py` `answer`) both finish through `SqlAnswerStore.finish`, which set
  neither.

## Decision

1. **One rule for stored text.** `research/storable.storable_text` removes NUL and the C0 controls
   other than tab, line feed and carriage return; the line-separating ones (vertical tab, form feed
   and the file, group, record and unit separators) become a line feed, so the words on either side
   of a PDF's page break do not run together, and every visible character is kept byte for byte.
   `build_document` makes a document's text storable before it hashes and caps it, so the composer
   quotes from the text that will be stored; the chunk store (`retrieval/indexing._apply`, both the
   chunked and the planned paths), the kept quote chunks, a live source's title, authors,
   publisher, licence and attribution, and the claim writer's text and quote use it too.
   `clean_untrusted_text` reads the same control set from it.
2. **A quote matches what is stored.** `research/quotes.normalise_quote_lines` makes its text
   storable first, so `quote_key` reads a quote and a stored passage alike whether or not the
   source carried the bytes, and a re-chunked source re-links its earlier quotes.
3. **A fact is filed under the craft it names** (`write_back_crafts.craft_filing` over
   `write_back_names.CraftNames`). The text is read first, then the sentence's passing quotes, as
   whole words of the resolver's keys (`data/craft_text.core_key`):
   - The craft researched, and in a comparison each compared craft, is named by a word of four
     letters or more of its name that no other of them shares and fewer than three master-list
     crafts use (the comparison rule of decision 0124), by a name, alias or spelling the craft index
     holds for it, or by a place of its below a state: its districts and place labels, a district's
     other name, or a place word of its own name (Kutch for Kutch Ajrakh, Khurja for Khurja
     Pottery). A state names no one craft. A word two of the crafts share names neither; a text
     naming two of them is skipped as before.
   - A text naming none of them that names exactly one other catalogued craft by a name, alias or
     spelling (`craft_matching.named_craft_ids`, the resolver's exact match) goes to that craft;
     naming several, it is skipped. Other crafts are not named by a single word of their names:
     "blue" would name Blue Pottery of Jaipur in a sentence about a cobalt glaze.
   - A text naming a place outside India or another culture is refused with the place in the
     reason; so is one naming no craft but a place of India (`names azamgarh but no craft of it`).
   - A fact naming no craft and no place, in chemistry, physics or materials, goes to the craft
     family's science: no craft, and the shared concept named as the family's category, of the type
     `curation_keys.DISCIPLINE_CONCEPT_TYPES` gives the field, which is where a category's
     contributed facts are written and what a craft's scope reads (decision 0122). In a comparison
     this needs every compared craft in one category. Any other fact naming no craft is skipped.
   - A sentence resting on field interviews alone stays with the craft researched: the speaker's
     own practice, which the field-voice rule already limits.
   - Research for no craft files its facts on shared concepts as before.
4. **Places outside India are a hand-kept list.** `data/places_abroad.json` lists the United
   Nations' member and observer states but India, with Taiwan and Kosovo, under their English short
   names and adjectives, with the regions and cultures craft literature names (Khorezm, Jingdezhen,
   Delft, Ottoman ...), and the other senses in which a place word names a material or a sea (china
   clay, Turkey red, German silver, the Arabian Sea), inside which it names no place. Words with a
   common Indian sense are left out, each with its reason in the file (English, Mali, Tonga, Bali,
   Polish, Tibet, Sindh). The loader refuses India, a name shorter than four letters, a name listed
   twice, and an other sense holding no listed place word.
5. **Every refusal leaves a reason.** A refused sentence is in the write-back's `skipped` list with
   its reason, as gate refusals are, and `store_live_research` logs each skipped sentence with the
   answer it came from. The other gates are unchanged.
6. **An answer records its cost and latency.** `AnswerAsk.asked_at` is set when the question is
   received. `SqlAnswerStore.finish(..., asked_at=...)` writes `latencyMs`, from then to the finish,
   and `costUsd`, the summed `UsageEvent.costUsd` of the request id the answer ran under
   (`services/answer_cost`): the HTTP request's for the API's stream, the per-question tag for the
   evaluation, so both paths record both. Outside a request id the cost is not recorded and a
   warning says so. `services/` cannot import `providers/`, so the sum is a query of its own over
   `UsageEvent`, by the exact request id, not the router's prefix spend with its reservations.

## Consequences

- No migration and no stored fact changes: the 19 Khurja facts stay in the review queue for a
  person; the rule applies to write-backs from now on.
- Fewer facts are written under a craft. A craft-specific process or history sentence that names
  neither the craft nor its place, and whose quotes do not either, is refused rather than filed:
  research for a craft with few facts adds fewer of them. Sources about a craft usually name it, so
  the quote rescues most.
- Family-science facts carry no craft, so their dedupe key and their duplicate and novelty gates
  are those of shared knowledge: the same general sentence found for two families is one fact,
  filed under the first family's concept, and it is compared with every shared fact rather than
  its family's alone.
- A quote id (`citation_id`, a curated `claim_source_id`) changes only for a quote that contained
  the removed bytes; curated quotes never do, since curation reads through `clean_untrusted_text`.
- `store_live_research` and `SqlAnswerStore` need the process's `CraftIndexStore`; the coverage job
  makes its own.
- The cost is what was settled when the answer finished: work that outlives it (a builder still
  running) is not in it.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/research/test_storable.py`,
`backend/tests/db/test_storable_text_db.py`, `backend/tests/write_back/test_write_back_names.py`,
`backend/tests/write_back/test_write_back_filing.py`, `backend/tests/answering/test_answer_cost.py`
and `backend/tests/db/test_answer_cost_db.py`.
