# 0076. The release gate looks at what the reader sees

The production E2E captures a page only once it is still, and fails a screen on what is wrong rather
than on its length, at five widths in light and dark. It can run on a preview, checks the Professor
and Admin screens only when their secrets exist and only in production, and adds no dependency.

Date: 2026-11-18. Status: accepted. Extends decision 0029.

| For | Read |
|---|---|
| What it builds on | [0029 E2E against production, on dispatch, as one Researcher account](0029-e2e-production-run.md): the Professor and Admin screens it left not covered |
| Every decision, by group | [README.md](README.md) |

## Context

The E2E production run passed every screen on 18 November while its screenshots showed a landing
headline still fading in, "1 4 1 4" after a lede sentence, pictures in empty frames and 45 repeated
sentences in the Indigo answer. Its phone and tablet Region tab and tablet craft index screenshots
also end in dozens of blank tiles, but those are not empty page: Chromium stopped painting each
very tall full-page screenshot partway down and filled the rest with background. Two different
tablet pages stop in the same staircase inside the same tile, phone text is cut mid-word along a
rectangular edge, the phone Region tab is blank from device row 131,072, and the Desktop Region tab
(pixel ratio 1) painted in full, so the limit is in device pixels. A local check reproduced it: a
60,000 px page at 390 px and ratio 2.625 painted only 103,632 of its 157,500 rows in one capture,
while an eight-screen clip of the same page painted in full. The run's checks read the DOM
and the stream, not the picture, and it captured 700 ms after network idle. It ran only at 390,
834 and 1440, light theme, Chromium, against production. Plan task 1A-11 asked for more gates and
a height cap; the two critiques of the plan asked instead not to cap page height in general (a
cited monograph should be long), to add 360 and 1920, phone and tablet answers, dark, and WebKit,
and noted that a Vercel preview cannot be driven without a CORS rule for its origin and a way past
Vercel's deployment protection.

## Decision

1. **Capture when the page is still.** Before each capture the run scrolls to the end in steps of
   0.8 screens, waits for the network to be quiet (no open request, event streams and media
   aside, for 500 ms), for fonts, for every visible `molecule-3d` to leave `waiting` and
   `loading`, and for busy text to clear, then returns to the top and waits for finite CSS and
   Web Animations to end (`e2e/production/capture.ts`).
2. **Gates on what is wrong, not on length.** A screen or answer fails on any of these
   (`sight.ts` reads the page, `gates.ts` judges, `tiles.ts` reads the screenshot):
   - a headline word, or the largest text or picture in the first screen, below 99% opacity;
   - a screen-high tile whose pixels are 99.9% one colour (channels within 4); a last tile shorter
     than half a screen is not judged. The full-page screenshot is scanned first; when it has a flat
     tile, every tile from the one before it is judged again from clipped captures of at most eight
     screens (`fullPage` with `clip`), which Chromium paints in full. A tile flat only in the
     full-page screenshot is a note on the screen, not a failure, so page height is never capped
     through the back door;
   - a citation cluster (adjacent chips) that repeats a source number;
   - inside an answer view, a visible sentence or a picture (Wikimedia thumbnails folded to their
     file) shown more than once;
   - a picture of at least 48 px that never loaded;
   - text that starts with Loading, Searching or Checking still on screen once the page settled;
   - a 3D molecule that failed or never reported ready;
   - a page not drawn in the run's theme;
   - gap copy, now also "not enough cited evidence", "not curated", "yet to be ..." and "nothing
     here yet".

   Height is capped only on the Region tab: three screens before "All measurements" (the whole
   panel while there is no such control).
3. **The matrix.** Screens run at 1920, 1440, 834, 390 and 360, each light and dark (ten
   Chromium projects, `e2e/production/matrix.ts`). Questions run once, at 1440 light; each stored
   answer is then opened at 834 and 390, light and dark, from the same session. A preview run adds
   a WebKit iPhone project. Screens added: Sign up, Forgot password, Privacy, Session ended, the
   Sources and All evidence tabs, Agra Marble Inlay (empty), Cane Bamboo Craft (All India),
   Sanganeri Hand Block Printing, an unknown craft (its 404 and alert expected), Compare idle and
   with Kutch Ajrakh and Bagru (a pair without a comparison fails), and Saved.
4. **Previews.** The workflow takes a `base_url`. The config refuses any site but
   `https://kalavigyan.vercel.app` and `https://kalavigyan-<9 characters>-cxacraftecosystem-8028s-projects.vercel.app`,
   because the run types the E2E passwords into it. With `VERCEL_AUTOMATION_BYPASS_SECRET` set,
   the run sends `x-vercel-protection-bypass` once to the preview origin through the context's
   request client, which stores Vercel's bypass cookie; the token is never sent elsewhere, as
   `extraHTTPHeaders` would. The API accepts the preview origin when
   `BACKEND_CORS_PREVIEW_PROJECT` and `BACKEND_CORS_PREVIEW_SCOPE` are both set: the rule is built
   from the two slugs, escaped, as `https://<project>-[a-z0-9]{9}-<scope>\.vercel\.app`, never a
   pattern on `vercel.app`; a half-set pair or a non-slug value stops the API at start. Previews
   stay off until the pair is set: `seed_secrets.py` writes it only with `--preview-cors`, so a
   reseed never turns previews back on. Branch aliases (`-git-`) are not accepted, since the
   project has no Git link. Browser calls go through the web app's own `/api` proxy, so the rule
   matters for any direct call and keeps the backend's CORS answer true for previews. Google
   refuses every preview origin (its authorised origins take no wildcard), so on a preview the run
   expects Google's origin refusal on Login and Sign up (`googleRefusesPreview` in `preview.ts`) and
   nothing else from Google; a production run expects neither.
5. **Professor and Admin screens on secrets.** `/lessons` and `/admin` run at 1440 light only when
   `E2E_PROFESSOR_*` or `E2E_ADMIN_*` (email, password, TOTP secret) exist, and are skipped
   otherwise. They run only against production: a preview can be built from any branch, so a
   preview run gets neither the secrets nor the screens (`roleSiteRefusal` in `preview.ts`). The
   run computes the RFC 6238 code from the secret (`twoStep.ts`). This replaces decision 0029's
   "not covered" for those roles.
6. **No new dependency.** The PNG reader is a streaming inflate over `node:zlib` with the five
   PNG filters, so a 200,000-row phone screenshot is read row by row; `sharp` is only Next's
   optional dependency.

## Consequences

- A run is 13 tests (14 on a preview) on four workers and may take up to 90 minutes.
- A preview run needs the two backend settings in Parameter Store and a backend deploy, and the
  bypass secret in GitHub (`docs/RUNBOOK.md`, E2E production run). The media bucket's CORS still
  lists only production and localhost, so media fetched by script on a preview is refused.
- The gates are proved with fixtures in `frontend/e2e/production-checks-unit.spec.ts`: a
  half-built headline, "1 4 1 4", a blank tile, a tile blank only in the full-page screenshot,
  repeated sentences and pictures, busy text, the Region cap, previews, Google's preview refusal and
  RFC 6238 vectors.
- A tall page with a flat tile costs one more capture per eight screens past it; the saved
  full-page screenshot is still the one Chromium painted, so its blank end is explained by the note.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
