# 0036. The asking screen: dictation, an optional craft, depth by role

The asking screen takes a typed or dictated question (the browser's Web Speech API), an optional
craft and the depth the server gives the reader's role, and sends `depth`, never `mode`. The ask box
offers no live call.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0030 The explainer contract](0030-explainer-contract.md) |
| The review that fixed it | [0038 Phase A review fixes](0038-phase-a-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

`docs/plans/answer-experience.md` sections 1.1 and 2.5 (owner-approved, section 8 final) replace
the ask box's Mode choice and the live voice call with: a question typed or dictated through the
browser's Web Speech API (no AI tokens), a craft that can be picked but never has to be, a depth
(Basic, Detailed, Expert) that starts from the reader's role, and the answer language. The
explainer contract (decision 0030) carries the server's reading back in the `understood` event.
Lane 0031 built the understanding step and depth on the server at the same time: its ask body is
`{question, depth|null, craftSlug|null, anyCraft, language|null}` (no `mode`; a null depth is the
role's default) and `/answers/config` lists `depths: [{depth, label}]` and `defaultDepth`. The
boards are the "Asking" and "Answer experience" pages of the design project.

## Decision

1. **Depth comes from the server, once.** The screen draws the config's `depths` with their
   labels and starts at its `defaultDepth` (`research/depth.default_depth` of the asker), so the
   role table has one home and the client mirrors nothing. A depth the reader picks wins and goes
   into the address (`?depth=`); before the config answers, or when it cannot be read, the request
   sends `depth: null` and the server applies the role's default. An off-contract depth list is
   logged and the choice is not drawn (`lib/askConfig.askDepthsOf`). `ask-choices-unit.spec.ts`
   reads `research/depth.py` and the config route to pin the plan's table and the two config keys.
2. **The request carries `depth`, never `mode`.** `VERIFIED` stays internal, so the "Research it
   live" offer after a stored-only answer is no longer drawn on `/ask`, and `lib/askConfig.ts`
   drops `modes`, `defaultMode` and `MODE_LABEL` (the client's `canAskDeep` goes with the Mode
   control).
3. **The craft is optional, and the picker says what was detected.** The picker is the
   `SearchableSelect` over the craft catalogue. Untouched, it reads "Any craft" and the server
   works the craft out. After the `understood` event that row reads "Kutch Ajrakh · detected"
   (every detected craft for a comparison), an explicit "Any craft" row appears above the list,
   and the `candidates` are one-tap buttons beside the picker. Choosing that explicit row asks
   with `anyCraft: true` (no craft assumed); it holds only for that question, so a new question is
   detected again (`pickForQuestion`). Picking a craft, a depth or a language while the asked
   question is still in the box asks again (`reasksOnChange`), the plan's "a wrong guess is one tap
   to change"; editing the question first leaves the change for the next Ask. The "Which craft?"
   stop is gone with `AMBIGUOUS`.
4. **`understood` reaches the current answer state.** `lib/answerStream.ts` parses it with the
   contract's `understoodShape` (off the contract it is logged and dropped) and keeps it as
   `AnswerState.understood`. The explainer UI lane (0037) owns the rest of the stream, so this is
   the one event added to the existing reducer.
5. **Dictation is one adapter and is drawn only where it can work.** `lib/dictation.ts` wraps the
   Web Speech API: the standard `SpeechRecognition`, else `webkitSpeechRecognition`; continuous,
   with interim results; the locale is the answer language with India as its region (`hi-IN`,
   `ta-IN`, ...). Words still being heard are written into the box live, after whatever was typed,
   within the 1000-character limit; the box is read-only while listening so typing cannot fight
   the recogniser. The mic is drawn after mount and only when the browser has the API; where the
   browser can say which languages it serves (`SpeechRecognition.available`), a language it calls
   unavailable gets no mic, and a `language-not-supported` refusal hides the mic for that language
   with one sentence. That is the plan's per-browser check, made by the browser itself instead of a
   list in the client that would go stale. Listening shows the mic filled and pulsing, moving bars
   (decoration: the API gives no audio level) and "Listening · हिन्दी"; under either reduced-motion
   switch the pulse is gone and the bars stand still, and the words carry the state. The mic stays
   the same button while listening (its name becomes "Stop dictation"), so keyboard focus is never
   dropped.
6. **No live call from the ask box.** The ask page no longer mounts `VoicePanel`; the voice code is
   untouched (lane 0035 switches the call off). "Ask from a photo" on the board is not drawn: no
   route serves it, and the screen hides what cannot work. The board's three notes under the
   composer are left out: they explain how the screen works.
7. **Layout.** The page widens to `max-w-6xl` for the composer and the explainer to come; the
   current answer view keeps its reading width inside it. The container hook `useAskScreen` holds
   the state and the asks, the components only draw, and every rule is a pure function in
   `lib/askCraft.ts`, `lib/askDepth.ts`, `lib/askRequest.ts` and `lib/dictation.ts`.

## Consequences

- The production E2E picks Detailed (the Researcher's default, `HYBRID` research) where it picked
  Hybrid, checks the Depth group instead of the Mode group, and checks `depth` in the request.
- Each target browser's dictation languages are still to be tried once by hand (plan 2.5); the
  runtime refusal path makes an unsupported language safe but not verified (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
