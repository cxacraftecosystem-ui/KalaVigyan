# 0112. Each field photograph filed on an artisan is reviewed by a person before it is shown

Admins and Master Admins review each field photograph filed on an artisan before it is shown, one
recorded decision per photograph, after the picture screens have looked at it. A photograph flagged
as an identity document or an unnamed face can be shown only by a Master Admin, the rule fails
closed, and pages follow at once.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "the admins, and master admins should be able
to review the images and add them here"). Amends decision 0084 (amendment of 2026-11-18, point 5)
and the held images of decision 0091; the legal floor and the rest of both stand.

| For | Read |
|---|---|
| What it amends | [0084 Field voices v2: both portals, full transcripts and craft images, by cursor with tombstones](0084-field-voices-v2.md): point 5 of its amendment of 2026-11-18; the legal floor stands |
| What it amends | [0091 Field voices v2 in KalaVigyan: storage, citation, the craft page and the reading view](0091-field-voices-kalavigyan-side.md): its held images, each field photograph filed on an artisan now reviewed by a person |
| Every decision, by group | [README.md](README.md) |

## Context

Since decision 0084 the designer and documentation portals send every image above the legal floor.
An image filed on an artisan, a session or a participant field comes marked `artisanLinked`, and
KalaVigyan stores it but shows it nowhere, because researchers have filed Aadhaar cards on artisan
profiles that no portal can recognise. The only way to show such photographs was one setting,
`field_voices.artisan_images`, which a Master Admin could flip for every held photograph at once;
the standing rule was never to flip it before a person had looked at the whole held list. Artisans'
own photographs of their work therefore never reached their pages, and the one switch that could
show them would also have shown any identity card among them.

## Decision

1. **One decision per photograph.** Admins and Master Admins (`REVIEW_CONTRIBUTIONS`) review each
   held photograph on `/admin/field-photos`, beside the contributed pictures: the picture large and
   zoomable, its caption, crafts, people named, placements, credit, workshop, rights statement,
   rights holder and licence, portal and file id, date taken and size, and what each screen found.
   They show it, keep it hidden with a reason (an identity document, a person who has not agreed, a
   private place, poor quality, not this craft, or another reason given in a note), or show a crop
   that leaves a region out. A crop is a new copy of the region kept, made by the bounded imaging
   adapter of decision 0109 (`research/image_intake_pixels.cropped`) from KalaVigyan's stored copy,
   kept in the photograph's own format and stored beside it under `naming.field_voice_key`; the
   original stays private. Each decision names the copy it was made on (`seenSha256`); a decision on
   a copy the reviewer did not see is refused.
2. **Who, when and why.** The current decision is one `FieldPhotoReview` row per photograph (the
   decision, reason, note, flags cleared, crop, decider, role and time); every decision also writes
   an `AuditLog` row `field_photo.decided` with the same facts, and the screen lists the last five.
   A shown photograph can be hidden again at once by any Admin.
3. **Screens first.** The picture screens of decision 0109 look at every held photograph as the
   sync brings it (`app.scripts.sync_field_voices` screens up to 200 a run after the sync, and an
   Admin can screen ten at once from the page): a perceptual fingerprint compared with every stored
   picture and every other field photograph (within 12 bits it is a near duplicate), then one call
   to the cheapest CAPTION route asking about identity documents, faces and unsafe content. A field
   photograph is a photograph, so the screen is asked to flag any face (`FACE`), not only one in an
   AI-made picture. The result is kept per copy in `FieldPhotoScreen` with its route, tokens and
   cost; a copy the screen could not look at is looked at again on the next run. The queue sorts
   likely identity documents first, then faces, then everything else the screens flagged or have
   not looked at, then the clear ones.
4. **The riskiest last word.** A photograph the screen flags as an identity document, or as a face
   when its record names no one, can be shown only by a Master Admin, and only after clearing the
   flag with a note saying why it is wrong or by showing a crop that leaves the region out. Nobody
   shows a photograph the screens have not looked at.
5. **Fail closed.** A photograph filed on an artisan reaches a page, the "Show all" list, the
   gallery or the image route only when its own decision, made on its current copy, is to show it
   or its crop. A new copy from the portal waits for a new decision. `field_voices.artisan_images`
   becomes the master kill switch: `HIDDEN` hides every such photograph whatever its decision;
   `SHOWN` shows only those decided shown. A portal's tombstone still withdraws a photograph at once:
   its row, screen and copy go, its review loses its photograph and is deleted with its crop after
   the same sync run, and the same photograph listed again waits for a new decision. Photographs
   not filed on an artisan are shown as before unless a decision hides them. The rule lives in
   `services/field_photo_scope.shown_field_photos`, which every reader of field photographs uses.
6. **Pages follow at once.** A decision moves the craft page's stamp (`fieldPhotoDecidedAt`, one term
   in `services/craft_page_stamp.py`) and asks the web's revalidation route to refresh the pages of
   the photograph's crafts; flipping the switch refreshes every craft with a held photograph.

## Consequences

- The vision screen's call moves from `api/picture_vision.py` to `providers/picture_vision.py`, so
  the sync script can screen without importing the API layer; `VisionRequest` gains `faces`, and its
  `user_id` may be empty for a run with no person behind it.
- A screen costs one vision call per held copy, settled in the usage ledger without a user; without
  a CAPTION route every held photograph is recorded as not looked at and an Admin decides by eye.
- Answers use no field photographs today; any future reader of them goes through
  `shown_field_photos`. `retrieval/field_scope.shown_images` alone no longer decides a held
  photograph and should take the review clause when that module is next changed.
- The served crop keeps the stable image route, which answers 302 to a fresh 15-minute link; a
  browser may keep an earlier redirect for up to five minutes after a photograph is hidden again.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
