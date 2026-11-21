# 0072. Field voices come through signed peer routes, filtered by consent at the portal

Field voices reach KalaVigyan through three signed peer routes instead of the portals' export,
filtered by consent at the portal: publication is its own consent purpose, only the artisan's own
words travel, and credit is as the artisan chose. Withdrawal is by absence and fails closed, and
photographs travel as derived copies.

Date: 2026-11-18. Status: accepted; amended by 0084 (version 2: both portals, full transcripts and
craft images, by cursor with tombstones).

| For | Read |
|---|---|
| What amended it | [0084 Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones](0084-field-voices-v2.md): version 2, for both portals, full transcripts and craft images, by cursor with tombstones |
| The contracts it names | [field-voices.md](../contracts/field-voices.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Plan feature 9 (artisan voices, phase E) was designed on 2026-11-17 to pull the portals' existing
transcript export (`GET /api/data/transcripts/recordings.ndjson` and `turns.ndjson`) nightly,
signed in with each portal's master account, and to keep the transcripts as private
`FIELD_INTERVIEW` sources. On 2026-11-18 the owner approved publishing consented field-repository
interview quotes and process photographs, credited to the artisan and the workshop, never with
contact or identity details, and made craft pages public. The documentation portal's consent
ledger has purposes for outside processing, cross-portal sharing and analytics, but none for
publication, and its `ledger.decide` allows a recording when nothing was recorded. Photographs
there are the original uploads, with their EXIF location data.

## Decision

1. **Three signed peer routes, not the export.** `docs/contracts/field-voices.md`: an index per
   craft, then paged quotes and photographs per craft, on the same peer mechanism and token as
   the craft feed (decision 0003), behind their own portal flag. The portal sends only what may
   be published; KalaVigyan holds no portal password and never receives what it would have to
   drop. The export route stays the Research app's.
2. **Publication is its own consent purpose and needs a grant.** `PUBLICATION` joins the ledger's
   purposes in both portals. A quote needs a grant for its recording or its speaker and no later
   refusal by the speaker; a photograph needs its own grant from a person who looked at it
   (everyone shown agreed, no one under 18 shown). The owner's attestation of 2026-11-17 is
   written as `OWNER_ATTESTATION` grants for the recordings transcribed by that day, and covers no
   photograph and no artisan who refused sharing beyond the portal (`ArtisanSharingConsent`
   `granted` false, or a `CROSS_PORTAL_SHARING` refusal): a recorded refusal outweighs a blanket
   attestation until the owner decides otherwise.
3. **Only the artisan's own words.** Turns whose speaker is mapped to a consenting artisan of the
   recording; researchers and unmapped speakers are never sent. The question asked comes from the
   questionnaire's wording, not from the researcher's voice.
4. **Credit as the artisan chose.** A new portal row records named or unnamed and the name to use;
   without one, the recorded name (O4). Place is district and state from the stated location.
   The village is left out of version 1: the portal files it with the stated address, and a name
   with a village can find a home. Years in the craft are sent (O4's credentials); age, gender
   and every identity or contact field never are. Free text (quotes, workshop titles, captions,
   stage names, questions) can still carry a withheld name or the village, and only the portal
   holds them, so the portal screens it against each item's held-back terms and withholds or
   nulls what matches. The screen catches only spellings the portal holds, so KalaVigyan also
   never shows a workshop title beside an unnamed credit.
5. **Consistency by digest.** The index gives each craft's counts and a SHA-256 over sorted
   `id revision` lines; KalaVigyan recomputes it from the pages and applies nothing of a craft
   that changed while it was read. The signed path has no query string, so pages echo their slug
   and cursor.
6. **Withdrawal by absence, failing closed.** A complete snapshot that lacks an item removes that
   craft's link to it; an item left with no craft link is withdrawn at that sync, so an item
   listed under two crafts is not lost when it leaves one. A craft whose digest changed but could
   not be read is hidden, and nothing unconfirmed for 7 days is served.
7. **Photographs as derived copies.** The portal serves a metadata-free copy, at most 2,400 px,
   through a 15-minute presigned URL; KalaVigyan copies it once per revision into its own bucket.
   The copy lives under the opaque key `field-voices/<sha256>.<ext>` and is signed with that
   neutral file name, because the portals' naming convention puts the uploader, village and
   subject in keys and file names, which the URL would otherwise carry. KalaVigyan accepts image
   URLs only on the hosts in `FIELD_VOICES_IMAGE_HOSTS` and only with that path.
8. **Reader first, storage later.** KalaVigyan's reader (`services/field_voices_reader.py`) is
   built and tested against recorded answers behind `FIELD_VOICES_ENABLED` (default off); the
   tables are specified in the contract and wait for a migration. `PortalPeer.signed_json` is now
   the one signed GET of both peer feeds, and the craft feed's duplicate and first-problem checks
   are shared from `services/portal_craft_feed.py`.
9. **Source kind.** A recording is a `FIELD_TESTIMONY` source (the existing kind), not a new
   `FIELD_INTERVIEW` value; published quotes are `PUBLIC` chunks, replacing PLAN section 13 item
   7's researcher-only excerpts for consented recordings.

## Consequences

- Nothing reaches KalaVigyan until the portal ships the consent purpose, the credit row, the
  attestation script, the photograph copies and the routes, and both flags are turned on.
- The `artisan_voice` block (`research/blocks_people.py`) still declares `address` and `village`,
  which this feed never fills, and a `language` limited to the answer languages, which a quote in
  another language or `und` cannot meet; the block needs its next version before phase E shows
  quotes.
- The designer portal's ledger must gain the same purpose, since the two ledgers are one model.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
