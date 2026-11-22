# 0097. Everything reads without signing in except asking

Everything reads without signing in except asking: public is the default, every guarded route states
why, and the web app splits into two route groups. Asking sends the reader to sign in and back, the
craft page and atlas render on the server, and field transcripts and an asker's chosen share links
are public.

Date: 2026-11-18. Status: accepted. Extends decision 0079; amends decisions 0084 (point 3), 0091
and 0095 (item 7).

| For | Read |
|---|---|
| What it amends | [0084 Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones](0084-field-voices-v2.md): point 3, now that the full transcript is public |
| What it amends | [0091 Field voices v2 in KalaVigyan: storage, citation, the craft page and the reading view](0091-field-voices-kalavigyan-side.md): field recordings and their transcripts read without signing in |
| What it amends | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): item 7, what on the page is public |
| What it builds on | [0079 Craft, category, map and science pages read without signing in](0079-public-reading.md): public reading, widened to everything but asking |
| The contracts it names | [field-voices.md](../contracts/field-voices.md), [craft-page.md](../contracts/craft-page.md) |
| Shared answers read their language from a public list of the answer languages | [decision 0145](0145-monograph-pages-and-speed-without-debt.md) |
| A share's files recorded and deleted from the bucket when it stops | [decision 0155](0155-accounts-and-sharing-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

On 2026-11-18 the owner directed that everything generated for a craft be reachable from its page
and that "only the query part is to be guarded, the rest of the application is going to be public
only". Decision 0079 had opened the craft, category, map and science reads; the web app still put
every reading page behind sign-in, transcripts, compare and answers stayed signed in, and the
structural test listed only the open routes, so a new guarded route needed no stated reason.

## Decision

1. **Public is the default for reading; every guarded route states why.**
   `backend/tests/public/test_route_inventory.py` gives every route one class and fails on a route
   with none, or a class naming no route. Open routes are `PUBLIC` (every public read takes
   `core/deps.get_optional_user` through `public_reader` or `public_asset_reader`, GET only),
   `SIGN_IN_FLOW` and `SERVICE` (health and the custom-LLM endpoints, which check their own
   secret). Guarded routes are `ASKING` (answers, follow-ups, research again, voice and artisan
   conversations, Listen, film, media), `OWN_RECORDS` (account, saved items, explainers and their
   exports, lessons and their files, share links, notifications, preferences, profile, own usage,
   artisan contributions), `ADMIN` (access, users, keys, routing, usage, testimony review, hiding
   generated pieces, held field images) and `CONSENT` (notices and consents). Each guarded route
   answers 401 anonymously, and each `ADMIN` route 403 to a signed-in Student, checked route by
   route; the password-link routes check `MANAGE_ACCESS` as a dependency for this, before reading
   the body or the database. Every public read but the four long-cached assets (`ASSET_ROUTES`)
   takes `public_reader`, and those four take `public_asset_reader`, so a public route without a
   counted bucket fails the test. The unused signed-in `GET /crafts/{slug}/profile` and
   `knowledge_view.craft_profile` are removed.
2. **The allowance fits a campus.** One anonymous Kutch Ajrakh page view makes 4 counted reads on
   opening (the page, its region, its shared science, the map layer list), one per Show all list
   and one per term looked up; about 10 for a reader who opens every tab and five terms. The limit
   is `CAMPUS_PAGE_VIEWS_PER_WINDOW` (30) times `COUNTED_READS_PER_PAGE_VIEW` (30): 900 anonymous
   reads per address in 10 minutes, and the web server's own bucket 9,000. Long-cached reads
   (conformers, river basins, map layer values, field-image redirects) take
   `public_deps.public_asset_reader`, counted in a bucket of their own,
   `ASSET_READS_PER_COUNTED_READ` (10) times the page allowance: 9,000 per address and 90,000 for
   the web server in the same window (`rate_limit.public_asset_attempt`). The figures and pictures
   of one page never spend its allowance, and no anonymous read is unbounded: a conformer miss can
   reach PubChem and a field-image redirect has no `ETag`.
   `tests/public/test_public_routes.py` replays 30 such page views with their asset reads from one
   address, checks the asset reads still answer once the allowance is spent, and that they are
   refused with 429 once their own bucket is.
3. **Two route groups in the web app.** Reading pages (`/crafts`, `/crafts/[slug]`, `/map`,
   `/compare`, `/voices/[id]`, `/shared/...`) moved to `app/(reading)`, whose shell never redirects
   and shows Sign in when signed out; `/ask`, `/saved`, `/lessons`, `/settings`, `/admin` and
   `/contribute` stay in `app/(protected)`. The account gates and the frame are shared
   (`components/shell/`), and the protected shell's route fade went with the move, since a first
   paint at opacity 0 breaks the design system's complete-at-rest rule. A signed-out reading page
   makes no signed-in call: no `/me` probe without a session marker, no `/answers/config`, no
   `/media/options`. `canReadAllEvidence` is gone; the Evidence tab follows the page.
4. **Asking sends the reader to sign in and back.** An Ask link from a reading page is
   `/login?next=/ask?q=<question>&craft=<slug>` for a signed-out reader, so the question and the
   craft come back after sign-in (`lib/askEntry`, `components/ask/useAskHref`). Talk is offered
   only to a signed-in reader, because whether voice is on is a signed-in read.
5. **The craft page and atlas render on the server**, from `publicFetch` in the server's own
   bucket, with `generateMetadata`: the craft's name, its first lede sentence, its path and its
   hero plate at the Commons width 1280, credited in the image's alt text.
6. **A signed-out production run** (`e2e/production/anonymous.spec.ts`, 360, 834 and 1440 px)
   opens the atlas, Kutch Ajrakh, the map and compare and fails on a redirect to sign-in or any 401
   or 403 under `/api/`; Ask from the page must land on sign-in with the question and, given the
   E2E account, return to it.

## Consequences

- Each new route needs a class in the inventory before its tests pass, and a new reading page
  goes in `app/(reading)` and `READING_ROUTES`.
- The redesign's monograph screen renders inside `ReadingShell`; its Ask, suggested-question and
  open-question links take `useAskHref`.
- The page metadata reads the version 2 fields (`overview.lede`, the `HERO` picture) that schema 3
  keeps until schema 4; it moves to `lede` and `masthead.picture` with the chapter screen
  (`docs/TECH_DEBT.md`).
- The shared pages draw an answer in English reading metadata, since the answer languages list is a
  signed-in read (`docs/TECH_DEBT.md`).
- The design guard's baseline carries the counts of the moved pages under their new paths
  (`app/(reading)/compare/page.tsx`, `components/crafts/CraftAtlas.tsx`) and the frame's bottom-nav
  padding (`components/shell/ShellFrame.tsx`); no count rose.

## Field transcripts

The owner decided on 2026-11-18 that full field transcripts are public: "only the query part is
to be guarded, the rest of the application is going to be public only", and everything in the
portals is already consented for (decision 0084).

1. `GET /api/field-voices/recordings/{recordingId}` and the `/voices/<id>` page read without
   signing in, through `public_deps.public_reader` and `cached_read` like every other public read
   (counted per address, `ETag`, `Vary: Authorization`, `public, max-age=300` without a session).
   What it answers is unchanged: the portals' scrubbing (identity numbers, phone numbers and email
   addresses replaced before the text is sent), the credit as recorded, the withdrawal by
   tombstone at the next sync, district as the finest place.
2. `research/retrieval.chunk_acls_for` gives every reader, anonymous or signed in, `PUBLIC` and
   `SIGNED_IN`, and a `READ_RESEARCHER_QUOTES` holder every ACL. An anonymous reader again reads
   exactly what a signed-in Student reads (decision 0079 point 3 as first written), so the craft
   page's `OPEN` variant is the same for both because both read the same ACLs. The `SIGNED_IN`
   value keeps its name until a migration folds it into `PUBLIC`; that is recorded as debt.
3. The field-image redirect takes `public_deps.public_asset_reader`, like conformers, river
   basins and map layer values, so the pictures of a page leave the page allowance alone.
4. Still signed in: artisans' own conversation audio and transcripts (decision 0083), testimony
   waiting for review (decision 0083 item 16) and a reader's own records.
5. The privacy notice says field interview transcripts from the portals are published, credited,
   with identity numbers, phone numbers and email addresses removed. Decision 0084 point 3, 0095
   item 7, `docs/contracts/field-voices.md` and `docs/contracts/craft-page.md` say the same.

## Share links

The owner's direction makes everything but asking public, and answers stay their asker's. Both
are kept by letting the asker choose what to publish.

1. **Opt-in, per version.** The asker of an explainer may share one version (`PUT
   /api/explainers/{id}/versions/{n}/share`), and a lesson's builder a pack (`PUT
   /api/lessons/{id}/share`, `BUILD_LESSONS`). Each answers a `ShareLink` (schema 1) whose `path`
   is the web page `/shared/answers/<token>` or `/shared/lessons/<token>`. `DELETE` stops it. A
   version, not the whole explainer, is shared, because a version is fixed: a later follow-up
   never appears under a link the asker made earlier, and a citation of the link stays true.
   Unshared answers and lessons still answer 404 to everyone else.
2. **The token is stored as it is.** It is 32 URL-safe characters (`secrets.token_urlsafe(24)`) in
   `Answer.shareToken` and `LessonPack.shareToken`, unique, with `sharedAt`, both null together
   (the `models/sharing.SharedByLink` mixin, migration `0030_share_links`). It is not hashed like a
   password link, since it grants only reading what its owner chose to publish, and the owner must
   be able to see and copy it again. Sharing again keeps the token. Stopping and sharing again
   makes a new one, so an old copy of the link stays dead.
3. **The public reading never shows more than an anonymous reader may see.** A shared version is
   the stored version read as its asker reads it (`explainer_history.shown_version`), then
   `services/public_explainer.public_version`. That step withdraws every citation whose claim and
   source have no `ClaimSource` an anonymous reader may quote (`knowledge_view.claims_by_id` at
   `chunk_acls_for(None)`), through `field_voices_readback.without_withdrawn`. A closed-licence or
   restricted quote, a withheld source and a hidden or non-`OPEN` claim therefore leave a
   Researcher's shared answer. A share with nothing left is refused (422) and answers 404 if it
   empties later. A shared lesson is rebuilt on each read from the public reading of its explainer,
   with the stored pack's title, sections and quiz choice and its id and date kept.
4. **The asker never shows.** The body carries no user id, email address or role. Files of a share
   (the report PDF, lesson slides, handout and HTML) are filed under the neutral owner id
   `00000000-0000-0000-0000-000000000000`, never the asker's, so a signed link names nobody. The
   question is the asker's own words, shown to them before they share.
5. **Read like every public read.** `GET /api/shared/answers/{token}` with `/citations`,
   `/citations/{format}` and `/pdf`, and `GET /api/shared/lessons/{token}` with `/files/{format}`,
   take `public_reader`. They are counted per address, carry an `ETag` of the body and
   `Vary: Authorization`, and answer `public, max-age=300` without a session (file links
   `private, no-cache`). A stopped share may therefore live in a shared cache for up to 300
   seconds. Exports of an unshared answer stay with its asker (`SAVE_EXPORT`).
6. **The privacy notice** says that the question, the shared version with its citations and its
   report are readable by anyone with the link, without the asker's name, email address or role,
   and without passages that only signed-in researchers may read, and that stopping the share, or
   a suspended or deleted account, ends the link.
7. **Asked first.** Share link opens a confirmation (`lib/shareNotice.SHARE_NOTICE`, the
   `ConfirmProvider` of both layouts) before the `PUT`: for an answer, the question, this version
   with its citations and its PDF report; for a lesson, the lesson with its citations, its slides
   and handout; and that the name, email address and role never appear.
8. **A link lives only while its owner may publish.** `shared_answer` and `shared_lesson` open a
   token only while its owner's account is not deleted and has no `REJECTED` or `SUSPENDED` access
   row (`services/access_roster.account_in_good_standing`), so a path that misses the withdrawal still
   answers 404. Deleting or suspending an account (`/users/{id}`, `/users/{id}/suspend`) and
   suspending or refusing its access (`/access/roster/{id}`, the `REJECT` decision, through
   `access_roster.bar_account`) withdraw every share of the account in the same transaction
   (`share_owners.withdraw_shares`), audited as
   `shares.withdrawn` with the cause and the counts; restoring the account does not bring a link
   back. A role change that loses `BUILD_LESSONS` withdraws the account's lesson shares
   (`reader_profiles.apply_role_change`), and the owner of a lesson reads and stops its share with a
   session alone, without `BUILD_LESSONS`.

Tests: `tests/learning/test_share_links.py` (routes with fakes: the anonymous and signed-in bodies
equal, no reader field, 304, the asker's own version only, 422 with nothing public, the lesson
capability, a former builder's own share, files under the neutral owner, the public reading's ACLs
and withdrawals, the lesson rebuild), `tests/learning/test_share_owners.py` (the owner condition
of both reads, the withdrawal and its audit record, barring an address, the roles that lose lesson
shares), `tests/db/test_share_links_db.py` on GitHub (a
seeded closed-licence quote leaves a shared version and its lesson, a stranger cannot share or stop
it, stopping ends the link, an answer with nothing quotable is refused, a suspended, refused or
deleted owner's link answers nothing, a withdrawal ends both kinds with its audit row, a demoted
builder's lesson stops while the answer stays), and `e2e/public-reading-unit.spec.ts` (the
confirmation's words, asked before the one `startSharing` call).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
