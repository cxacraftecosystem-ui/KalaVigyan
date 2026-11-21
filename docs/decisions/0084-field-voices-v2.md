# 0084. Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones

Field voices version 2 serves both portals through one contract: full transcripts credited as
recorded and scrubbed rather than withheld, craft images by an allow-list of fields, and a ledger
read by an `updatedAt` cursor with tombstones. Its amendment the same day publishes everything above
the legal floor.

Date: 2026-11-18. Status: accepted. Amends decision 0072.

| For | Read |
|---|---|
| What amended it | [0097 Everything reads without signing in except asking](0097-public-reading-everywhere-but-asking.md): point 3, now that the full transcript is public |
| What amended it | [0112 Each field photograph filed on an artisan is reviewed by a person before it is shown](0112-reviewed-field-photographs.md): point 5 of its amendment of 2026-11-18; the legal floor stands |
| What it amends | [0072 Field voices come through signed peer routes, filtered by consent at the portal](0072-field-voices-contract.md): version 2, for both portals, full transcripts and craft images, by cursor with tombstones |
| What it amends | [0079 Craft, category, map and science pages read without signing in](0079-public-reading.md): point 3, with full transcripts for signed-in readers only |
| What built on it | [0091 Field voices v2 in KalaVigyan: storage, citation, the craft page and the reading view](0091-field-voices-kalavigyan-side.md): its KalaVigyan side |
| The contracts it names | [field-voices.md](../contracts/field-voices.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0072 specified version 1 of the field voices contract: the documentation portal alone,
single artisan turns as quotes, process photographs, a `PUBLICATION` grant per item, and per-craft
snapshots withdrawn by absence. No portal built it. On 2026-11-18 the owner directed that the
transcripts and the images of both portals, the designer portal included, come into KalaVigyan,
stated that everything in those applications is already consented for, and authorised building the
portal side. The safeguards that still hold: no identity data (Aadhaar, phone numbers, email
addresses, identity-card images or documents, postal addresses or anything finer than district,
dates of birth, bank details); phone numbers and email addresses scrubbed from transcript text;
quotes may be public, credited by the recorded name, workshop and date; the full transcript only
for signed-in readers; deleted or withdrawn records gone at the next sync; data only through the
signed peer routes, never with anyone's sign-in credentials.

## Decision

1. **One contract for both portals** (`docs/contracts/field-voices.md`, version 2): the same three
   signed peer routes in each, a state route and two streams (transcripts, images), behind
   `CROSS_PORTAL_FIELD_VOICES_ENABLED` (default off, pinned from an Actions variable), on the craft
   feed's token, nonce and signature. The version 1 routes are never built.
2. **The owner's direction is the consent; a recorded refusal still wins.** An item needs no grant.
   It is withheld when any refusal is recorded against it, its people or its workshop (the
   outside-processing verdict, `CROSS_PORTAL_SHARING`, the documentation portal's sharing refusal,
   or `PUBLICATION`). `PUBLICATION` joins the ledger's purposes as the way an admin withdraws a
   person, a recording, an image, a workshop or an account from KalaVigyan, from a web control in
   both portals. The attestation script and the per-artisan credit row of version 1 are dropped.
3. **Full transcripts, credited as recorded.** Every speaker, researchers included, is sent as the
   portal's speaker mapping records them, with the artisan's or designer's recorded name. KalaVigyan
   publishes only artisan and designer segments as quotes (`PUBLIC` chunks) and keeps the full
   transcript for signed-in readers in a new `SIGNED_IN` chunk ACL, so `chunk_acls_for` now takes
   the reader and an anonymous reader no longer reads what a signed-in Student reads (amending
   decision 0079 point 3). Amended by decision 0097: the full transcript is public, and every
   reader reads `SIGNED_IN` chunks.
4. **Scrub transcript text, never withhold it for a pattern.** The portal replaces email addresses,
   phone-like and Aadhaar-like numbers with KalaVigyan's own patterns and placeholders, plus the
   linked people's own numbers and addresses and the record's places finer than district
   (`[place]`, sparing words of the craft's own name). Spoken numbers in words cannot be caught, so
   takes that answer an identity or contact question, consent evidence and dictation clips are
   never sent. Labels (titles, captions, names) are still screened and nulled on a match.
5. **Images by an allow-list of craft fields.** Products, tools, processes and steps, raw
   materials, motifs, sketches, prototypes, iterations, final products and packaging are sent;
   images filed only on a person, a session or a workshop, event and cover photographs, signatures,
   logos, mood boards and designer-defined fields never are, because that is where portraits,
   identity cards, attendance sheets and other people's pictures are filed and the portal cannot
   tell them apart. The neutral metadata-free copy, its opaque key and its 15-minute URL are kept
   from version 1.
6. **A ledger, an `updatedAt` cursor and tombstones replace per-craft snapshots.** Each portal keeps
   `FieldVoiceItem` (one row per item, with its revision and payload) written by one writer at a
   time under an advisory lock with strictly increasing stamps, refreshed by the worker every 15
   minutes; the state route runs a gone pass first, so deletions and withdrawals are tombstones
   before each read. Tombstones say why (`DELETED`, `WITHDRAWN`, `REPLACED`, `MERGED`,
   `UNLISTED`); artisan merges re-key people through `mergedIds`. A `gone` view lets KalaVigyan apply
   every tombstone on every run even while a long first import is still paging. The version 1
   digest survives as a per-stream reconciliation check.
7. **District is the finest place**, from the LGD register only; under-18s stay out (kept from
   version 1, since the portals record no guardian's consent).
8. **A field interview is an A source for the speaker's own practice.** The curation rubric gains
   that line; testimony alone may support process, materials, design and economics claims about the
   speaker's own work, and only beside another A or B source for science, history and health.
   Claims from it start provisional.
9. **Shared code, recorded once.** The portal side lives in a shared package recorded in
   `shared/field-voices.sha256` with its own parity test, beside a small per-portal adapter
   (`field_voices_portal.py`) for what only one portal has: design workshop stages and designers,
   the documentation portal's sharing refusals, and each portal's merge records.

## Consequences

- Both portals build the package, the adapter, a migration (`PUBLICATION`, the ledger), a worker
  lane, the admin control (web only) and a deploy pin; their differences are recorded in
  `C:/dev/IIT/docs/convergence`. KalaVigyan replaces its version 1 reader and builds the storage,
  the `SIGNED_IN` ACL, the transcript reading page, the craft page's voices and gallery, the image
  copies and the withdrawal cascade. The build split is at the end of the contract.
- Designer portal prototypes and sketches arrive as images, which delivers the image half of plan
  feature 10.
- The craft page's Voices part and `artisan_voice` version 2 are shared with KalaVigyan's own
  artisan testimony (decision 0083), told apart by `origin` (`DESIGNER`, `FIELD_REPOSITORY`,
  `KALAVIGYAN`).
- Portraits, event photographs and session photographs stay in the portals until a later version
  can tell a document from a picture.
- The portals hold a second copy of each listed transcript in the ledger's payload; a gone item
  keeps no content there.

## Amendment (2026-11-18, later the same day): everything above the legal floor

The owner directed: "Everything is consented for already. There is no one over there that is under
the age of 18 in terms of artisans. So don't bring too much ethics into this... I need all of the
recordings from there. Loosen it up, do whatever. I need each and everything that is present over
there with me as well." Full transcripts are public on KalaVigyan. Later that night, for images
filed on artisans (researchers had filed Aadhaar cards on artisan profiles): "Bring it, but do not
show, we will figure out something later, but do not close the path".

- **Point 4 changes:** takes that answer identity or contact questions, whole-section and
  whole-session takes, consent clips and dictation clips are listed, with their numbers and email
  addresses scrubbed. Place terms are no longer held back: village and place names stay in
  transcript text, titles, captions and labels. Labels are scrubbed like text and nulled only when
  nothing but placeholders is left, so everyone is credited by the name the portal records.
  `scrubbing.version` is 2 and counts `EMAIL` and `NUMBER`.
- **Point 5 is replaced:** every image comes across wherever it is filed (artisans, sessions,
  workshops, design workshops, designer profile photographs, events, covers, openings, mood boards,
  designer-defined fields, portraits), except the legal floor. An image filed on an artisan, on a
  session or in a participant field is sent marked `artisanLinked`. KalaVigyan stores it like any
  other image (private copy, `MediaRef`, `FieldImage` with `artisanLinked` true) and shows it in no
  public or signed-in payload, page, list or image route, behind the setting
  `field_voices.artisan_images` (`HIDDEN` until a Master Admin sets `SHOWN` with
  `PUT /api/field-voices/held-images/visibility`, no code change); admins see what is held at
  `GET /api/field-voices/held-images`. A held image may be an identity card the portals cannot
  recognise, so before the setting is flipped every held image is opened in its portal (the list
  names the portal and the file's id) and an identity document there is withdrawn or removed.
- **Point 7 changes:** district stays the finest place in structured fields; the under-18 rule is
  removed (the portals no longer read a date of birth).
- **The legal floor**, stated in the contract as law, not policy (section 29(4) of the Aadhaar Act,
  2016 prohibits publishing, displaying or posting an Aadhaar number publicly; identity documents,
  signatures and bank details are never craft content): Aadhaar-like numbers (spaces, hyphens or
  dots), phone-like runs of ten or more digits, PAN-, voter ID- and IFSC-like codes, email
  addresses, and the linked people's own phone and Pehchan numbers and email addresses are
  scrubbed from all text (a number spoken in words, an unlinked person's Pehchan number and a
  nine-digit account number are not caught); images the portal recognises as identity documents
  (any `identityPhotograph` mark, the designer portal's `PENDING` mark written the moment a card is
  read included, or a media, stage or sent caption or a file name naming one), signatures (consent
  forms and certificates included), bank or payment details and CVs are never sent, nor the
  Aadhaar verification and fingerprint fields; no account credential is ever sent. An identity
  card no portal can recognise (no mark, no naming caption; the documentation portal has no mark
  at all) can only be filed on an artisan, a session or a participant field, so it arrives
  `artisanLinked` and is held, never shown, under the owner's "Bring it, but do not show";
  section 29(4) forbids publishing or displaying, which a held copy does not do. KalaVigyan's
  reader refuses a page only for the legal floor (a signature, CV or certificate stage field, an
  identity, signature, consent or bank caption, a never-sent key) and for an image item without
  `artisanLinked`; the portals withhold every image whose sent caption would match, so a portal
  page is never refused for a caption. KalaVigyan's field screen holds the same text patterns
  (`field_voices_screen.FIELD_PERSONAL_DATA`), apart from the shared `PERSONAL_DATA`, which also
  screens research identifiers.
- **Contract follow-ups from the portal build:** the identity-question rule is gone; the held-back
  people are every linked artisan (the take's subjects, mapped speakers, the session's
  participants, the file's own artisan, stage and record artisans) and the design workshop's
  designers, for their numbers and email addresses only; held-back places are gone; the admin
  control's strings are `frontend/lib/fieldVoices/strings.json`; the database tests are one
  byte-identical file, `test_cross_portal_field_voices.py`, in both portals.
- **Still out:** a recording without a transcript, an item without a craft, drafts, rejected,
  removed or deleted records, recorded refusals and undecodable images.
- **Consequence:** the consequence above that portraits, event and session photographs stay in the
  portals no longer holds; they arrive, artisan-linked ones held hidden.

## How this record is kept true

Its Amendment of 2026-11-18 records the owner's direction later the same day. Beyond that it is not
edited except to mark it superseded: a later choice is a new record that names this one, and the
table above links the two both ways. The parts later records changed stay here as they were decided;
the later record is the one that holds. It records the choice as taken on 2026-11-18; what the code
does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
