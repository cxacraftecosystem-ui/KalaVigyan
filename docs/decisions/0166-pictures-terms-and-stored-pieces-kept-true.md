# 0166. Pictures are paired by the Public Suffix List and reused once stored, local words are terms only with a stated meaning, and stored vectors are compared within one model

A web picture's page and image are paired by the Public Suffix List; Brave's image results back
SearXNG's; a section shows the pictures already stored for its claims before it searches; the
stored-only answer marks terms and shows pictures, and the nightly rebuild searches none; the
glossary seed removes what its plan no longer makes, a local word is a term only with a meaning a
source states word for word, and a researched term summary is renewed after half a year; image and
term vocabularies stay check constraints; knowledge pieces carry their embedding stamp, and every
stored vector is compared only with vectors of the current model.

Date: 2026-11-23. Status: accepted (the lead's debt-clearing brief of 2026-11-23, pictures, terms
and planning lane). It amends [decision 0034](0034-images-and-terms.md) (the image sources, the
registrable-name test and the glossary), [decision 0039](0039-pictures-and-terms-wired.md) (where an
answer's pictures come from) and [decision 0008](0008-stored-knowledge-retrieval.md) (the stamps).
The contracts are `docs/contracts/explainer.md` (Pictures and terms as served, `Term`),
`docs/contracts/research.md` (coverage, the stored-only answer) and `docs/contracts/retrieval.md`
(Stamps, Embedding runs).

| For | Read |
|---|---|
| The pictures and terms it amends | [decision 0034](0034-images-and-terms.md) |
| The stream wiring it amends | [decision 0039](0039-pictures-and-terms-wired.md) |
| The stamps it extends to pieces | [decision 0008](0008-stored-knowledge-retrieval.md) |
| The vocabulary pattern it keeps | [decision 0033](0033-knowledge-pieces-and-reuse.md) |
| The per-answer cost it must not raise | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| Stored pictures read before the search's sources are built (amends item 3) | [decision 0175](0175-production-checks-read-what-the-page-shows.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Twenty-three entries of `docs/TECH_DEBT.md` were handed to this lane. The owner's rules for the
round bind it: no AI imagery as a reader's picture, pictures are credited plates, a field voice's
picture is never shown before a person reviews it, and no fix may add to an answer's model calls or
input tokens while answers are measured against Opus and Sonnet (decision 0165). Reading the code
showed that a picture's site was judged by twelve second-level labels, that every answer section
searched the image services even when the pictures chosen for the same claims were stored, that the
glossary seed and the term cache only ever grew, and that piece vectors carried no model.

## Decision

1. **The Public Suffix List decides a site.** `research/public_suffixes` reads a vendored snapshot
   of the list (`research/public_suffix_list.dat`, ICANN and private sections, wildcards and
   exceptions), and `images.site_of` returns the registrable name by it. We chose a vendored file
   over `tldextract` or `tld`: no new dependency, a dated copy we replace whole, and the private
   section makes `alpha.blogspot.com` and `beta.blogspot.com` two sites, so the test fails closed.
2. **Brave backs SearXNG for pictures.** `BraveAdapter.images` reads `/res/v1/images/search` as
   link cards under the same rule as SearXNG (the image the page's own site serves, never Brave's
   proxied thumbnail). `WebImages` asks Brave only when SearXNG finds fewer than two cards or
   fails, for an answer's sections (`LiveSourcesStore.web_images`). It is a search, not a model
   call.
3. **Stored pictures first.** A section shows the pictures stored for its cited claims
   (`MediaRefClaim`, both displays) by the caps a search uses, and searches only when none is
   stored. A stored picture is current while its claim is visible, it is not a field photo nobody
   has reviewed, and it passes today's shop and social rule; we chose these over an age limit,
   since a picture's licence and page do not age with the answer. Curated plates of a claim are
   shown before a search could find a weaker one.
4. **Every answer path marks and shows alike.** The stored-only answer of a refused spend marks
   its prose and shows its claims' pictures; the nightly piece rebuild keeps the term marking its
   pieces store and searches no picture (`section_enrichment.without_pictures`).
5. **The glossary seed removes what it no longer plans.** It deletes links its plan no longer
   makes to crafts without a curated page and to seed concepts, and the terms those deletions
   leave with no link, no shared-term row and no cached summary. Links of curated pages and
   contributors' structures are the curated import's.
6. **A local word is a term only with a stated meaning.** `data/local_term_meanings.json` lists
   each meaning with the words that state it, found in a seed claim of the word's concept or in a
   quote of a named curated claim; the seed refuses a row it cannot find. We chose a checked table
   over reading meanings out of brackets: the bracket reading gave `rang` "stage" and `fara`
   "folded", which would be invented facts.
7. **A researched summary is renewed after 180 days.** A `WIKIPEDIA` or `WEB_SEARCH` summary is
   built again on the next signed-in tap; a `STORED` one is dated by its claims and rebuilt by the
   curated import, so its age alone never sends a tap to research.
8. **Vocabularies stay check constraints.** `MediaRef.display`, `MediaRefClaim.relevance` and
   `TermSummary.basis` keep their `CHECK` constraints (decision 0033's pattern, 28 model files):
   a value is added or dropped by swapping one constraint, which the release before reads as text,
   while a Postgres enum label may be added only after a release that reads it has shipped and is
   never dropped without recreating the type (`docs/contracts/infra.md`).
9. **Stored vectors are compared within one model.** `KnowledgePiece.embeddingModel` (migration
   `0089_piece_embedding_stamps`) is stamped by every embedding run, stored vectors took the
   route's stamp, and a piece of another stamp is embedded again. The piece store's reuse distance
   and the candidate gates' neighbour search read only vectors whose model is the route's.
10. **One embedding call for a question's coverage.** The facets' targets are embedded together
    through the answer's embeddings cache before their searches run.
11. **A translated term is found as a whole word.** A span moves to the term's rendering or to one
    of the glossary's names for it (any script) only where no letter, mark or digit stands beside
    it, so a Devanagari vowel sign never ends a word (`research/terms.shown_as_word`); we chose
    Unicode categories over `re` word boundaries, which treat a vowel sign as a boundary.
12. **No vision call in an answer.** A picture is still chosen by its words; a `CAPTION` call on
    the top two candidates of every section would add two model calls and their image tokens to
    every answer, which the owner's rule of this round forbids. The entry stays, waiting on the
    owner's choice after the Opus and Sonnet measurement.

## Consequences

- Migration `0089_piece_embedding_stamps` adds one nullable column; the release before reads and
  writes under it.
- An answer makes no more model calls and reads no more input tokens; its embedding calls for
  coverage fall from one per facet to one, and a section whose claims have stored pictures makes
  no image search.
- The release controls open the saved Kutch Ajrakh answer and check every picture's credit and an
  underlined term's sheet; a term without a kept summary is researched once on that tap.
- Seed sources keep an organisation author whole; `seed_claims.json` and the goldens built from
  it take the whole names when the seed is next converted, and the seed then restamps the stored
  sources' authors.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/research/test_public_suffixes.py`,
`backend/tests/sources/test_brave_images.py`, `backend/tests/images/test_section_images.py`,
`backend/tests/answering/test_stored_only_enrichment.py`, `backend/tests/answering/test_rebuild_pictures.py`,
`backend/tests/terms/test_local_term_meanings.py`, `backend/tests/terms/test_term_summary_age.py`,
`backend/tests/db/test_glossary_seed_removal_db.py`, `backend/tests/db/test_embedding_stamp_neighbours_db.py`,
`backend/tests/retrieval/test_prepared_embeddings.py`, `backend/tests/terms/test_script_word_spans.py` and
`etl/crafts/tests/test_source_authors.py`.
