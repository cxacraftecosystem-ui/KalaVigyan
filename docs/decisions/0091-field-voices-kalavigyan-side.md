# 0091. Field voices v2 in KalaVigyan: storage, citation, the craft page and the reading view

KalaVigyan stores field voices version 2 from one migration, cites each recording as one
`FIELD_TESTIMONY` source through the existing write-back and copies the images again on its own
side. The craft page gains voices and field photos, the sync runs from its own workflow, and
staleness fails closed.

Date: 2026-11-18. Status: accepted. Builds the KalaVigyan side of decision 0084.

| For | Read |
|---|---|
| What amended it | [0097 Everything reads without signing in except asking](0097-public-reading-everywhere-but-asking.md): field recordings and their transcripts read without signing in |
| What amended it | [0112 Each field photograph filed on an artisan is reviewed by a person before it is shown](0112-reviewed-field-photographs.md): its held images, each field photograph filed on an artisan now reviewed by a person |
| What it amends | [0079 Craft, category, map and science pages read without signing in](0079-public-reading.md): point 3, what each reader reads of field transcripts |
| What it builds on | [0084 Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones](0084-field-voices-v2.md): its KalaVigyan side |
| The contracts it names | [field-voices.md](../contracts/field-voices.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0084 and `docs/contracts/field-voices.md` version 2 specify how both portals serve their
transcripts and craft images through signed peer routes, by cursor, with tombstones. The owner's
direction of 2026-11-18 is the consent; the safeguards are no identity data, scrubbed transcript
text, public quotes credited by the recorded name, the full transcript for signed-in readers only,
and withdrawal at the next sync. The portal side is not built yet; KalaVigyan has to be ready and
switched off until it is.

## Decision

1. **The reader is replaced, not extended.** The version 1 models, recorded answers and per-craft
   snapshot reading are deleted; `field_voices_feed`, `field_voices_items` and
   `field_voices_reader` read the state route and the two streams of either portal. A page that is
   unsigned, names another portal, stream, view or cursor, carries a never-sent key, breaks the
   order or a revision, or links an image off a listed host or outside 15 minutes is refused and
   stops that stream for the run. KalaVigyan screens every label and transcript text again and
   counts what the portal missed as `portalScrubMisses`. The scrub counts arrive as a list of
   `{kind, count}`, the shape the portals' shared builder sends: their kind names `EMAIL` and
   `PLACE` would be never-sent keys, so neither side exempts any key. As a second line behind the
   portal, a page is also refused when an image is filed in a stage field outside the contract's
   listed placements, a transcript's stage media is outside its listed fields, or an image caption
   reads as an identity document, signature or consent (`field_voices_placements`). Changes must
   rise by (`updatedAt`, `id`) across the pages of one view within a run, not only within a page.
   Recorded answers made by the designer portal's own builder pin the shape a portal really sends,
   and the portals' scrub vectors are kept byte for byte with their manifest hash.
2. **One migration, `0027_field_voices`,** adds the six tables of the contract, `ChunkAcl`
   `SIGNED_IN` and `MediaRef.objectKey`, plus `FieldVoiceStream.rereadFrom` and `seenAt` on the item
   tables: after a digest mismatch the stream is read again from the start and items that read does
   not touch are withdrawn at its end. Row ids are `uuid5` of portal and media id, so a re-run is a
   no-op and a changed revision replaces in place.
3. **A recording is one `FIELD_TESTIMONY` source**, reliability A, sensitivity
   `ATTRIBUTE_REQUIRED`, `evidenceKind` `FIELD_INTERVIEW`, its `url` the signed-in reading page
   `/voices/<id>`. Quote chunks (an artisan's or designer's segment of 40 characters or more, in its
   language and in English) are `PUBLIC`; transcript windows of every speaker are `SIGNED_IN`.
   `chunk_acls_for` now takes the reader: anonymous reads `PUBLIC`, any signed-in account adds
   `SIGNED_IN`, `READ_RESEARCHER_QUOTES` reads everything (amends decision 0079 point 3).
4. **Answers cite field interviews through the existing write-back.** Field chunks of the craft
   join stored-knowledge chunk retrieval; the composer sees each as an `EVIDENCE` candidate labelled
   "field interview: …"; a sentence that quotes it becomes a `PROVISIONAL` claim citing the
   recording's source and chunk, found by its URL. Answers read `PUBLIC` chunks only, so a stored
   explainer never holds a signed-in passage. The write-back cannot tell which planned facet a
   sentence is about, so the rubric's A line is applied fail closed: a sentence citing only field
   interviews is written back only when every facet of its section is `PROCESS`, `MATERIALS`,
   `DESIGN` or `ECONOMICS`, filed under the first; beside other sources it is filed under the first
   other source's facet and, for any other discipline, needs an A or B source among them.
5. **Images are copied again in KalaVigyan.** The portal's neutral copy is downloaded within its
   15 minutes, checked against its size and hash, re-encoded without metadata and stored at
   `naming.field_voice_key`. The `MediaRef` points at a stable public route that redirects to a
   fresh presigned URL, so stored pages and explainers never carry an expiring link.
6. **The craft page gains `voices`, `fieldPhotos` and `fieldVoicesTotal`** (schema version stays
   2: fields added, none changed). Voices merge the portals' quotes with approved KalaVigyan
   testimony (decision 0083) newest first, share `research/voices.VoiceQuote` with the
   `artisan_voice` block version 2, and list each quote's source in the page's numbering.
   `recordedOn` is a partial date, the day for portal quotes and the month for testimony. "Show
   all N" pages a public list route by offset.
7. **The sync runs from its own workflow only**, daily after the craft sync and on dispatch, up to
   90 minutes. It is not a deploy step: a first fill can take longer than a release may wait.
8. **Staleness fails closed.** A stream whose last good contact is over 7 days old serves nothing
   on the page, in the lists, the reading view, the image route or retrieval. That includes the
   claims written back from its recordings: `retrieval/field_scope.withheld_field_sources` (hidden,
   stale or linked to no craft) is left out of `claim_conditions`, `readable_citations` and
   `chunk_conditions`, so such a citation is unreadable, a claim with no other citation is hidden,
   and the recording's chunks are not retrieved through either branch.
9. **A changed revision checks its claims again.** The recording's chunks are deleted and made
   again, so no citation points at other text under a reused ordinal; each citation of its source
   keeps only while its quote still occurs in a `PUBLIC` quote chunk (and then points at it), and a
   claim left with no citation is deleted, as a tombstone deletes the claims that cite only it.
10. **Stored explainers are filtered when read, not rewritten.** `field_voices_readback` runs
    wherever a stored explainer is read (versions, exports, lesson packs, quiz, Listen, film): a
    citation of a portal interview stays only while its recording is shown and its claim still cites
    it. Filtering at read covers the 7-day rule too, which a rewrite at sync time could not. A prose
    sentence carrying a withdrawn citation is dropped, any other block carrying one is dropped,
    images then illustrating nothing cited go, sources are renumbered, and a section left empty says
    "A field interview this section quoted is no longer shown."; an explainer with no ready section
    left is not served. Stored knowledge pieces are reused only against current claims, which no
    longer include the withdrawn ones.
11. **"Show all" pages one order.** Portal quotes and approved testimony are merged in SQL
    (`field_voices_view.quote_order`: newest recording or conversation, portal before testimony,
    then recording and turn position, testimony by approval and id) and paged by offset there, so
    every quote appears once and a page loads only its own rows.
12. **Field images are not yet illustration candidates.** No `MediaRefClaim` rows are written for
    them; they show in the craft page gallery only (`docs/TECH_DEBT.md`).

## Consequences

- Nothing is read until `FIELD_VOICES_ENABLED` and `FIELD_VOICES_IMAGE_HOSTS` are set, and nothing
  arrives until a portal ships the routes; until then both portals answer 404 and the run reports
  them `not_served`.
- The craft page's Voices part and gallery components, and the full-transcript chunks for the
  expert panel's artisan seat, are not drawn yet (`docs/TECH_DEBT.md`).
- A saved explainer section only partly affected by a withdrawal shows no "quote withdrawn" note:
  the explainer contract has no field for one outside `artisan_voice` (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
