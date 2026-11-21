# 0100. The Kutch Ajrakh craft page is the hand-built monograph, served as built

The Kutch Ajrakh craft page was the owner's approved hand-built monograph, served as a static file
changed only to fit the app, until the template renderer matched it. That ended on 2026-11-20, when
decision 0106's React renderer passed the parity proof.

Date: 2026-11-19. Status: accepted. Overrides the craft page renderer (decisions 0071, 0095 and
0098) for one craft, Kutch Ajrakh; every other craft keeps it.

| For | Read |
|---|---|
| What ended it | [0106 One monograph template for every page, reached through fragments](0106-one-monograph-template-for-every-page.md): its renderer passed the parity proof on 2026-11-20, so the craft page draws its stored document |
| What it supersedes in part | [0071 The craft page reads as a curated reference](0071-craft-page-rebuild.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| What it supersedes in part | [0095 The craft page becomes a monograph in chapters, public to read, built without a question](0095-craft-page-chapters.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| What it supersedes in part | [0098 How the craft page chapters were built: the readings taken where the contract was open](0098-craft-page-chapters-build.md): its renderer, for Kutch Ajrakh only, until 2026-11-20 |
| Every decision, by group | [README.md](README.md) |

## Context

The owner approved a finished, hand-built Kutch Ajrakh page (the answer "How does Ajrakh work?"
and its monograph, built from the curation dossier by the scripts in the `_cons` working folder:
`build.py`, `build2.py`, `build3.py`, `kv.js`, `kv.css`) and asked for it to be the live Kutch
Ajrakh craft page exactly as it looks, now, not rebuilt in React.

## Decision

1. **The page is a static file.** It lives at `frontend/public/monographs/kutch-ajrakh/index.html`
   with its ten pictures in `img/` beside it. `CRAFT_MONOGRAPHS` in `frontend/next.config.ts` maps
   the slug `Kutch-Ajrakh` to that file, and a `beforeFiles` rewrite serves it at
   `/crafts/Kutch-Ajrakh` to every reader, signed in or not. Next.js matches rewrites without
   regard to case, so `/crafts/kutch-ajrakh` serves it too. The edition addresses
   (`/crafts/Kutch-Ajrakh/v1`) and every other craft keep the craft page renderer.
2. **Changed only to fit the app.** Line endings are LF, picture paths are absolute
   (`/monographs/kutch-ajrakh/img/...`), the brand goes to `/`, and each Ask next question is a
   link to `/ask?q=<question>&craft=Kutch-Ajrakh` instead of a demonstration toast, so a signed-out
   reader is sent to sign in as on any ask link. Content, design and animation are as approved.
   The citation texts keep their full `https://kalavigyan.vercel.app` addresses, since a copied
   citation needs one.
3. **The global headers apply.** The app's Content-Security-Policy sets no `script-src`,
   `style-src` or `font-src`, so the inline scripts and styles and the Google Fonts load; the
   pictures are `'self'`.
4. **This holds until the renderer matches it.** It is the Kutch Ajrakh page until the chapter
   renderer reproduces it. Removing the `Kutch-Ajrakh` entry from `CRAFT_MONOGRAPHS` returns the
   craft to the renderer.
5. **The dossier stays the source of facts.** `backend/app/data/curation/Kutch-Ajrakh.json` is
   still where the facts live. A dossier change does not reach this page by itself: rebuild the
   page from the `_cons` scripts, then copy it in again with the same four changes.

`e2e/craft-monograph-unit.spec.ts` checks the rewrite, the title, the pictures and the Ask next
links, and that other crafts are not rewritten.

## Ended (2026-11-20)

The React renderer of decision 0106 passed the parity proof at 360, 834 and 1440 in light and dark
(text, all 31 chapters, interactions; run 44617385866), so `/crafts/Kutch-Ajrakh` draws its stored
document like every other craft and the rewrite is gone. The approved file stays at
`/monographs/kutch-ajrakh/` as the parity reference, served with `X-Robots-Tag: noindex`;
`e2e/craft-monograph-unit.spec.ts` checks that arrangement.

## How this record is kept true

Its section Ended (2026-11-20) records how the override ended. Beyond that it is not edited except
to mark it superseded: a later choice is a new record that names this one, and the table above links
the two both ways. The parts later records changed stay here as they were decided; the later record
is the one that holds. It records the choice as taken on 2026-11-19; what the code does today is in
[ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
