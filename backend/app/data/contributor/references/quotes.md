# Quotes and locators

KalaVigyan's sentences rest on stored facts, and its facts on verbatim quotes from graded sources.
These are the rules of that evidence and of the fact it supports, for every contributor: a fact
proposed over the MCP server, a claim in a dossier, a structure item, a source added to a held
fact, or a unit of a delivered component.

## Quotes

- Every fact carries at least one quote, copied verbatim from the source in the source's own
  language: 25 to 300 characters, the whole clause the fact rests on, never a fragment that changes
  its scope. When the supporting sentence sits next to the quoted one, quote it too.
- A fact rests on up to 5 sources, each with up to 6 quotes, each quote given once.
- Every number, formula, name, colour, cause and comparison the fact states is in one of its
  quotes.
- Every local name in a fact appears in a quote, spelt as the quote spells it.
- Tables are read: quote the row as it stands (`Date of Filing | 15-10-2025`).
- A source's error stays as the source wrote it (the page checklist, rule 22).
- The gates fetch every source themselves and refuse a quote they cannot find in the fetched text.
  Typographic quotes and dashes, line-break hyphens and spacing are folded before matching; nothing
  else is, so never correct, shorten or translate a quote.
- A source the contributor supplied is read from the supplied text instead: quote it exactly as
  supplied, with the locator of its passage.
- Take a quote from what `read_source` returns: its passages are the fetched text after that same
  folding, so a quote copied whole from one passage, or across the neighbouring lines of a PDF, is
  found. `check_quote` gives the gate's verdict on a quote before it is proposed, and on a miss the
  closest run of words the text holds; a quote is mended from that run, never the text from the
  quote.

## Locators

- Every quote names where it stands in its source: a page, section, paragraph, line, table row or
  timestamp (`p. 14`, `section 2.3, paragraph 4`, `Table 3, row 7`, `12:40`).
- A locator points at the quote itself, not at the document: a reader who follows it finds the
  words.
- `read_source` numbers the fetched text by paragraph for a web page and by line for a PDF. Give
  the page or section the source itself shows when it has one, and that paragraph or line when it
  has none.

## One fact per sentence

- A fact is one plain English sentence of 8 to 40 words that says no more than its quotes. Every
  word that carries meaning (a cause, a comparison, a material, a place, `most`, `faster`,
  `completely`) is in a quote. Same subject, scope, tense and time as the source: `during British
  rule`, not `after`; `were`, not `are`.
- Hedges and qualifiers stay: about, approximately, believed, said to, probably, in the mid 2010s.
  A theory or a legend is marked as one, and marking it does not replace its hedge.
- One voice stays one voice: an artisan's account, an author's or an organisation's opinion, or a
  GI application's assertion is attributed (`one artisan said`, `the GI application describes`),
  never stated as the craft's general fact.
- Counts, prices and dates carry their year, quoted. An undated `today` or `now` is not a date. A
  date is what the record says, never inferred from a document's title.
- When sources disagree, each version is its own fact, and the difference is shown as "sources
  differ"; it is never settled by a writer.
- One fact is stored once. A second source for a held fact is a second quote on that fact, never a
  second fact.
- General facts stay general: an encyclopedia definition or a statement about the craft across
  several states is never hung on this craft's material or centre unless a source says so. No
  filler: museum listings, plinth descriptions, an event a page only lists.
- Places are named to district or village, the district taken from a quote, not from memory.
- No personal data beyond what a published source states: a named person only as a source names
  them with the craft, and never an authorised user's name, house number or address, a phone number
  or an email address.
