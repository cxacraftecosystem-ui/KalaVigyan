# What counts as a source

How KalaVigyan chooses, grades and records the sources its facts rest on, and which licences let a
source's material be shown. Every contributor follows it, over the MCP server or in the repository.
The gates read each source again themselves: they fetch it, grade it and read its licence, so a
source chosen against these rules is refused, never argued.

## Where to look

KalaVigyan's own research reads these, and over the MCP server every contributor reads them
through the very same adapters, keys and limits:

| Kind | Sources | Tool |
|---|---|---|
| Scholarly | OpenAlex, Semantic Scholar, Crossref, Europe PMC, DOAJ, CORE, arXiv, Springer Nature, Elsevier; Unpaywall for open-access copies | `search_sources` |
| Reference | Wikipedia, Wikidata | `search_sources`; `lookup_entity` for one item |
| Web | SearXNG, then Brave when it finds too little | `search_sources` |
| Compounds | PubChem, with its GHS hazard records | `lookup_compound` |
| Pictures | Wikimedia Commons, Openverse | `find_pictures` |
| Snapshots | the Wayback Machine | `archive_source`; `read_source` names an existing one |

A source found anywhere else is judged by the same rules below.

## The grades

Grade every source before quoting it, and prefer A and B:

- **A**: primary or authoritative. The GI journal and registry, peer-reviewed papers, museum
  collection records, government reports (Textiles Committee, Development Commissioner
  (Handicrafts), state handicraft boards), academic books.
- **B**: theses, conference papers, edited encyclopedias, established craft institutions with named
  authors.
- **C**: reputable press features, artisan organisations' pages with a named author, and a page a
  named organisation publishes about its own work, author named or not (a cooperative about its
  members).
- **D**: other web pages, and any shop, sales or retail page (a page that sells the craft, or links
  its visitors to a shop for it).

A fact whose quotes all come from D sources is refused, except an ECONOMICS fact stating a price in
a currency from a dated page (a price on that date). A source without a named author is never
graded B: it is A when it is one of the A kinds (a registry, a government report) and C or D
otherwise. A recorded field interview held by KalaVigyan's own portals is graded A for what the
speaker says of their own practice, and reaches facts only through the site's own write-back, never
through a proposal.

`search_sources` shows the grade its adapter gives each result by these rules, or the grade of
KalaVigyan's own record when the source is held already. `read_source` and `check_quote` report
the grade the gates will record for the address you cite: the held source's grade, or C for a page
KalaVigyan does not hold yet. Either way, choose by the grades above.

## Never used

Shadow libraries, AI-generated content farms, social media posts, unattributed blog posts,
screenshots of other sites, and anything behind a login, unless the contributor supplies its text
with `supply_source` (decision 0110): a paywalled paper read through their own subscription or
library, a book or PDF they hold, an archive, or a site that refuses our fetcher. Its identity is
confirmed in Crossref, OpenAlex or Semantic Scholar where it can be; a work found nowhere is graded
C at most (D with no named author or publisher). The text is kept privately for reviewers and
never shown; pages show only the short quote and its citation.

## Recording a source

- **Address**: the canonical page, over https, with no tracking parameters (`utm_*`, `fbclid`,
  `gclid`), never a search result or a redirect page. Give the DOI when there is one.
- **Title, authors, publisher and year** as the source states them, never guessed.
- **Language**: Indian-language sources are welcome; quote them in their own language and record
  the language code (`gu`, `hi`, `sd`).
- **Access**: open, abstract only, or restricted. A restricted source is cited from its open
  abstract, or from text the contributor supplied.
- **Archive**: when the live page blocks automated reading, give its Wayback Machine snapshot
  (`https://web.archive.org/web/<timestamp>/<url>`) as well. The same page at a new address, or its
  snapshot, is a source like any other when the quote is found in it. `archive_source` asks the
  Wayback Machine for a fresh snapshot, and `read_source` names one that already exists.
- **The day you read it**, as `YYYY-MM-DD`.
- **Independence**: a near-verbatim rewrite of another source is not independent support, and two
  quotes corroborate a fact only when their publishers differ.

## Licences

- **A source's own licence** is recorded as the source states it. Any source may be quoted in
  short verbatim quotes; its licence decides whether those quotes are shown to the public or kept
  for researchers. A licence declared open that the page itself contradicts is refused. The
  source tools mark each stated licence open or not by the very test the gates apply.
- **A picture from elsewhere** (Wikimedia Commons) needs an open licence that allows reuse and
  changes: CC0, the public domain or the public domain mark, PDDL, CC BY or CC BY-SA, any version.
  Never a non-commercial (NC) or no-derivatives (ND) licence, "all rights reserved", or a picture
  whose page states no licence. It is credited where it is shown: "Photo: Author, licence, via
  Wikimedia Commons". `find_pictures` lists only pictures whose licence passes this rule and that
  name their author, each with that credit line.
- **A picture a person gives** carries the person's own declaration instead of a licence (the
  contributor skill, Pictures).
- **A dataset** follows the dataset guide (`datasets.md`): the licences it may carry, how it is
  recorded, and which values belong to a dataset rather than to a fact.
