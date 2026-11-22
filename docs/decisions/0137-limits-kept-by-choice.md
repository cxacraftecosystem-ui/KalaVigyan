# 0137. Limits kept by choice

Nine limits that the debt register carried are kept on purpose: each is the safer or simpler side
of a real trade-off, and nothing would be better if it were removed today. They leave the register
and are recorded here with what would change the choice.

Date: 2026-11-22. Status: accepted (the lead, in the register review of 2026-11-22; within the
owner's go-ahead of 2026-11-22 to clear the register "not just for this round, also for all
time").

| For | Read |
|---|---|
| What is still below standard | [TECH_DEBT.md](../TECH_DEBT.md) |
| The sandboxed explainer frame | [decision 0055](0055-generated-explainers.md), [decision 0061](0061-phase-c-review-fixes.md) |
| Versions are never rewritten | [decision 0063](0063-follow-ups-versions-and-alerts.md) |
| No per-answer caps for now | [decision 0093](0093-no-caps-for-now.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The register's rule is that an entry is something knowingly below standard with a way to clear
it. On 2026-11-22 every entry was checked against the code. Nine were found to be choices, not
shortfalls: their own text says nothing is needed unless a named condition arises, or the change
that would remove them costs more than the limit. Keeping them in the register hid the work that
is truly open among notes that will never be acted on.

## Decision

Each limit below stays as it is until its condition arises; the change that meets the condition
removes the limit and supersedes its row here.

| Limit | Why it is kept | What would change it |
|---|---|---|
| A generated explainer's frame reports its own height (`FRAME_SIZER` in `frontend/lib/sandboxFrame.ts`), so code that slipped a `postMessage` past the static check could post another height. | The page cannot measure a frame of another origin; the message moves only that frame's height, clamped to 120 to 1,200 px. | The bounds proving wrong in production. |
| `frame-src` allows `https://accounts.google.com/gsi/`, so a generated explainer that navigated itself there (refused by the static check) would load Google's page in its own sandboxed frame. | `frame-src 'none'` would break the Google sign-in button; no other address loads. | A separate origin for the sign-in screens, or sign-in leaving the GSI button. |
| The sandbox's static check (`backend/app/research/sandbox.py`) scans script text with patterns, not a JavaScript parser, so it refuses some good code and cannot follow every alias of the window. | The frame's sandbox, content policy and guard are the boundary; the check is a filter that fails closed, and no JavaScript parser runs on the server. | Production regenerations showing it refusing good explainers, or an escape it misses: then a tokenizer behind one adapter. |
| `@elevenlabs/client` loads its AudioWorklet processors from `blob:` and `data:` URLs. | The content policy has no `script-src`, so they load. | The change that adds `script-src` copies `node_modules/@elevenlabs/client/worklets/*` into `public/` at build time and passes `workletPaths` from `frontend/lib/elevenLabsAgent.ts`. |
| The understood line moves focus to its control under the question box by element id (`components/ask/AskOptions.focusAskOption`). | Threading refs through the asking screen and the explainer for one focus call is heavier than an id. | The asking screen gaining a focus API (refs from `useAskScreen`). |
| PubChem record sources stored before decision 0042 keep their random ids. | Ids cited by stored claims and pieces must not move, and every reader takes the id from `Compound.sourceId`. | A reader deriving the id from the CID: then a migration rewrites them. |
| A read-back explainer is hidden when its piece is hidden or when a hidden generated piece has its content hash. | Versions are never rewritten (decision 0063), and two explainers never share a content hash because each carries its build time. | Pieces being copied between answers. |
| Compare and the quiz options change layout at viewport breakpoints, not at the width of the section they sit in. | Every other block uses viewport breakpoints, and the section fills the reading column at every width. | A block drawn in a narrower place (a lesson slide, a side panel): then container queries. |
| Fixed rules choose quiz questions, distractors and compare cells (`backend/app/research/quiz.py`), so a distractor that also fits the blank, or a true but off-point cell, is not caught. | The rules keep every value cited and the output the same for every reader at no model cost. | An optional plan-model pass that may only drop offered distractors and reorder offered facts, measured against the rules on the known-answer questions. |

## Consequences

- The debt register holds only work that is open or blocked on something outside the repository.
- A change that meets a row's condition removes the limit and marks the row superseded here.

## How this record is kept true

It is not edited after acceptance except to mark a row superseded: a later choice is a new record
that names this one. It records the choice as taken on 2026-11-22; what the code does today is in
[ARCHITECTURE.md](../ARCHITECTURE.md) and the [contracts](../contracts/README.md).
