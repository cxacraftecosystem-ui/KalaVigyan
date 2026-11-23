# 0034. Pictures and tappable terms

Explainer sections show pictures from the web through one adapter per service, inline or as a link
card by one rule, chosen by their relevance to the claim text. Terms are marked on the server and
open short cited summaries.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Sites are judged by the Public Suffix List, Brave backs SearXNG, and local words are terms only with a stated meaning | [decision 0166](0166-pictures-terms-and-stored-pieces-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase A of `docs/plans/answer-experience.md` (sections 2.7 and 2.8, owner decisions of
2026-11-17) adds pictures from the web to an explainer section and underlined terms that open a
short cited summary. Decision 0030 fixed the shapes (`MediaRef`, `ImageItem`, `ImagesBlock`,
`TermSpan`, `Term`) and left the adapters, tables, selection rules, the term route and the image
hosts in the CSP to this lane. Owner O2 settled that web pictures without an open licence are
credited link cards whose thumbnail loads from the source site and opens the source page.

## Decision

1. **One adapter per service.** Commons pictures are an `images` method on the existing
   `WikimediaCommonsAdapter` (its home): the file page, the 960-pixel thumbnail, the original's
   size, author and licence from `extmetadata`, `utm_` parameters dropped. Openverse is a new
   adapter in `sources/images/` that asks only for `by`, `by-sa`, `cc0` and `pdm` and still drops
   anything off the open allow-list, marked mature, or without a creator to credit. SearXNG web
   pictures are an `images` method on `SearxngAdapter` (`categories=images`). All three return
   `research/images.ImageCandidate` and meet the `ImageSource` protocol;
   `sources/images/registry.image_sources` builds them on the live sources' client
   (`LiveSourcesStore.images()`). Brave image search is left for later (debt).
2. **Inline or link card is one rule.** `research/images.media_ref_of` makes a picture inline
   only under an open licence (`licences.open_licence` of its name or URL) with its author, which
   is the `MediaRef` contract's own check; every other picture is a link card. SearXNG results
   carry no licence, so they are always link cards.
3. **The thumbnail comes from the source site.** A SearXNG result is kept only when its
   `img_src` and its page share a registrable name (`collections.vam.ac.uk` and
   `framemark.vam.ac.uk`), never the search engine's thumbnail proxy (`thumbnail_src`), and never
   over plain http. That is O2 read literally: the reader's browser loads the picture from the
   site credited on the card. The registrable name is a short heuristic (two labels, three under
   a two-letter country code with `ac`, `co`, `gov`, `org` and similar); IP addresses and single
   labels are refused. The Public Suffix List would be exact (debt).
4. **Relevance against the claim text.** The section's other blocks cite claims; a picture
   illustrates the claims whose content stems (`research/quotes.content_stems`, the composer's
   own overlap measure) it shares at least two of, with the words of the craft name left out,
   because every result of a craft search carries them. A section shows at most four pictures,
   inline first, at most two link cards, each original image once (Openverse often returns
   Commons files). The search text is the craft name and the two content words most shared by
   the section's claims, then the craft name alone when that finds nothing; a failing service
   leaves the others to answer. Relevance is `TEXT`; the vision check of plan 2.7 is debt.
5. **Stored pictures.** `MediaRef` holds each picture once, keyed by the SHA-256 of provider,
   page and image URL (`urlKey`, since two 2048-character URLs exceed a btree key) with an id
   derived from it, the stored `Source` when the page is one, and `MediaRefClaim` links to the
   claims it illustrates with their relevance, so the craft page can find a craft's pictures.
6. **Terms.** The `Term` glossary is seeded on every deploy by `seed_claims` (after the claims and
   the science seed): every craft name with its active aliases (Latin spellings to find it in
   text, other scripts as local names), the matched Wikidata item, its description as the term's
   meaning and its labels in other languages, and its tradition concepts; the seed's materials,
   tools and stages whose names state what a local word means (`Kut (iron-water black paste)` is
   the term `kut` meaning "iron-water black paste"; `Alum (fatakdi)` is `alum` with the local name
   `fatakdi`); plain material names; and the science seed's compounds through the materials that
   use them. Terms merge by `term_key`, and only terms of at least one craft are kept, because
   what is found for a term is stored as claims of a craft's concept. The meaning is never shown:
   it narrows the searches and the summary prompt.
7. **Spans are server-side.** `research/term_marking.TermMarker` marks whole words, longest name
   first, each term once, only where the span's text first occurs in the sentence (the contract
   underlines the first occurrence), and never a name two terms share. `glossary_entries` gives
   an answer's crafts' terms without their own names. The model never chooses spans.
8. **Term summaries.** `GET /api/terms/{key}?language=` answers the `Term` contract for any
   signed-in reader, 60 lookups in 10 minutes except for Master Admins (no caps of any kind), and
   404 for an unknown term or one with no cited summary (the reader's screen hides it). A summary
   is cached per term and language in `TermSummary` and served while every claim it rests on is
   visible. Otherwise, in order: the defining stored claims of the term's concepts (the claim
   whose text is the concept's description; `STORED`, as decision 0030 put stored knowledge
   first); else the Wikipedia lead of the article whose Wikidata item is the term's, or whose
   title is one of its names or meaning (`WIKIPEDIA`, up to three verbatim sentences, each its own
   quote, checked by `composition.sentence_violations`); else one web search, up to two pages read
   through the fetcher and one `SUMMARISE` call (Gemini Flash Lite first, through the router as
   the reader) whose sentences must quote the pages and pass the composer's checks
   (`composer/term_summary`, the term and pages inside untrusted blocks). A summary with no
   passing sentence is refused. Pages and sentences found are kept as `LIVE_RESEARCH` sources and
   quoted `PROVISIONAL` claims of the term's concept (`BACKGROUND`), so the knowledge base grows
   and the summary cites stored claims like every other answer. Other languages translate the
   English summary through `answer_translation.translated_sentences`.
9. **SUMMARISE routes.** Migration `0012_images_and_terms` seeds the `SUMMARISE` task's routes
   (Gemini 3.5 Flash-Lite, Claude Haiku 5.5, GPT-6 Luna) and `DEFAULT_ROUTES` lists them, so the
   Settings hub can reorder them. The summary schema uses only `type`, `properties`, `required`,
   `additionalProperties` and `items`, which every route accepts.
10. **Check constraints, not new enum types.** `MediaRef.display`, `MediaRefClaim.relevance` and
    `TermSummary.basis` are strings with `CHECK` constraints built from the tuples, which now live
    in `models/enums.py` (`MEDIA_DISPLAYS`, `IMAGE_RELEVANCE`, `TERM_BASES`; `research` imports
    them, the client's vocabulary spec reads them there). The schema tests know only the enum
    types the first migration declares (debt).
11. **CSP.** `img-src` becomes `'self' data: <media bucket> https:`. Link-card thumbnails come
    from any source site (O2), so no host list could cover them; listing Commons and Openverse
    hosts besides `https:` would add nothing. Pictures cannot run script, plain http stays
    refused, and every component that draws a web picture's `imageUrl` must set
    `referrerPolicy="no-referrer"` (pinned by `e2e/picture-rules-unit.spec.ts`), so the source
    site learns nothing about the page that showed it. Links open the source page. Narrowed by
    decision 0038 until the stream sent pictures; decision 0039 restored it on every page when it
    wired them in.

## Consequences

- The answer stream calls `SectionImages.block` and `TermMarker` since decision 0039: spans on
  each English sentence of a section's blocks before translation, and an `images` block after
  them, bounded so that pictures never stop or hold a section for long.
- Tested on recorded responses (Commons, Openverse) and a hand-written SearXNG image answer; a
  recorded Commons picture reproduces the explainer fixture's inline `MediaRef`, and a stored
  claim reproduces the term fixture, byte for byte. Database tests for the glossary seed, the
  term store and the picture store run on GitHub Actions.
- New tables: `MediaRef`, `MediaRefClaim`, `Term`, `TermCraft`, `TermConcept`, `TermSummary`
  (row-level security on, public roles revoked).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
