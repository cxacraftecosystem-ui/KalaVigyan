# 0006. Reference source adapters: Wikipedia, Wikidata, PubChem, Wikimedia Commons

Wikipedia (English and the Indian languages on an allow-list), Wikidata, PubChem and Wikimedia
Commons are each one `SourceAdapter` under `backend/app/sources/reference/`, read through the Action
API, SPARQL or PubChem's own routes. Commons gives file metadata only, hidden markup is dropped, and
each service has its own pace.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| The contracts it names | [research.md](../contracts/research.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Live research (PLAN section 0, tier T3) reads reference sources besides the scholarly indexes:
Wikipedia in English and Indian languages, Wikidata, PubChem (compounds, formulas, hazards) and
Wikimedia Commons file metadata. Each is one `SourceAdapter` (`docs/contracts/research.md`)
built on the shared `sources/http`, `sources/records` and `sources/adapter` (decision 0005).
Live calls were made on 2026-11-16 to choose endpoints and record fixtures.

## Decision

1. **Home.** `backend/app/sources/reference/`: `mediawiki.py` (what the three Wikimedia
   adapters share: the Action API call with `format=json`, `formatversion=2`,
   `errorformat=plaintext`; API errors returned inside a 200 become `ExternalFailure`
   (`no-such-entity`, `missingtitle`, `nosuchpageid` are `not_found`, `ratelimited` and
   `maxlag` `rate_limit`, `readonly` `unavailable`, anything else `error`); pages in search
   order by `index`; the latest revision; `primary_language`), one module per service,
   `wikidata_statements.py` and `pubchem_hazards.py` for the pure rendering, and
   `registry.reference_sources(client)`. No keys are needed; the contact email reaches every
   service in the User-Agent of `source_client`, as Wikimedia's policy asks.
2. **Wikipedia uses the Action API, not the REST search.** `rest.php/v1/search/page` returns no
   canonical URL, licence, revision or Wikidata id, and REST has no plain-text article. One
   `generator=search` call returns all four with `meta=siteinfo&siprop=rightsinfo`, so the
   licence is read live per wiki ("Creative Commons Attribution-Share Alike 4.0" on
   2026-11-16), not hard-coded. Fetch is TextExtracts `explaintext` of the whole article
   (`FULL_TEXT`). Ids are `wikipedia:<language>:<page id>`; the revision id travels in
   `externalIds.revision` and the attribution, so a quote can be traced to the version read.
3. **Wikipedia languages are an allow-list**, `WIKIPEDIA_LANGUAGES`: English and every Indian
   language that had a Wikipedia in the sitematrix on 2026-11-16 (as, awa, bh, bn, bpy, gom,
   gu, hi, kn, ks, mai, ml, mni, mr, ne, new, or, pa, sa, sat, sd, ta, tcy, te, ur). The query
   language's primary subtag picks the wiki (`bho` is `bh`, `kok` is `gom`); any other language
   is `InvalidInput`. The host is built from the code, so the list is also the guard against a
   crafted host. Widening it is one line.
4. **Wikidata: Action API for terms, SPARQL for statements.** Search is CirrusSearch
   (`list=search`, which matches multi-word text; `wbsearchentities` matched nothing for
   "alizarin mordant") followed by `wbgetentities` with `languagefallback`, because
   `prop=entityterms` has no fallback and many items lack Indian-language labels. Fetch reads
   the item the same way and its statements through one SPARQL query on
   `query.wikidata.org`, which returns property and value labels and quantity units in one
   call (`wbgetentities` would need a second, batched label lookup). Deprecated statements are
   left out. Time values keep only the precision Wikidata states (year, month or day); coarser
   ones (decade, century) are left out because the SPARQL literal would show a false day.
   External ids are left out of the text; PubChem CID, CAS number and ChEBI id go to
   `externalIds` (`pubchem_cid`, `cas_number`, `chebi`) so a Wikidata item links to the PubChem
   record. Fetch renders in English (`en,mul` labels): `fetch` takes no language. The item
   text is `EXCERPT`. Licence `CC0 1.0` (Wikidata's rightsinfo: structured data in the main
   namespace is CC0). Source type `DATASET`, trust `B`.
5. **PubChem: names, formulas and GHS hazards.** A query that is a molecular formula (element
   symbols checked against the periodic table, so `EDTA` is a name) goes to `fastformula`;
   anything else is looked up as a complete name, then as words (`name_type=word`), exact
   matches first ("alizarin" exact is CID 6293; word order puts sodium alizarinesulfonate
   first). A 404 is no hits. Properties (title, formula, weight in g/mol, IUPAC name, InChIKey,
   SMILES; `SMILES` and not the retired `CanonicalSMILES`) come from one property-table call.
   `fetch("pubchem:<cid>")` returns those properties; `fetch("pubchem:<cid>:ghs")` returns the
   GHS classification from PUG View. The hazards are a separate item because their licence is
   the reporting source's, not PubChem's: its URL is the first reporting source's page, its
   publisher that source, its licence the sources' licence URLs, and its attribution
   `Source: <name>, <url>` (ECHA asks for that form). At most `GHS_MAX_SOURCES` (3) sources, in
   PubChem's order; precautionary codes are left out (their text is an instruction to click).
   Compound records carry the NCBI policy URL as licence ("NCBI itself places no restrictions
   on the use or distribution of the data", read on 2026-11-16). Trust `A`. Pacing 0.25 s,
   under PubChem's 5 requests a second, because one search makes up to three calls.
6. **Wikimedia Commons: file metadata only.** `generator=search` in the File namespace with
   `imageinfo` `extmetadata` (object name, description, date, artist, credit, licence short
   name and URL). A file without a licence name is left out. `licence` is the short name
   (`CC BY-SA 4.0`, `CC0`); attribution follows Commons' form "author, licence (URL), via
   Wikimedia Commons" (an `http://` licence URL is dropped, URLs are https only). `published` is
   the original date only when it is an ISO date (`circa 1640–50` gives none; the upload date
   would misdate the work). Ids are `wikimedia_commons:<page id>`, with `commons_file` (the
   `File:` title) and `commons_media` (`M<page id>`) in `externalIds`. Source type `OTHER`
   (the enum has no media kind), trust `C` (uploader-written, unreviewed). Fetch text is the
   title, description, date, author, credit and licence lines (`EXCERPT`).
7. **Hidden markup.** `records.markup_text` now drops elements styled `display:none`, with the
   `hidden` attribute, and `script` and `style` content: Commons hides machine data inside
   descriptions (`date QS:P571,...`), and that text must not become quotable.
8. **Rates.** Wikipedia, Wikidata API and Commons 0.2 s each (Wikimedia asks for serial,
   moderate reads), Wikidata SPARQL 1.0 s (the query service allows 60 s of query time a
   minute per client), PubChem 0.25 s. Each has its own `SourceHttp` and 600 s cache.

## Consequences

- `reference_sources(client)` builds the four adapters; the answering service and coverage job
  hold the result for the process, as with `scholarly_sources`.
- Fixtures are responses recorded on 2026-11-16, trimmed of fields the adapters do not read;
  the PubChem word list is cut to 10 CIDs and the Wikidata statement rows keep only three
  external ids. The Wikidata time-precision and unitless-quantity cases are hand-written
  binding rows in the tests (no recorded item of the right shape was needed to state the rule).
- A SPARQL `select` for arbitrary structured lookups is not exposed: no caller needs one yet.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
