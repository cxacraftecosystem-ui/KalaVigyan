# 0121. A quote is shown only where its page allows

A citation's quote is read under its page's access, never more openly because no passage was linked
to it. A quote whose check failed is never shown as the source's words, a fact whose every quote
failed stays out of answers, re-reading a source never moves or hides what earlier citations rest on,
and a vector is never stored for a text that changed while it was being made.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21, on the audit of the answer pipeline: "yes, run
all five lanes"). The contracts are `docs/contracts/retrieval.md` (Who may read a citation, The
passage that holds a quote, Re-reading a source, Stamps), `docs/contracts/knowledge-writes.md`
(Citations and their passages), `docs/contracts/open-data.md` and `docs/contracts/nightly-upkeep.md`
(1a).

| For | Read |
|---|---|
| The rules as they stand | [retrieval.md](../contracts/retrieval.md), Who may read a citation and Re-reading a source |
| How a quote is linked when a fact is written | [knowledge-writes.md](../contracts/knowledge-writes.md), Citations and their passages |
| What a held fact is and how it heals | [nightly-upkeep.md](../contracts/nightly-upkeep.md), 1a |
| What the open data leaves out | [open-data.md](../contracts/open-data.md) and [decision 0116](0116-open-data-with-a-doi.md) |
| A fact whose quotes are closed stays for every reader, unquoted, and one rule names the facts a reader sees (amends items 1 and 6 and the open-data consequence) | [decision 0149](0149-a-fact-readers-can-see.md) |
| Every decision, by group | [README.md](README.md) |

## Context

A page fetched under a closed licence is stored as passages for researchers only, and a quote linked
to such a passage is shown to researchers only. Four faults let a quote out, or kept a dead one in:

- A citation with no linked passage counted as public: `readable_citations` and the open-data export
  read `chunkId IS NULL` as readable. Quotes went unlinked whenever no single passage held them: a
  250-character quote across two long paragraphs (the chunker carries the last paragraph over only
  when it is 300 characters or less), a word broken by a hyphen at a line end (the chunker kept
  `mor- dant`, the matcher reads `mordant`), and every new quote of a curated source, whose seed
  passages were kept when its full text was read. So a quote of an "all rights reserved" page reached
  craft pages, the Knowledge API and the open data. A stored answer read publicly was redacted per
  fact and source, so a closed quote that shared both with a public one stayed.
- Re-reading a source rewrote its passages by position under the new reading's access while
  citations kept their old passage and locator. A public abstract quote became researcher-only when
  the paper's full text arrived with no licence, and an edited page left citations pointing at text
  that no longer held their quote.
- A held fact (every quote failed the nightly check) left pages but not search or the views answers
  are built from, and every stored quote was labelled verbatim whatever its check said.
- An embedding run wrote the vector without checking that the text was still the text it embedded,
  so a text rewritten during the call kept the old text's vector, stamped current.

## Decision

1. **A citation follows its page, read at query time.** `retrieval/citation_access.readable_citation`
   is the one rule for every view, the open-data export and the re-reading: a linked citation follows
   its passage; an unquoted one is readable (it shows no words); an unlinked quote takes the most
   closed passage of its source and the source's own sensitivity. No column was added and no
   migration was needed: the rule reads the passages the source already has. A source with no
   passages (a book cited by page, a supplied source) shows its short quotes as before.
2. **Quotes are linked better.** A quote is linked to the first passage that holds it, else to two
   neighbouring passages of the same access (to the first, with both paragraphs as its locator), and
   the chunker joins line-end hyphens as the quote matcher does.
3. **A curated source read in full takes its full text.** `keep_document` replaces any source's
   passages when its full text is read, not only a live-research source's, so a new quote of a closed
   page is linked to a closed passage.
4. **Re-reading re-links and never hides.** After rewriting, every quoted citation of the source is
   re-linked to the passage that holds its quote, its locator following unless it carries its own. A
   citation everyone could read before, whose quote has not failed, keeps a public passage of exactly
   its quote when its new passage is closed or none holds it, as the seed import keeps its quotes.
   This keeps the citation public without making the closed text around it public: the words were
   already shown.
5. **A stored answer is redacted per citation.** A quoted citation is kept publicly only when a
   readable citation of the same fact and source carries the same quote.
6. **Held facts leave answers; contributors still read them.** Search leaves a held fact out in
   every mode (`claim_conditions(..., held=HELD_LEFT_OUT)` by default), and so do `claims_for` and
   `claims_by_id`, the views answers, pages, component checks and public readings are built from.
   Every answer mode is read by readers (the site, MCP `ask`, voice), so none keeps them. A
   contributor re-sources a held fact from `knowledge_view.contributor_claims_for`
   (`held=HELD_KEPT`), where it shows with its failed quotes unquoted. The rule of 2026-11-20 that
   "answers and the Knowledge API's reads still find it" is withdrawn for answers.
7. **A failed quote is never verbatim.** A view drops the words of a citation whose last check is
   `FAIL` and labels it `INFERRED`; the citation and its source stay.
8. **Vectors are written only on unchanged text.** The embedding run's `UPDATE` compares the text
   (or a piece's payload) with what it read; a changed row keeps no vector and is not counted.

## Consequences

- A quote that was public only because it was unlinked becomes researcher-only on the first read
  after this change, with no data written. This includes a curated quote of a source for which live
  research or a contributor had already stored a closed full text before this change; such a quote
  returns to public pages when its source is read again (decision item 4) or a curator links it.
- Facts held by the night leave answers, coverage counts in research planning, the saved-answer
  re-check and stored answers read publicly, as they already left pages.
- Until the Knowledge API's `get_facts` reads through `contributor_claims_for`, a contributor finds a
  held fact by the ids of its `RESOURCE_FACT` task and through the review queue, not in `get_facts`.
- The media claim set still counts an unlinked citation as visible to the asker (`app/media/rows.py`,
  `app/media/claim_set.py`, `docs/contracts/media.md`); it moves to this rule in a later change.
- `services/claim_holds.held_claim` and `retrieval/citation_access.held_claim` state the same rule
  in two layers; the services one should call the retrieval one.
- Re-reading a source stores a short public passage per public quote whose page is now closed; these
  are searched like any passage and embedded on the next run.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/db/test_quote_visibility_db.py`,
`backend/tests/db/test_quote_relinks_db.py`, `backend/tests/db/test_open_data_db.py`,
`backend/tests/retrieval/test_statements.py`, `backend/tests/retrieval/test_quote_passages.py`,
`backend/tests/retrieval/test_chunking.py` and `backend/tests/learning/test_share_links.py`.
