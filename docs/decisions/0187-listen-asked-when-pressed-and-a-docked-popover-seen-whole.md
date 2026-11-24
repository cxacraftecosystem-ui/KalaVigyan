# 0187. Listen asks only when it is pressed, a docked citation popover is seen whole, the client's closing `done` keeps the quiz offer, the Listen dock keeps its focus and the access roster scrolls at once under reduced motion

Listen and the film ask for a script only when the reader presses Listen or opens the film, for the
answer then shown, and a follow-up's answer closes the dock; a generated page's passage lets a
popover docked in its margin run past its foot; the stream's own closing `done` keeps what the
server said about the quiz; the dock's play button stays focusable while the next part is prepared
and its status line is always mounted; and Edit on the access roster scrolls at once under either
reduced-motion switch.

Date: 2026-11-24. Status: accepted (the lead's review-fix brief of 2026-11-24, web lane, after the
whole-codebase review of that day). It amends [decision 0176](0176-listen-plays-as-it-narrates-builds-wait-for-the-api-runs-are-kept.md),
item 4 (the feed the dock and the film share), [decision 0183](0183-the-shared-template-draws-the-approved-page.md),
item 4 (a margin beside each run, which the kit docks the popover into), and
[decision 0141](0141-design-system-and-answer-screens-without-debt.md), item 6 (`done` carries
`quizAvailable`) and item 12 (scripted scrolls read the switches). The contracts are
`docs/contracts/frontend.md` and `docs/contracts/voice.md` (Listen), `docs/contracts/explainer.md`
(the quiz) and `docs/contracts/monograph-renderer.md` (margin notes).

| For | Read |
|---|---|
| The feed the dock and the film share, and "Preparing the next part…" | [decision 0176](0176-listen-plays-as-it-narrates-builds-wait-for-the-api-runs-are-kept.md) |
| Margin notes beside each run of a generated page | [decision 0183](0183-the-shared-template-draws-the-approved-page.md) |
| `done.quizAvailable`, and anchors scrolled through `scrollToAnchor` | [decision 0141](0141-design-system-and-answer-screens-without-debt.md) |
| Motion only while neither switch is on | [decision 0092](0092-design-system.md), and the skill `kalavigyan-design`, section 6 |
| Every decision, by group | [README.md](README.md) |

## Context

- **Listen narrated a follow-up nobody asked to hear.** Since decision 0176 the feed fetched the
  script in an effect keyed on the answer id and a count of requests. On /ask a follow-up keeps the
  explainer view mounted (`useAnswerStream.follow` leaves its round alone), sets the answer id to
  null and, at the follow-up's `done`, to the new answer's. The count was already 1, so the effect
  asked `GET /answers/{B}/listen` at once: the server narrates the first block before it answers,
  holds the reader's `VOICE_SECONDS` and makes the rest in the background. A script still playing
  was cleared under the dock, so the audio stopped mid-sentence; B's script then arrived while the
  status was still playing, the reset that runs only from loading never ran, and B started at the
  track A had reached, or sat on Pause with nothing to play when B had fewer tracks.
- **A docked popover was cut at its passage's foot.** Since decision 0183 every run of a generated
  page is a spread with `aside.margin`. From 1200px the kit's `place()` appends `#kv-pop` there as
  `position: absolute` at the numeral's height, and every passage is `div.bx.bx-pt > div.screen`,
  which the kit clips (`.bx-pt .screen{ overflow: clip; }`). A popover opened from a passage's last
  paragraph lost its quote, reliability and Open the source below the passage's padding, 32 px on a
  head passage and none on the others, and could not be scrolled into view.
- **The client's closing `done` erased the quiz offer.** `useAnswerStream` ends every stream that
  was not stopped with `done {answerId: null}`. `reduceSettling` kept the answer id but wrote
  `quizAvailable: undefined ?? null`, so Check yourself asked `GET /answers/{id}/quiz` for every
  answer without a quiz, and the route rebuilt the shown explainer and its quiz to answer 204.
- **The dock dropped focus at a narration gap.** At `waiting` the round play button took
  `disabled`, so focus fell to the page and Space scrolled it; nothing gave focus back when the next
  part played. Its status line was mounted together with its text, which many screen readers do not
  announce.
- **The access roster scrolled smoothly under reduced motion.** Edit called
  `scrollIntoView({ behavior: "smooth" })`, which the reduced-motion CSS's
  `scroll-behavior: auto !important` does not override; every other scripted smooth scroll asks a
  switch first.

## Decision

1. **A script is asked for when Listen is pressed, for the answer then shown.**
   `useListenScript.request` makes the ask, `{answerId, language}`, and fetches it there and then;
   nothing fetches when the answer id changes. The feed holds one `HeldScript` (`ask`, `script`,
   `load`, `error`, `stalled`): a reply or a poll changes it only while it still holds the ask the
   reply answers (`replied`), and the feed shows it only for the answer and language on screen,
   else nothing held (`heldFor`), so polling stops and nothing of one answer is played for another.
   `useListen` stops when the answer id or language changes, which closes the dock, clears the
   sentence being read and puts the track back to the first; the Listen control returns after the
   follow-up's `done`, and the film, a modal over the answer, asks on opening as before. Fetching
   in an effect keyed on the ask, and clearing the feed in an effect on the answer id, were the
   alternatives: asking in the press itself makes an unasked fetch impossible by construction, and
   deriving what is shown needs no second render.
2. **A docked popover is seen whole.** `documentPage.css`, the app's own sheet, sets
   `.kv-monograph .bx-pt > .screen:has(.pop.docked){ overflow-y: visible; }`. `overflow-x` stays
   `clip` (clip with visible is a valid pair, so nothing scrolls sideways), and the popover's
   `--z-popover` draws it over the next passage. The kit files stay as approved. Lifting the clip
   from every passage was the alternative; the clip is kept wherever no popover is docked.
3. **The closing `done` keeps the quiz offer.** `reduceSettling` writes
   `quizAvailable: event.data.quizAvailable ?? state.quizAvailable`. `askingExplainer`,
   `followingExplainer` and `explainerStateOf` already start every new answer at `null`, so a
   stream whose `done` cannot say still asks once.
4. **The dock keeps its control.** While the audio is being prepared the round button is
   `aria-disabled`, styled as the film's (`aria-disabled:cursor-wait aria-disabled:bg-sunk
   aria-disabled:text-ink-3`), and keeps focus; `useListen.toggle` does nothing while loading or
   waiting, where it used to call `start()` and set playing on the ended track. One
   `role="status"` line is always mounted in the player and only its text changes; it is visually
   hidden while the clock shows.
5. **Every scripted smooth scroll has an instant side.** The roster's Edit scrolls with
   `motionAllowedNow() ? "smooth" : "auto"`, as `scrollToAnchor` does, and the motion spec fails on
   any `"smooth"` in `app/`, `components/` or `lib/` that is not one side of a choice whose other
   side is `"auto"` (it walks the files through the design guard's `scannedFiles`).

## Consequences

- A follow-up's answer costs no narration until its reader presses Listen on it; each press makes
  one ask, as before decision 0176.
- A reader listening while asking a follow-up loses the dock when the follow-up starts, not when it
  finishes, and Listen on the new answer reads it from its first block.
- The release check's popover step (`e2e/release/documentControls.ts`) still checks only that the
  popover opens and how; that a popover docked under a passage's last sentence is seen whole is
  checked at 1440 by the template spec, with the kit's own script and sheets.
- Check yourself no longer asks for answers whose stream said there is none; the 204 stays for a
  stream from a backend that leaves the flag out.
- Nothing is added to or removed from `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`frontend/e2e/listen-pending-unit.spec.ts`, `learning-screens-unit.spec.ts`,
`monograph-template-unit.spec.ts` and `motion-unit.spec.ts`.
