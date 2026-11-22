# 0149. A fact is shown to every reader with its citation, and only its quote follows its page

A published fact whose sources have no open licence is shown to every reader with its citation
and no quote, one rule says which facts a reader can see and every count and view reads it, the
proposal reply says where a reader sees the fact or why not, a field's facts no section cites are
listed in its chapter, the gate judges answer in parts the verdict is worked out from and are
scored every night, and the night counts what the read rules hide.

Date: 2026-11-23. Status: accepted (the lead's round 7 brief, contributions-visible lane, on the
owner's report of 2026-11-22: sixteen Sanganeri facts contributed through Claude were "Published,
approved" and no reader could see them). It amends
[decision 0121](0121-quote-visibility.md), items 1 and 6 and its open-data consequence;
[decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15's gates 1, 3 and 4 and
its sources-differ rule; and [decision 0116](0116-open-data-with-a-doi.md), what the export leaves
out. The contracts are `docs/contracts/retrieval.md` (A fact a reader can see; Who may read a
citation), `docs/contracts/knowledge-writes.md` (The gates, in order; Routes), `docs/contracts/open-data.md`,
`docs/contracts/nightly-upkeep.md` (step 5d) and `docs/contracts/monograph-document.md` (Facts no
section cites).

| For | Read |
|---|---|
| The quote rule it keeps and the fact rule it changes | [decision 0121](0121-quote-visibility.md) |
| The gates whose judges it makes structural | [decision 0101](0101-knowledge-architecture-for-every-craft.md), item 15 |
| What the open data releases | [decision 0116](0116-open-data-with-a-doi.md) and [open-data.md](../contracts/open-data.md) |
| The rule as it stands | [retrieval.md](../contracts/retrieval.md), Who may read a citation |
| The reply, the gates and their evaluation | [knowledge-writes.md](../contracts/knowledge-writes.md) |
| The nightly count | [nightly-upkeep.md](../contracts/nightly-upkeep.md) |
| Every decision, by group | [README.md](README.md) |

## Context

On 2026-11-22 the owner asked Claude, over the KalaVigyan MCP server, to fill Sanganeri Hand Block
Printing's missing fields. Sixteen facts passed every gate and the server replied "Published,
approved". No reader could see one of them:

- Every source had no open licence, so every quote sat on a researcher-only passage.
  `knowledge_view._cited_views` kept a claim only when one of its citations was readable at the
  reader's access, so the page, `get_facts` and answers dropped every fact, while coverage, which
  counted any citation of a visible source, counted all sixteen. Decision 0121 meant to hide a
  closed page's words, not the fact, which is KalaVigyan's own sentence.
- Health, Climate and Physics had no written section, and the generated page draws sections only.
- The reply said "Published, approved"; the contributor's AI told the owner the facts were on the
  page.
- The novelty judge refused the Indigofera tinctoria fact with `adds: false` while its own reason
  said the details were new; the duplicate judge marked five compatible pairs as sources differ;
  the quotes gate refused "2014" though 2014 was the cited study's own year; and a source was
  stored with the title "aa.MDI", its PDF's metadata.

Nothing caught it: each guard fails closed, so over-hiding is silent, and no check followed a
contribution from MCP to a signed-out reader.

## Decision

1. **A fact follows its sources' visibility; a quote follows its page.** A reader sees a fact that
   is shown (`PROPOSED`, `IN_REVIEW`, `APPROVED`), not restricted, filed under a concept readers
   see, cited by at least one source that is not restricted and not a withheld field recording,
   and not held. Its every such citation is shown, with its source and locator; its quote only
   when `readable_citation` lets this reader read the passage (decision 0121 item 1, unchanged),
   otherwise unquoted and labelled `INFERRED`, as a failed quote already was. A view carries the
   ids of the citations whose words it hid (`ClaimView.closed`), so stored pieces built with those
   words are not reused for this reader.
2. **One home.** `retrieval/citation_access.reader_fact()` is that rule. Search
   (`statements.claim_conditions`, which narrows the statuses by mode), the views
   (`knowledge_view.claims_by_id`, `claims_for`), coverage and the field tasks
   (`open_work_counts.owned_facts`), the open data (`open_data_claims._published`), the reply
   (`reader_facts.shown_to_readers`), the generated page's fact lists and the nightly count read it,
   and `reader_citations` reads a fact's citations with whether their words are readable. Coverage
   still counts fact levels only; a hypothesis is shown apart.
3. **The open data releases the fact.** A published fact citing a source readers may see is
   released with its citation row; the row never carried a quote's words, and still does not.
4. **The reply says where readers see a fact.** A passed proposal's reply carries
   `readers {shown, reason, pageUrl, chapter, field, inProse, writeTask}` and its message says
   "Readers see it now at …" with the page, the field and the open write-section task, or
   "Readers cannot see it yet: …" with the rule that hides it. A fact the queue worker publishes
   refreshes its craft page, as the REST route's already did.
5. **A field's facts no section cites are listed in its chapter.** The generated page lists, after
   a field's written sentences (or under the field's heading when it has none), up to twelve of
   the field's facts no section or curated structure of the page cites, each a list item carrying its claim and its
   citations (`craft_page_unwritten`). The web client draws list items already.
6. **Judges answer in parts.** The duplicate judge answers, per pair, whether the two say the same,
   speak of the same thing, property and stage or time, and can both be true, and names the two
   values; a pair differs only when it is one question with two different values that cannot both
   be true. The novelty judge lists the new details and says whether the fact is specific to the
   craft; it adds exactly when the list is not empty and it is specific. No model returns a verdict
   beside its reason any more in the gates; the other model booleans (picture screens, the miss
   judge, simulations, drafting) are findings, not verdicts with reasons, and are left.
7. **A source's own date passes the quotes gate.** A statement may give its cited source's
   publication year, or its full date written day.month.year, without a quote holding it; any
   other figure still needs one.
8. **A file name is never a source's title.** A title that is a file name or has fewer than three
   words of letters gives way to the contributor's title, then the document's first heading; a
   source with none of them is refused by the source gate, asking for the work's title. A stored
   source with such a title takes the next proposal's usable title.
9. **The judges are measured.** `app/data/eval/judge_cases.json` holds 13 labelled pairs (8
   DISTINCT, the five Sanganeri pairs among them; 3 DIFFERS; 2 SAME) and 7 labelled candidates (4
   that add, the Indigofera fact among them; 3 that do not). `app.scripts.eval_judges` asks the live
   judges as the queue does (cheapest first) and `.github/workflows/judge-eval.yml` runs it every
   night at 01:37 UTC, failing below the floors: duplicate accuracy 0.80, compatible pairs kept
   DISTINCT 0.85, novelty accuracy 0.80. They are provisional until the first live run; the lead
   re-bases them then, as decision 0133 did for answers.
10. **The night counts what the rules hide.** Nightly upkeep counts, per craft, the approved facts a
    signed-out reader cannot see, by reason (`HELD`, `RESTRICTED_FACT`, `HIDDEN_CONCEPT`,
    `NO_SHOWN_SOURCE`), and the approved facts the rule shows but a reader's view leaves out
    (`unexplained`). It stores the report for admins (`GET /api/coverage/hidden-facts`) and the
    night's `ok` is false when any fact is unexplained.
11. **A release proves the round trip.** After every served release, a Professor's MCP client
    proposes a marked test fact quoting a page with no open licence, and the run fails unless
    `get_facts`, the field's coverage count and the craft page show it to a signed-out reader,
    unquoted; the Professor then retracts it and the run checks it is gone.
12. **Voice reads at the reader's access.** A voice pack is loaded and kept per reader access, so a
    student's turn never carries a researcher-only quote.

## Consequences

- Facts that were hidden only because their quotes sat on closed passages appear on pages,
  in `get_facts`, answers, the open data and voice on the first read after this change, unquoted.
  No data is written.
- The five pairs flagged on 2026-11-22 were cleared by hand; `app.scripts.rejudge_differing`
  re-judges every live flagged pair with the new comparison and writes nothing.
- The stored "aa.MDI" title is repaired by the next proposal citing the study, or by
  `app.scripts.retitle_sources --set <id> --title "<title>"`, which records an audit row.
- The authored Kutch Ajrakh page does not list unwritten facts; its chapters are written by hand.
- The hidden-facts report has an admin route and no screen yet (`docs/TECH_DEBT.md`).
- A stored answer read publicly still drops a quoted citation whose quote is closed (decision 0121
  item 5); a sentence whose only citation was such a quote leaves the public reading.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/retrieval/test_citation_access.py`, `backend/tests/db/test_reader_facts_db.py`,
`backend/tests/db/test_quote_visibility_db.py`, `backend/tests/db/test_open_data_db.py`,
`backend/tests/db/test_voice_store_db.py`, `backend/tests/voice/test_pack_access.py`,
`backend/tests/db/test_unwritten_facts_db.py`, `backend/tests/knowledge_writes/test_structural_verdicts.py`,
`backend/tests/knowledge_writes/test_dates_and_titles.py`, `backend/tests/knowledge_writes/test_judge_eval.py`,
`backend/tests/knowledge_writes/test_differ_rejudge.py` and `frontend/e2e/release/mcp-contribution-unit.spec.ts`,
and run live by `frontend/e2e/release/mcp-contribution.spec.ts` and `.github/workflows/judge-eval.yml`.
