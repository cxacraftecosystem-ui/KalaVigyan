# 0079. Craft, category, map and science pages read without signing in

Craft, category, map and science pages read without signing in, through one optional-reader
dependency in which an anonymous reader holds the lowest role and is limited per address. Ask,
Saved, Lessons, Settings and Admin stay signed in, and the boundary is tested.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| What amended it | [0084 Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones](0084-field-voices-v2.md): point 3, with full transcripts for signed-in readers only |
| What amended it | [0091 Field voices v2 in KalaVigyan: storage, citation, the craft page and the reading view](0091-field-voices-kalavigyan-side.md): point 3, what each reader reads of field transcripts |
| What amended it | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): the page's one role-dependent part |
| What built on it | [0097 Everything reads without signing in except asking](0097-public-reading-everywhere-but-asking.md): public reading, widened to everything but asking |
| Every decision, by group | [README.md](README.md) |

## Context

The owner decided on 2026-11-18 that craft, category, map and science pages are readable without
signing in and show link previews, while Ask, Saved, Lessons, Settings and Admin stay signed in.
Until now every API route except the sign-in flow and the privacy notice needed a bearer token
(`core/deps.get_current_user`). The read routes behind those pages answer from stored rows only;
their only role-dependent part was the craft page's All evidence (`READ_ALL_EVIDENCE`, Researcher
and above) and the full craft list with retired crafts (Professor and above). The glossary term
route is different: on a miss it searches the web, makes a summarising model call, writes claims
back and translates, all charged to the signed-in reader.

## Decision

1. **The public reads.** These answer with or without a session: `GET /api/crafts/catalogue`,
   `/api/crafts/{slug}/page`, `/process`, `/region`, `/shared-science`,
   `/api/shared-science/{termKey}`, `/api/compare`, `/api/map/crafts`, `/api/map/layers`,
   `/api/map/layers/{layer}`, `/api/map/districts/{districtLgd}`, `/api/rivers/{mainRiv}`,
   `/api/molecules/{pubchemCid}/conformer`, `/api/terms/{key}`, the category pages'
   `/api/categories` and `/api/categories/{slug}`, and the new `/api/public/summary`. The craft
   profile (`/crafts/{slug}/profile`), which no page reads any more, stays signed in, as does every
   write, answer, voice, Listen, film, media, export, saved item, lesson, notification, usage,
   setting, preference and admin route.
2. **One optional-reader dependency.** `core/deps.get_optional_user` answers `None` when no bearer
   token is sent. A token that is sent must still be good: an expired or revoked one is 401 and a
   pending password change or two-step setup is refused exactly as on signed-in routes, so a
   reader is never silently read as anonymous. Routes take `api/public_deps.public_reader`, which
   adds the anonymous rate limit below.
3. **Anonymous is the lowest role, never more.** Role checks on a public read use
   `public_deps.reading_role(reader)`, which is the reader or `core/roles.LOWEST_ROLE` (Student):
   an anonymous craft page has no All evidence and only the claims its parts cite. The full craft
   list (`includeInactive`) answers 401 to an anonymous reader. Every public read is built from
   stored rows that leave out restricted sources, non-open claims and concepts and hidden claim
   statuses for every role. Quotes are scoped by their chunk as well: a citation linked to a
   stored chunk (`ClaimSource.chunkId`, which only answer write-back sets) is shown only when the
   chunk is not `RESTRICTED` and its ACL is one the reader may quote, and a claim left with no
   citation is not shown (`retrieval/statements.readable_citations`, read by every
   `services/knowledge_view` builder). `research/retrieval.chunk_acls_for` gives the ACLs:
   `PUBLIC` for a Student, `PUBLIC` and `RESEARCHER` (closed-licence full text, decision 0013)
   for a `READ_RESEARCHER_QUOTES` holder, as the media claim set already did (decision 0018).
   The craft page, process, shared science, compare, district and term reads pass
   `public_deps.reading_acls(reader)` to their loaders; the category pages, the relatives' ledes
   and the public summary read curated claims, which link no chunk, at the default (point 9). So
   an anonymous reader gets byte for byte what a Student gets and a Researcher still reads closed
   quotes; `tests/public/test_public_routes.py` checks the routes and
   `tests/db/test_public_reading_db.py` the stored rows.
4. **Terms: stored only for an anonymous reader.** `services/term_summaries.StoredTermLookup`
   answers a cached summary, or for English the summary built from the term's stored defining
   claims, and never searches, calls a model, translates or writes. A term that would need any of
   those answers 401 "Sign in to look this term up." (`NEEDS_LOOKUP_REASON`). A signed-in reader's
   lookup is unchanged, with its per-user throttle. The term store reads with the reader's chunk
   ACLs, and a kept summary is answered only while every citation it quotes is still shown to
   that reader (`term_summaries.cites_only_shown`), so a summary a Researcher kept with a closed
   quote is built again for anyone else. A summary built from stored claims carries as
   `checkedAt` the latest change of its claims and citations, not the time of the request, so
   its body and ETag hold between reads.
5. **Anonymous reads are limited per address.** `core/rate_limit.public_read_attempt` allows 300
   anonymous public reads in 10 minutes per client address (`client_ip`: the web proxy's viewer
   address when its secret matches, else the peer); the 301st answers 429 with `Retry-After` and
   a sentence that offers signing in. Signed-in reads are not counted. The web server's own reads
   (the proxy secret with no viewer address) count in one larger bucket of their own
   (`SERVER_READS_PER_WINDOW`, decision 0082), so server-rendered pages never share a visitor's
   allowance.
6. **Cache headers.** Every public read sets `Vary: Authorization` and an `ETag`: the stored
   version where the route has one (the catalogue, a map layer, a river basin's SHA-256), else the
   SHA-256 of the canonical JSON body (`core/http_cache.body_version`), or of the SDF for a
   conformer; a matching `If-None-Match` answers 304. An anonymous answer is
   `Cache-Control: public, max-age=300`; a signed-in one stays `private, no-cache`, so a shared
   cache never keeps a role-scoped answer. The conformer's signed-in
   `private, max-age=604800` became `private, no-cache` with its ETag, like every other read.
   `http_cache.revalidated` was replaced by `public_deps.cached_read`.
7. **`GET /api/public/summary`** (`research/public_summary.PublicSummary`, schema 1, golden
   `shared/public.summary.golden.json`): `counts` is the catalogue's own `summary` (crafts that are
   active and not catch-alls, GI-registered, states, placed, families, kinds), so the landing and
   the catalogue count with one rule (`services/catalogue_rows.catalogue_summary`); `featured` is
   the curated crafts of `FEATURED_CRAFT_SLUGS` (Kutch Ajrakh, Bastar Dhokra, Tikuli Painting), each
   with its page's `HERO` picture (or `null`) and its first lede sentence with every citation;
   `specimen` is the first overview sentence of Kutch Ajrakh citing curated claim `C023` (the 2001
   move to Ajrakhpur for good groundwater) with every citation and quote; `sources` lists each
   source those sentences cite once, in the order first cited; `points` are the map's points with
   only the crafts the catalogue counts, each with its total and the curated crafts there. A
   featured craft without a curated page or lede, or a missing specimen sentence, is left out with
   a logged warning, never an error, so the landing always renders. The summary is built at most
   once a day per process (`services/public_summary.SummaryCache` on `app.state`) and answered
   `public, max-age=86400` with its ETag. It carries no reader data.
8. **The boundary is tested.** A structural test lists every route reachable without a session and
   fails when one is added without being named; an anonymous request to every other route answers
   401 (voice calls switched on for the check); the rate limit is checked per address. A route test
   checks that each public read of claims is built for its reader's chunk ACLs, and a database
   test seeds a closed-licence chunk quote, a restricted chunk quote, a restricted source, a
   restricted-sensitivity claim and a withdrawn claim on Kutch Ajrakh, then checks that the
   anonymous page, process, shared science, compare and term summary leave all of them out and
   equal the Student's while a Researcher still reads the closed quote, and that a district story
   quoting the closed chunk is left off the map for a reader who may not quote it.
9. **Claim loaders default to what anyone may quote.** `knowledge_view.claims_for`,
   `claims_by_id` and `craft_profile`, `piece_lookup.claim_states`, `craft_process.process_records`,
   the shared-science, compare, district and craft-page loaders and the SQL term store take
   `acls` and default to `research/retrieval.OPEN_CHUNK_ACLS`, so a read that names no reader
   never shows a closed or restricted quote. The signed-in craft profile passes its reader's ACLs.
   The signed-in answer paths that read stored claims for the asker without knowing the asker's
   role (stored-claim answers and the write-back's cited claims, voice, zoom stories, what-if,
   market and measure blocks, picture choice, saved-explainer and quiz visibility, piece reuse, and
   the compare and concept-graph builders) pass `EVERY_CHUNK_ACLS` and read exactly as before.
   Scoping them by the asker is recorded as debt.

## Consequences

- The web client must stop treating a 401 from a public read as an ended session when it sent no
  token, call these routes from signed-out pages, and not call `/answers/config`, `/media/options`
  or any other signed-in route there. The web proxy should vary its own cache on the session
  cookie, since the browser never sends `Authorization` to it.
- The craft page's term sheet shows "Sign in to look this term up." to an anonymous reader for a
  term no signed-in reader has looked up yet.
- A Student signed in on the answer paths still reads a closed-licence quote of a written-back
  claim, which PLAN's capability table keeps for Researchers; the public reads no longer show it
  to anyone below Researcher. A citation whose chunk was later deleted (`chunkId` set to null by
  re-chunking) counts as having no chunk, as in the media claim set.
- The summary depends on the catalogue v2 summary and the craft page's `HERO` picture role; a
  change to either is a change to this contract.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
