# 0013. Quote strength, open licences, one craft scope and scoped embedding

A review of the answer stream tightened its checks: a quote is at least 20 characters after folding,
matches whole words and whole numbers, and the sentence it supports carries its wording. Full text
is public only under an allow-listed open licence, a craft's claims have one home, a write-back
embeds only what it wrote, and untrusted text stays inside its blocks.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The lanes it reviewed | [0012](0012-answer-stream-end-to-end.md) |
| The figure check reads quantities, number words and element formulas | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| Every decision, by group | [README.md](README.md) |

## Context

A review of the answer stream (decision 0012) found that the citation checks could be passed by
quotes that carried no meaning: a one-letter quote, or a number cut out of a larger number. It
also found five other problems. Full text could be stored for every student under a licence
that did not allow it. The rule for which claims belong to a craft lived in two places. Each
write-back embedded the whole backlog inside the learner's request. A spend-cap refusal raised
while finding the craft was hidden. Text from users and synced portals sat outside the
untrusted blocks of model prompts. PLAN section 0 asks for accuracy over speed and a citation on
every sentence. The practice skills ask for one home per rule and for guards that fail closed.

## Decision

1. **A quote is at least 20 characters after folding** (`research/quotes.QUOTE_MIN_CHARS`,
   `trivial_quote`). `QuotedSpan.text` enforces it on the raw text. The compose schema sets
   `minLength` from the same constant. `sentence_violations` refuses a quote whose folded text is
   shorter (`TRIVIAL_QUOTE`), which catches padding such as soft hyphens. The write-back plan
   does not let such a quote pass. A short quote is reported as `MALFORMED` and regenerated
   once, like any other broken sentence. A stored claim shorter than 20 characters can still be
   cited by quoting a longer passage of its source.
2. **A quote matches on whole words and whole numbers.** `quote_occurs` requires the quote to
   start and end on a word boundary when its edge is a letter or digit, and never inside a
   decimal (`1` does not match `1.5`). So `50` cannot verify against `1500`, and `500 °C` cannot
   verify against `1500 °C`. Every figure check reads only verified quotes, so a quote's numbers
   are then whole numbers in the source.
3. **A sentence must carry its quotes' wording** (`quote_overlap`, `QUOTE_OVERLAP_MIN` 0.5). At
   least half of the sentence's content words must appear in its verified quotes. Content words
   are runs of four or more letters that are not in a short stop list, compared by their first
   four letters, so plurals and simple verb forms match. A sentence below the threshold is
   `UNRELATED_QUOTE`. A sentence with no content words fails it, which is the closed choice.
   This check assumes the answer and its sources share a language. English is the only answer
   language today (item 7). A second language needs a translated comparison first, which is
   recorded in `docs/TECH_DEBT.md`.
4. **Full text is public only under an allow-listed open licence** (`research/licences.
   open_licence`). The allow-list holds CC0, CC BY, CC BY-SA, PDDL, the public-domain mark and
   their Wikimedia and Wikidata spellings, matched by short name or canonical URL. Everything
   else is closed. That includes publisher text-and-data-mining URLs, `publisher-specific-oa`,
   `implied-oa`, `other-oa`, NC and ND licences, and an empty value. A licence that a T4 web
   page declares about itself is never trusted (`live_source_store.
   SELF_DECLARED_LICENCE_TIERS`). Closed full text is stored with the `RESEARCHER` chunk ACL.
   An open-access copy carries only the licence its locator reports. It no longer inherits the
   licence of the metadata record (`planner/reading.py`), because a bronze copy has no licence.
   Abstracts and short excerpts stay `PUBLIC`: services such as Crossref publish them for
   display, and a learner sees them only as quoted passages.
5. **One home for a craft's claims** (`retrieval/statements.scope_claims` and
   `claim_conditions`). Verified answers and the craft profile now use the same conditions as
   the Hybrid and Deep T1 search. The profile shows the claims Hybrid may cite
   (`knowledge_view.PROFILE_MODE`). Stored answers rank with the same OR text query and
   `ts_rank_cd` as T1 (`statements.text_query`, `lexical_rank`). They do not use a vector,
   because a Verified answer makes no model call.
6. **A write-back embeds only what it wrote** (`retrieval/indexing.embed_written`). It embeds
   the claims it wrote or matched and the chunks of the documents it kept. When embedding fails
   after the commit, the answer still completes: the failure is logged, and
   `StoredResearch.embedding_error` holds it. The rows wait for `embed_knowledge`, which the
   daily Coverage enrichment workflow now runs before it enriches. The backlog is therefore
   never paid for by a learner's request.
7. **Untrusted text stays inside untrusted blocks.** The craft name and slug go in one block
   (`research/crafts.craft_block`) for both the planner and the composer. The answer language
   is checked at the API boundary against `research/vocabulary.ANSWER_LANGUAGES`, the same list
   that `/answers/config` offers. A regenerate request names only the problem kinds outside the
   blocks. The section heading, the problem details and the failed sentence go in the failed
   sentence's block.
8. **A spend-cap refusal while finding the craft is shown in the router's words.** This is the
   same rule as for research (decision 0012). `NOT_FOUND_DETAIL` is defined once, in
   `services/answering`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
