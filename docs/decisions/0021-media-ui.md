# 0021. Media UI: Image and Video on the craft page's process stages

The craft page's process stages offer Image and Video only as the options route allows, with one
idempotency key per press and polling that follows the server's status. The illustration sits beside
the evidence and never in it, its links are renewed, downloads take the server's file name, and the
CSP names the bucket.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0092 The KalaVigyan design system: Alum & Indigo](0092-design-system.md): its colour, type and motion choices; its behaviour stands |
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [media.md](../contracts/media.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the media contract (`docs/contracts/media.md`): `GET /api/media/options`
lists the kinds the asker may still make today and the stages whose server-derived claim set is
large enough, `POST /api/media/jobs` takes a kind, a stage and an idempotency key, and
`GET /api/media/jobs/{id}` answers the job with `pollAfterSeconds` while it is open and the
labelled asset when it succeeds. PLAN 11 asks for buttons that exist only when the stage has
enough claims and the role has quota, polling every 3 s with the ProgressBar, every asset labelled
"AI illustration" with model and date and never in the evidence column, alt text from the claims,
downloads named by the naming convention, and sharing by professors with a second professor's
sign-off for an asset that depicts a named cluster. The media backend (0018) is built at the same
time, and the contract leaves the sharing route to a later governance lane. PLAN 0 and the owner
rules bind: no gap admissions or how-it-works copy, a control that cannot work is hidden, guards
fail closed, no code comments.

## Decision

1. **One store per craft page, above the tabs.** `lib/craftMedia.ts` (`CraftMedia`) holds the
   options and one slot per stage and kind (`<stageId>:<IMAGE|VIDEO>`), and is created by
   `components/craft/useStageMedia.tsx` in the craft page's panels. The Process tab unmounts when
   another tab opens, so a job held inside a stage card would be lost on a tab switch; the store
   lives with the page instead. Its adapters (the media routes, session storage, the key maker,
   the clock and the timer) are passed in, so the unit specs drive whole jobs with fakes, as the
   voice controller is driven (decision 0020). Teardown waits one task, so a strict-mode remount
   keeps the same jobs and timers.
2. **Buttons come only from the options route.** A stage draws Image or Video exactly for the
   kinds `offeredKinds` returns: listed for that stage, listed among the kinds, units left. A
   failed or off-contract options answer offers nothing (the API's guard stays the last word).
   Options are re-read after every job settles and after every refused press, so a spent daily
   allowance removes the button. Each button says what is left today ("4 left"), the cap rule of
   the frontend skill; an unlimited allowance says nothing. The voice dock's `offer_image` now
   lands on a stage that has the button.
3. **One idempotency key per press.** `newIdempotencyKey` makes `media:<uuid>` (42 characters,
   inside the backend's `IDEMPOTENCY_KEY_PATTERN`, which a seam test reads from
   `schemas/media.py`). A press the server answered with a refusal shows the server's sentence and
   the next press makes a new key. A press that got no answer (a network failure, or 500, 502 or
   504) keeps its key, and Try again sends the same request, so a job the server did create is
   answered again rather than made twice. A second press while a job is open does nothing.
4. **Polling follows the server.** An open job is polled after its own `pollAfterSeconds` (3 s,
   `POLL_SECONDS`), so the interval has one home. Two missed polls in a row are retried silently;
   the third shows "Couldn't reach the server." with Try again, which resumes the same job. After
   15 minutes of watching (`MEDIA_WAIT_LIMIT_SECONDS`: three attempts of the 240 s timeout plus a
   queue's wait) polling stops with "Still working on it." and Check again, so a stuck worker
   does not keep a tab polling for ever. A 404 on a poll ends the slot with the server's sentence.
5. **Progress is the server's status, not a guess.** The ProgressBar moves one step of four:
   starting (the POST in flight), queued, running, done, with the word beside it (Queued,
   Drawing… or Rendering…, Trying again… on a retried attempt). No time-based estimate is drawn:
   there is no measured duration to base one on, and a bar that moves on its own would claim
   progress the server has not reported. The width eases by CSS, which both reduced-motion
   switches reach.
6. **Every response is checked at the boundary.** `checkedMediaJob` repeats the backend model's
   status rules the screen relies on (asset exactly when succeeded, a reason exactly when failed or
   blocked, a poll interval exactly while open, the asset's type and file name matching the kind);
   `checkedMediaOptions` checks the craft and the kinds; the store checks that a job answers for
   the stage, kind and craft it was asked for. A broken answer shows "Couldn't load the
   illustration." and logs the failing path; nothing half-drawn.
7. **The illustration sits beside the evidence, never in it.** `ProcessTimeline` takes a
   `stageMedia` slot drawn after the stage card inside the stage's panel, under a divider, with
   its own heading for screen readers; the stage card, which holds the cited claims, materials,
   conditions and reactions, knows nothing of media (a unit spec reads both files). The figure
   carries the server's `label.text` ("AI illustration") in a neutral chip that looks like no
   evidence badge, the model id and the generation day (`formatCalendarDay`, which reads the IST
   day as a calendar day so no time zone moves it), and the server's alt text: `alt` on an image,
   a described-by paragraph on a video. Images use `next/image` unoptimized, since a presigned
   URL changes on every read and has nothing to optimise.
8. **Links are renewed, never trusted stale.** A presigned URL lives 900 s. A download first asks
   for the job again when the URL has a minute or less left; an image or video that fails to load
   with an expired URL is renewed once quietly, and otherwise shows "Couldn't load the
   illustration." with Try again. Remembered jobs (below) are re-read on arrival, so their URLs
   are fresh.
9. **Downloads use the server's file name.** The asset is fetched as a blob and saved through an
   object URL with `download` set to `fileName`, because a cross-origin link ignores `download`
   and the presigned URL's disposition is `inline`. `lib/download.ts` (`saveBlob`,
   `downloadFile`) is now the one place a file is handed to the browser; the recovery-codes
   download uses it too. The client never builds a media name.
10. **The CSP names the bucket.** `connect-src` (the blob download), `img-src` and `media-src`
    name the regional virtual-hosted host of the Terraform bucket
    (`https://kalavigyan-media-626159998512.s3.ap-south-1.amazonaws.com`), as the contract says;
    `img-src` keeps `'self'` and `data:` (the two-step QR code), `media-src` keeps `'self'` (relay
    speech). A unit spec derives the host from `infra/terraform/variables.tf`, so renaming the
    bucket fails it. The contract now pins that host for the presigned URLs.
11. **A returning reader sees their job.** Job ids are kept per craft in session storage
    (`kalavigyan_media_jobs:<slug>`, `lib/mediaJobMemory.ts`), validated on read, so a reload or
    Back during or after a job shows it again instead of losing a spent unit. Failed and blocked
    jobs, and ids the server no longer answers for, are forgotten. Storage that throws or is
    empty only means nothing is resumed.
12. **Sharing is drawn only when the server offers it.** No sharing route exists yet, and the
    contract left it to the governance lane, so this lane specifies the client side in the
    contract and hides it until the server sends it: `MediaAssetView.sharing` (optional;
    `{actions, awaitingSecondProfessor}`) and `POST /api/media/assets/{id}/sharing` with
    `{action: SHARE | UNSHARE}` answering the asset. A sharing control is drawn only for a
    professor or master admin (`canShareMedia`, held against `Capability.SHARE_MEDIA` in
    `core/roles.py` by a seam test) and only for the step the server lists: Share for a private
    asset nobody has signed, Withdraw while it awaits a second professor, Stop sharing once
    shared, with the state in words beside it. Buttons were chosen over a switch because the
    named-cluster case has a third state that is neither on nor off. A disabled or explained
    control was rejected: it would be a gap admission on a professor's screen.
13. **No style hint yet.** The contract accepts an optional style hint; the first UI sends
    `null`. A free-text box on every stage is a form with its own refusals (the banned words), and
    the owner asked for concise screens; it waits for a request.
14. **Copy and controls.** Image and Video are secondary buttons with an icon in an
    `ActionGroup`; Download, Share and Try again are media card actions (`MediaActionButton`,
    ported from the designer portal's pair: purple-50 ground, purple-600 edge, purple-800 ink,
    and their dark pair), icon and word, 44 px on touch. A polite status region per stage says
    what changed (Image: Drawing…, Image ready.). Server refusals are shown verbatim.

## Consequences

- Nothing is drawn until lane 0018 serves `GET /api/media/options`; until then the options call
  answers 404 and no stage has a button.
- Sharing stays hidden until the governance lane sends `sharing` and serves the sharing route, and
  a second professor's sign-off needs that lane's queue, since a job is visible to its requester
  only.
- The figure, buttons and downloads have not run in a browser, and the CSP's new `img-src` and
  `media-src` are unverified against every page. Each item is in `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
