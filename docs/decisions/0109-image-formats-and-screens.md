# 0109. Pictures in every common format, given from the chat and screened before review

Pictures arrive in every common format through one imaging adapter (Pillow with pillow-heif),
straight from the chat that made them, several under one declaration. They are screened before
review, cheapest check first, a flagged picture is never shared automatically, and missing pictures
are open work.

Date: 2026-11-20. Status: accepted (owner, 2026-11-20: pictures through MCP in every format, from
the chat that made them, screened before review; every MCP gap resolved). Supersedes the
no-imaging-library rule of decision 0104, item 3; the rest of 0104 stands.

| For | Read |
|---|---|
| What it supersedes in part | [0104 Image contributions: declared, read byte by byte, private until approved](0104-image-contributions-intake.md): item 3, the no-imaging-library rule; the rest stands |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0104 read PNG, JPEG and WebP byte by byte and added no imaging library, because a reviewer
saw every picture and re-encoding cost memory. Round 7 makes the MCP server the place knowledge is
created by many contributors at once: pictures arrive from phones (HEIC), scanners (TIFF, BMP),
AI tools (PNG, WebP, AVIF) and drawing tools (SVG, GIF), straight from the chat that made them, and
a Professor's picture is shared at once. Reading bytes alone cannot convert a format, compare a
picture with the ones already held, or let a model look at it before anyone else does.

## Decision

1. **One imaging adapter.** Pillow with pillow-heif (pinned in `backend/pyproject.toml` and
   `uv.lock`) lives behind `research/image_intake_pixels.py` only; everything else calls the
   intake. `Image.MAX_IMAGE_PIXELS` is 40 million and the adapter refuses, before decoding, a
   picture over 40 million pixels or one whose decoded size would pass 128 MB, so a decompression
   bomb is refused from its header. Decoding runs in a worker thread, two at a time per API
   process.
2. **Formats.** PNG, JPEG, WebP and AVIF are kept as they are, their metadata removed in place
   (PNG, JPEG and WebP as in 0104; AVIF's Exif, XMP and URI items are emptied inside the file, a
   valid empty Exif left where one was, and its `uuid` boxes become `free`; an AVIF whose metadata
   cannot be placed is made WebP). GIF keeps its first frame as a PNG. HEIC, HEIF, TIFF and BMP are
   turned upright from their orientation and made WebP at quality 90 with their colour profile and
   nothing else. SVG is accepted as a vector drawing and cleaned: a document type or entity is
   refused, and scripts, event handlers, foreign objects, embedded or linked pictures, links outside
   the drawing, `@import`, outside `url()`, metadata and editor attributes are removed; it is served
   with `Content-Security-Policy: default-src 'none'; style-src 'unsafe-inline'; sandbox` and
   `nosniff`, and pages show it only as an image.
3. **From the chat.** `give_image` and `give_images` (scope `contribute`) take the picture as
   `image_url` or `image_base64` (6 MB a picture, 12 MB a call) with the declaration the person
   confirmed in the chat and their words of confirmation. A link is fetched by the sandboxed
   fetcher process (`POST /fetch-picture`: the same https-only, public-address, pinned-TLS,
   three-redirect and streamed 10 MB guards as page fetches, no robots check because one person
   names one file), and its type is read from its bytes. Each call is recorded under the signed-in
   person as a `PictureDeclaration` (channel `MCP`, the words, the origin and tool, the terms
   version). The link page and the presigned slot of `start_image_upload` stay.
4. **Screens before review, cheap first.** Format and size (the intake), then an exact repeat
   (SHA-256) and a perceptual repeat: a 64-bit DCT hash compared in SQL with every stored
   picture's (`ImageFingerprint`, filled for older pictures by `python -m app.scripts.fingerprint_pictures`).
   A copy within 6 bits of a live picture is refused; within 12 bits it is flagged. Only then one
   call to the cheapest enabled route of the CAPTION (vision) task, with a 768-pixel JPEG preview,
   asks for identity documents (Aadhaar, PAN, passports, any card with a face and a number), a face
   in an AI-made picture, and unsafe content. The call is reserved and settled in the usage ledger
   like every model call, and its route, tokens and cost are kept in the picture's `ImageScreen`.
5. **A flagged picture is never shared automatically.** A picture flagged by the screen, a picture
   the screen could not look at (no vision route, the budget, a failed or unreadable answer) and
   every SVG wait for an Admin, with the reasons on the review card, even when a Professor gave
   them. A clear picture follows 0104: a Professor's is shared at once, anyone else's waits.
6. **Pictures as open work.** `MISSING_PICTURE` tasks are computed for every craft without a
   curated dossier: its first picture (`MASTHEAD`), the GI record's picture for a registered
   craft (`RECORD`), each stage and each material of its processes. A picture names one target or
   its task key; a waiting picture holds the task, approval completes the reservation and closes
   it, a refusal reopens it. A curated craft's pictures come with its dossier.
7. **One declaration for several pictures.** `POST /api/contributions/images/batch` and
   `give_images` declare up to ten pictures of one craft under one origin, tool and rights; each
   picture keeps its caption, description, facts, prompt and target and is screened and reviewed
   on its own.

## Consequences

- Converting means re-encoding: a HEIC or TIFF reaches the page as WebP and is no longer the
  file the person sent. The kept formats are still never re-encoded.
- The screens cost one vision call a picture (a few hundred tokens at the cheapest route). Without
  a CAPTION route every picture waits for a person; the admin routes page sets one.
- The perceptual comparison scans every fingerprint per upload; at a million pictures it should
  move to banded lookups.
- The cost recorded per picture joins the cost ledger built in parallel this round.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-20; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
