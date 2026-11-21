# 0104. Image contributions: declared, read byte by byte, private until approved

A contributed picture is declared first and its file sent second, read byte by byte and never
re-encoded, marked AI-made by its IPTC digital source type, and kept private until an Admin approves
it. The owner's amendment of 2026-11-19 makes an approved picture's consent irrevocable.

Date: 2026-11-19. Status: accepted (built on the owner's instruction to continue on Claude's
recommendations; the owner asked how an MCP user adds a picture made with ChatGPT or another AI).

| For | Read |
|---|---|
| What superseded part of it | [0109 Pictures in every common format, given from the chat and screened before review](0109-image-formats-and-screens.md): item 3, the no-imaging-library rule; the rest stands |
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): the backend of item 17's contributed pictures |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0101, item 17 settles that contributed pictures, AI-made ones included, travel outside the
chat, are declared, are checked on our side and are labelled as illustrations when AI-made, with
approval by role (item 12). This records how the first part, the backend, was built.

## Decision

1. **A declaration first, the file second.** `POST /api/contributions/images` records what the
   picture is and what it shows; `PUT /{id}/file` takes the bytes. The same two steps serve the web
   app now and the MCP tool later: the tool opens the declaration under the agent's sign-in and
   hands the person the upload page's link.
2. **The body is the picture.** The upload is the raw request body with a 10 MB cap read as a
   stream, so no multipart parser joins the dependencies.
3. **Read byte by byte, never re-encoded.** `research/image_intake.py` recognises PNG, JPEG and
   WebP from their bytes, reads their size from the headers, and drops the metadata segments:
   location, camera, text, XMP, IPTC and Content Credentials. A JPEG keeps only a rebuilt
   orientation, so a phone photograph stays upright. No imaging library is added: re-encoding would
   cost memory on the box (an 8,192-pixel square is 256 MB decoded) and change the pixels, and a
   reviewer sees every picture before it is shared.
4. **The AI mark is the IPTC digital source type.** ChatGPT, Firefly and other tools write
   `trainedAlgorithmicMedia` into their Content Credentials or XMP. Its presence is recorded, and a
   picture declared a photograph or drawing that carries it is refused. Its absence proves nothing,
   so the declaration stays the record of origin.
5. **Stored as a `MediaAsset`**, the table of the app's own generated pictures, private until
   approved and shared (`CRAFT_SHARED`) after; `ImageContribution` keeps the declaration and the
   review. Nothing shows a contributed picture on a page yet.
6. **Admins review**, through a new capability, `REVIEW_CONTRIBUTIONS` (Admin and Master Admin),
   because the owner asked for Admins to review others' contributions (decision 0101, item 12).
   Contributing uses `PROPOSE_KNOWLEDGE` (Researcher and above).
7. **The image module lives in `research`.** Media sits above services in the import layers, so the
   PNG size reader moved from `media/output.py` into `research/image_intake.py`, and media imports
   it from there.

## What follows

- The contribute page and the admin review screen: built (`/contributions/pictures`, `/admin/pictures`).
- Showing approved pictures on craft pages with their label ("Illustration, made with ChatGPT").
- The MCP tool (slice 2) that opens a declaration and returns the upload page's link.
- The owner's approval of the drafted terms texts (`docs/legal/`).

## Amended 2026-11-19 (owner)

- **Consent cannot be revoked.** A contributor can withdraw a picture only while it waits for its
  file or for review; an approved picture stays published, and `withdraw` refuses with 409.
- The declaration's text is drafted in `docs/legal/image-declaration.md`, with the contribution
  terms and the MCP terms of use beside it, for the owner and IIT's legal office.

## How this record is kept true

Its section Amended 2026-11-19 (owner) records the owner's amendment. Beyond that it is not edited
except to mark it superseded: a later choice is a new record that names this one, and the table
above links the two both ways. The parts later records changed stay here as they were decided; the
later record is the one that holds. It records the choice as taken on 2026-11-19; what the code does
today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
