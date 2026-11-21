# 0110. Sources a contributor's AI can read and we cannot, and a studio to build a page in

A contributor's AI may supply the text of a source KalaVigyan cannot read itself, which is graded,
checked by the gates against that text and kept privately, never republished. A draft workspace and
a preview an AI can judge let a contributor build a whole page in one guided flow.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "There is a greater maneuverability in the
MCP through the third party ai, it can get us access to better sources too and all, so add it to the
MCP as well, the MCP should be able to do all the research, the page curation, and the page preview
including uploading and all, it should be a miraculous experience in total"). Amends the sources
reference's "never used: anything behind a login" for text a contributor supplies under these rules;
the rest of decision 0101 (the gates, the review switch, trust tiers) stands.

| For | Read |
|---|---|
| What amended it | [0111 Twenty-one MCP tools in six groups, with small schemas](0111-fewer-mcp-tools.md): the tools it names; its services, allowances and contracts stand |
| What it amends | the sources reference's "never used: anything behind a login" ([sources.md](../../backend/app/data/contributor/references/sources.md)), for text a contributor supplies |
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): the gates, the review switch and trust tiers, which stand |
| Every decision, by group | [README.md](README.md) |

## Context

Every quote KalaVigyan publishes is re-found by its own fetcher. The best sources for a craft are often
out of the fetcher's reach: a paper behind a publisher's paywall, a monograph in print, a PDF a
researcher holds, a museum or state archive, a site that refuses automated reading. A contributor's AI
reaches many of them through the contributor's own subscription, library or bookshelf, but the QUOTES
gate refused every quote it could not fetch, so the best evidence never arrived. Building a whole page
also took one large `propose_page` call: an AI that researches over hours had nowhere to keep its work,
and `preview_page` returned a link but nothing it could judge without a browser.

## Decision

1. **Supplied sources.** `supply_source` (scope `contribute`, Researcher and above) takes a source's
   identity (DOI, ISBN or url, title, authors, year, publisher, kind, language), how it was read
   (`SUBSCRIPTION`, `INSTITUTION`, `OWN_COPY`, `ARCHIVE` or `BLOCKED_SITE`) and on which day, the
   source's own licence, and its words one way: passages with their locators (up to 60), the whole
   text (up to 200,000 characters, the fetcher's own limit), or a private upload slot for a PDF or a
   UTF-8 text file (20 MB, 30 minutes, single use, closed when the account's sessions end, like a
   picture slot). A PDF is read with pypdf in a worker thread, two at a time, at most 150 pages and the
   fetcher's 20 MB decompression limit; one without a text layer is refused.
2. **Identity and grade.** The title is looked up in OpenAlex, Crossref and Semantic Scholar, in that
   order, stopping at the first match: by DOI when one is given, otherwise by title (the same words, or
   one a prefix of the other from four words), year within one and a shared author surname. A
   confirmed work takes the index's grade by the rubric (a paper, book or chapter A; a thesis, report,
   preprint or dataset B; other C), and a work with no named author is never B. A work found nowhere is
   graded C when an author or publisher is named and D otherwise, so unconfirmed supplied text never
   carries a fact alone (the SOURCE gate refuses D-only facts). The cite url is `https://doi.org/<doi>`,
   else the canonical url, else `https://openlibrary.org/isbn/<isbn13>`.
3. **The gates read the supplied text.** When a proposer's fact, structure item or source proposal
   cites a url that the same proposer supplied (matched on the cite url, DOIs folded to lower case), the
   QUOTES gate reads the supplied text (every ready supply of that source by that proposer, joined by a
   pilcrow so no quote spans two passages) instead of fetching, and the SOURCE gate takes the supplied
   grade unless the source is already stored with its own. The QUOTES gate's reasons say the text was
   supplied, how and when it was read, and the supplied source's id, so the review queue shows it; a
   quote not in the text is refused as "not in the text supplied for it". Text supplied by one account is
   never used for another's quotes.
4. **Kept privately, never republished.** The supplied text is kept in `SuppliedSource` with its
   SHA-256 (and the file's), under row level security with no grants to the public roles, readable only
   by its supplier and by reviewers (`GET /api/knowledge/supplied-sources/{id}`, `private, no-store`,
   `noindex`). A fact that passes keeps its source as a link-only `Source` row with no chunks, so the
   text never enters retrieval, answers, exports or pages; readers see the short verbatim quote and its
   citation, as for every source. Quotes stay short (the 300-character limit) and cited; a whole text is
   never shown.
5. **Provenance and trust.** A fact resting on supplied text goes through the four gates and the review
   switch exactly as any other proposal: trust tiers apply unchanged, and its sources in the review queue
   carry `supplied {suppliedSourceId, access, accessedOn, grade, confirmedBy, textSha256, characters}`.
   Supplying a source counts against the hour's fact proposals, as a source proposal does; an account
   holds at most 300 supplied sources.
6. **A draft workspace.** `create_draft`, `add_to_draft`, `remove_from_draft`, `get_draft`,
   `preview_draft` and `submit_draft` keep one open draft per account and page (ten at once, 600 kB
   each, 14 days after the last change). A draft holds what a page bundle holds (facts, structure items,
   components and general-kind figures, the layout, pictures by contribution id or as new slots) plus
   supplied source ids and the page's own lists (mechanisms, ambiguous terms, the signature fact).
   Removing a fact renumbers the later `fact:N` references and refuses while a part still names it.
   Previews and submissions reuse `preview_page` and `propose_page` unchanged: a draft is a bundle
   built over many calls.
7. **A preview an AI can judge.** `preview_page` and `preview_draft` return, with the private link, a
   report of the assembled document against the page checklist: the 17 rules a machine can check pass or
   fail with their evidence (titles that are questions and a lede over three sentences, the masthead
   picture, every number in its quotes, the signature fact told once, each picture file once, every figure
   citing through its units, no progress state, credits under pictures, figures holding text, charts drawn
   to scale, mechanisms told in two sentences or more, elements conserved in each reaction, every field in
   its chapter and on the page, three sentences a field, no repeated sentence, no admitted gap), rule 18
   counts the sentences using each ambiguous term, and the 8 others are listed to judge on the link; a
   rule that needs the page's lists or formulas is left to judge until they are given. With it come
   coverage by field, figures and their kinds, sources by grade and pictures by licence. The rule titles are
   read from the checklist reference, its one copy. An
   MCP App (`ui://kalavigyan/page-preview.html`) draws the report in the chat in the design system's
   tokens, loading nothing.
8. **One guided flow.** The `curate_page` prompt walks any AI through the job in order: pick or claim the
   work, derive the lists, research with its own reach and the sources tools, supply and check sources,
   propose facts in batches, build structure, components, figures and pictures in the draft, preview,
   fix against the report, submit once, follow the outcome, and what to do when each gate refuses.

## Consequences

- The centre's cost of a supplied source is up to three cached index lookups and no model call; the
  gates' cost is unchanged (the supplied text replaces a fetch). Drafts and reports are database work
  only; a preview still costs what `preview_page` costs.
- A contributor could supply text that misquotes a real work. The identity check, the grade ceiling for
  unconfirmed works, the trust tiers and the reviewer's view of the supplied text are the defences; a
  reviewer who finds a false text rejects the fact and can see every fact resting on that supply.
- The sources reference and the contributor skill still say "anything behind a login" is never used;
  the lead amends them to name supplied text as the one way such a source enters.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
