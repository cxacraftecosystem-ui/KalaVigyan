# 0124. Live research writes back only what its sources say

Live research stores only what its sources say, filed under the right craft and field. It never
revives a fact reviewers closed, never lends one fact's citations to another sentence, reads long
documents instead of dropping them, and embeds only what it keeps.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21, on the audit of the answer pipeline: "is
there any other fault in our existing RAG pipeline?", then "yes, run all five lanes"). The
contracts are `docs/contracts/knowledge-writes.md` (The research write-back),
`docs/contracts/research.md` (the planner's reading, the composer's candidates and the write-back)
and `docs/contracts/coverage.md`.

| For | Read |
|---|---|
| The gates a written-back claim passes | [knowledge-writes.md](../contracts/knowledge-writes.md), The research write-back |
| The write-back, its key and the coverage job | [research.md](../contracts/research.md), Write-back of live research |
| How fields are counted | [coverage.md](../contracts/coverage.md) |
| A fact is filed under the craft it names, family science and places abroad (amends item 6) | [decision 0135](0135-write-backs-filed-under-the-craft-they-name.md) |
| A sentence citing a stored passage kept as a fact of its source, and the voice turn as a finder | [decision 0144](0144-stored-passages-as-evidence.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Four read-only reviewers audited the answer pipeline and the lead verified eight faults in how live
research is written back. The duplicate and novelty gates saw only open facts, and a write-back's
id came from the model's facet target, so a sentence a reviewer had rejected came back under
another target the next week. A sentence the gates refused was shown with the held fact's id, so
the reader saw the writer's wording with another fact's citations and its badge. A sentence the
composer had pooled from a stored fact and a live page was stored citing the page alone, and any
quote found in a document was marked as direct support for the whole sentence. Documents over 4,000
characters were offered to the writer only through reader quotes that no adapter sets, so most
pages and open-access papers were fetched, stored, embedded and dropped, and an author's manuscript
was cited as the published paper. A fact took its field from the first facet that found its
document, and in a comparison every sentence went to the leading craft. Every passage of every
document read was embedded before the section showed, though answers search only the chunks of
cited sources. A written-back sentence could carry personal data. The coverage job counted facts
by concept type while write-backs filed them by facet, and asked the same fruitless gaps every
seven days.

## Decision

1. **Closed facts stay closed.** A write-back whose id is a closed fact, or whose text is a closed
   fact's identical text or vector twin in any field of the subject, is refused at the duplicate
   gate with its reason, before any judge (`services/write_back_closed.py`). The statements are
   embedded once for this check and the later gates.
2. **The key is the fact, not the plan.** The dedupe key is `claim-write-back/v2`, craft, field and
   folded text (`research/write_back.claim_dedupe_key`). Old `v1` ids stay; the identical-text
   gate catches their twins.
3. **No borrowed citations.** A refused sentence keeps no claim; answers never cite a held fact
   under the writer's wording. Only a term summary, which shows a held fact's own text, still takes
   an identical held fact.
4. **Whole evidence or nothing.** A sentence citing a stored fact beside live evidence is not
   written back. A citation is `DIRECT` only when its own quote carries the sentence, and a claim
   is `QUOTED` only when its passing quotes together carry it.
5. **Long documents are read.** A long document without reader quotes offers the composer at most
   three passages chosen by the section's facet words weighted by their rarity, within the
   4,000-character budget, with no model call (`composer/passages.py`). The abstract is read beside
   an open published copy, and a submitted or accepted manuscript is cited as the copy read, with
   no DOI.
6. **The right field and craft.** A focused section's heading names its discipline; the claim takes
   that field and the cited facet of it. In a comparison a sentence naming one compared craft is
   filed under it and one naming two is skipped; the compared crafts are read from the answer's
   stored understanding. Claim writer and gates both use the field.
7. **Embed what is kept.** The answer path embeds the claims it wrote and the chunks of the sources
   they cite; the rest wait for the daily embedding run.
8. **No personal data, honest gaps, the right glossary entry.** A write-back's text is refused when
   it carries personal data. The coverage job counts by field and rests a question for 28 days
   after a run that added nothing to its field. A glossary term prefers the article whose title
   adds only words of the term's meaning ("Indigo dye" over the colour "Indigo"), and a term of
   several crafts is filed under the one owning its concept, else as shared knowledge.

## Consequences

- No migration: the new key is computed, the closed statuses are read, and a claim's field is
  stamped by the write-back after the claim writer inserts it.
- A reviewer's rejection now holds against research; the cost is one more twin query and one
  nearest query per written-back claim, both on indexed columns.
- An answer may lose a sentence the gates refuse rather than show it with borrowed citations; the
  answer drops such a sentence on its own, not its whole block.
- Composer prompts grow by at most three passages per long document; DEEP reads one more abstract
  per open copy, in parallel with the copy.
- Left for later changes: the claim writer could write the claim's field at insert
  (`services/claim_writer.py`), the section store could pass the section's discipline explicitly
  (`services/answer_sections.py`, `answer_store.py`), and the later gates could keep the duplicate
  judge's verdicts when the novelty judge fails (`services/candidate_gates.py`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/write_back/`,
`backend/tests/composer/test_passages.py`, `backend/tests/planner/test_research_run.py`,
`backend/tests/terms/test_term_filing.py`, `backend/tests/db/test_write_back_closed_db.py` and
`backend/tests/db/test_coverage_backoff_db.py`.
