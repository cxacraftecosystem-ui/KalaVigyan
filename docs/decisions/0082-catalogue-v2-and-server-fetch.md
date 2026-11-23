# 0082. Catalogue v2: reader names, depth, concepts and one count, and server fetch

Catalogue schema version 2 adds reader names, depth, concepts and one counting rule, with local
names only from sources and each piece of editorial data in one home. The web server fetches the
catalogue itself under its own allowance and keeps it for 300 seconds, with the body as its ETag.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| A week-cached reading page's reads are absent only on a 404, and any other failure fails the render (narrows item 8) | [decision 0172](0172-a-rotated-session-taken-over-and-cached-pages-kept-whole.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The crafts index and map audits (plan task 1A-10, corrected by both critiques) found the index
showing the register's spellings and taxonomy ("Metal Embosing", "Textiles based Craft Category ›
Embroidery"), no picture, depth or native-script name for any craft, and 35 catch-all rows counted
as crafts. "indigo", "mordant" and "lost wax" found nothing. The landing said 455 crafts, the
index 461 and the map 380, each counted by its own rule. Server-rendered pages (decision 0079 makes
craft, category, map and science pages public) had no way to call the API: the browser proxy is
the only path, and forwarding a session cookie to cache public data would make every view a round
trip to the API.

## Decision

1. **Catalogue schema version 2, fields added.** `GET /crafts/catalogue` keeps every field of the
   designer portal's `CraftCatalogue` and adds `schemaVersion`, `summary`, `concepts`; on categories
   `label`, `palette`, `readerCount`; on sub-categories `label`, `readerCount`; on crafts
   `displayName`, `familyLabel`, `kindLabel`, `palette`, `giYear`, `hero`, `depth`, and fills
   `localName`. The typed contract is `research/craft_catalogue.CraftCatalogue`; the golden
   `shared/craft.catalogue.golden.json` is reproduced byte for byte by the backend and parsed by
   `lib/craftCatalogueContract.ts`, which refuses a body off the contract.
2. **One counting rule.** A reader craft is active and not a catch-all row
   (`catalogue_rows.is_reader_craft`), the rule the map already used. Catch-all rows stay listed
   with `isCatchAll`; `summary` (crafts, GI-registered, states, placed, families, kinds) and every
   `readerCount` leave them out. States are LGD states and union territories, so "All India" is not
   one. The index, the map header, the landing and `/public/summary` read these numbers; no screen
   states a count of its own. Where catch-all rows are on screen they are named apart from the
   count: the index's status line reads "Showing 15 of 420 crafts and 1 “Other” entry", and a
   group's header counts its readers only.
3. **Editorial data, one home each.** Family and kind labels stay in `craft_families.json`
   (decision 0081), which gains one palette key per family from `FAMILY_PALETTES`. The keys are
   named here for the redesign's colour tokens to adopt (plan task 1A-01); no frontend token maps
   them yet. Spelling and case fixes of register names, and local-name overrides, are
   per-craft data in `craft_names.json`; the register list itself stays byte-identical with the
   designer portal and its spelling stays an alias, so search and cross-portal matching are
   unchanged. `craft_page_family.reader_name` is the one display-name rule for the page and the
   catalogue.
4. **Local names only from sources.** A stored `Craft.localName` wins; else the editorial value;
   else an active alias in a non-Latin script, in a language of the craft's first state that has
   one (`state_languages.json`), from the highest-ranked source (curated, then Immersive, then
   Wikidata) and the shortest within it.
   Machine transliterations never become a local name. 67 of the 420 reader crafts on the master
   list get one today.
5. **Hero and depth from what is stored.** The hero is the craft page's lead picture of a curated
   craft (`hero_index`), only an inline picture with its author and licence. A Commons file whose
   stored width is over 500 pixels is served as its 500-pixel thumbnail, one of Wikimedia's
   standard thumbnail widths; any other picture is served as stored, because Commons refuses a
   thumbnail wider than its original and the width of a picture is not known until it is
   recorded. Depth counts visible claims in HYBRID mode, the longest
   process's stages, the curated pictures and the district or point locations, with the curated
   coverage. GI year comes from the curated GI record, else the GI registry rows.
6. **Concepts are search's fallback.** Glossary terms linked to reader crafts (not the crafts' own
   names) and materials keyed on their head word are merged by key and sent with the crafts they
   link. Search answers matching concepts first, each with its crafts, then crafts matching by
   name, alias, local name, state or family, then the concept-linked crafts.
7. **The ETag is the body.** `version` is the SHA-256 of the catalogue as served, so an import or
   a curation version moves it and a touched `updatedAt` alone does not.
8. **Server fetch.** `lib/server/serverFetch.ts`: `publicFetch` sends no cookie or token and
   caches by Next tag for the API's public `max-age` (300 s); `signedInFetch` forwards the session
   cookie as a bearer token with the viewer address and is never cached. Both stop after 4 s and
   answer a typed failure, so a page renders its fallback (the landing reads its count from
   `/public/summary` and says "The crafts" when the count is not to hand).
9. **The web server's own reads have their own allowance.** A public read carrying the proxy
   secret and no viewer address is the web server rendering a page, not one visitor, so
   `core/rate_limit.public_read_attempt` counts it in one bucket of 3,000 reads in 10 minutes
   (`SERVER_READS_PER_WINDOW`) instead of the 300 of an address. A cold crawl of every public
   craft page and region (about 1,000 reads), fetched again once inside the window by the
   300-second revalidation, fits with room to spare. The viewer address is not forwarded on
   cached reads, because it would split Next's data cache by visitor. Every call the browser
   proxy and `signedInFetch` make carries a viewer address, `unknown` when the platform gave
   none, so a visitor's read never lands in the server's bucket: `unknown` is no address, and the
   API counts the call against the address it came from, as before.
10. **The reader catalogue is kept for 300 seconds.** `GET /crafts/catalogue` without
    `includeInactive` is built at most once per process in that time (`core/kept_value.KeptValue`,
    the public `max-age`), so a 304 or a repeat read costs no query; the full list with retired
    crafts is always read fresh.

## Consequences

- The catalogue grows from about 230 KB to about 340 KB for the 455 master crafts (unindented JSON,
  before the concepts), and assembling it takes about 70 ms after about ten database reads. Kept
  for 300 seconds, a curation import, a new claim or a register change reaches readers within
  five minutes, the delay the public `max-age` already allows. Caching it per curation version
  is plan task 1B-09's.
- Curated pictures carry no width yet, so every curated hero is served as its original file until
  the curation import records the dimensions (curation v2, plan tasks C0-01 and C0-02); then the
  thumbnail applies with no change here.
- `KeptValue` is the third time-limited value in the API, beside `CraftIndexStore` and
  `public_summary.SummaryCache`; those two should move onto it.
- Materials named differently across dossiers ("Myrobalan (harda)", "Harda (myrobalan)") are two
  concepts, each findable by the other's name; "lost wax" finds a concept only once the science
  library writes one (plan tasks C2-01 and C2-02).
- The client refuses a version 1 catalogue, so the API must carry version 2 before the web app
  that reads it; between the two deploys the craft list shows its load error.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
