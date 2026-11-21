# 0061. Phase C review fixes

Phase C's review fixed thirteen issues: the frame blocks peer connections in every browser, the
static check reads markup as a browser does and runs in linear time, and every generated explainer
shown can be hidden. The ElevenLabs download is bounded, film mode reaches production, and the
production E2E proves the phase.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The lanes it reviewed | [0055](0055-generated-explainers.md), [0056](0056-what-if-lab.md), [0057](0057-zoom-story-and-timeline-map.md), [0058](0058-elevenlabs-music-sound-image-video.md), [0059](0059-sandbox-and-what-if-renderers.md) and [0060](0060-zoom-timeline-and-film-renderers.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase C of `docs/plans/answer-experience.md` ("Play", owner-approved, section 8 final) was built
by lanes 0055 to 0060 to decision 0054's contract. Its review found thirteen issues: a frame that
could still reach the network through WebRTC, a parser difference that switched off every script
rule, numerals written against letters, quadratic patterns run on the event loop, a download that
read an unbounded body, generated explainers that could never be hidden or were shown again after
hiding, a Music and sound switch nothing could reach, a Mute that left the music playing on iOS, a
failed score with no message and a zoom level drawn over a map that did not show its district.
Decisions 0055 to 0060 left joining the four kinds to `BUILT_BLOCK_KINDS` to this review.

## Decision

1. **The four kinds are built.** `simulation`, `what_if`, `zoom_story` and `timeline_map` join
   `BUILT_BLOCK_KINDS` in `research/explainer.py` and `lib/explainerContract.ts` in one change, so
   `from_registry` starts their builders and the parser and stream take them. Tests that used a
   phase C kind as the example of an unbuilt one now use `artisan_voice`, and the simulation tests
   no longer patch the built kinds.
2. **The frame blocks peer connections in every browser.** `SANDBOX_CSP` gains `webrtc 'block'`
   on both sides and in the fixture (the plan's policy plus that directive). Chromium 158 does not
   recognise the directive (it logs a console error and a STUN request still leaves the frame), so
   the frame document gains a fixed script of the client's own before the sizer, `FRAME_GUARD`: it
   deletes `RTCPeerConnection` and `webkitRTCPeerConnection`, makes `contentWindow` and
   `contentDocument` of every frame-making element read as null, and removes any frame, object or
   embed the code adds, so no nested realm brings the constructor back. The production screens walk
   ignores exactly the unrecognised-directive console error from `about:srcdoc`.
3. **The static check reads markup as a browser does and closes the reflection routes.** A
   self-closed `<script/>` or `<style/>` is a `MARKUP` problem and its body is still read as script
   or style (Python's parser ended the element at once; a browser does not). The `API` rule refuses
   the reflection names (`getOwnPropertyDescriptor(s)`, `getOwnPropertyNames`, `getPrototypeOf`,
   `setPrototypeOf`, `defineProperty`, `defineProperties`), the window's other names
   (`defaultView`, `contentWindow`, `contentDocument`, an event's `.view`), `window`, `self` or
   `globalThis` used as a value, and `this` handed on as one; the `URL` rule refuses `stun:`,
   `stuns:`, `turn:` and `turns:` addresses and a `url(` that does not close. The check is split
   into `research/sandbox.py`, `sandbox_markup.py` and `sandbox_numbers.py` under the file budget.
4. **Shown numbers are read as figures are read everywhere.** Shown text, text attributes and CSS
   strings take their numerals from `quotes.numbers_in`, so `500km`, `18th` and `1868AD` are checked,
   and a run of three or more digits inside a formula-like word (`AD1868`) too; code numerals keep
   letters after them unless they are a CSS or canvas unit (`CODE_UNITS`); `start` is a numeric
   attribute; the numbers of `counter-reset`, `counter-set` and `counter-increment` must be data
   values. The runtime guard the review offered (refuse any shown numeral not in `kv-data`) is not
   built: it would hide the fixture's own explainer as soon as its slider moves, because the code
   rightly shows products of a data value and the slider's position. The contract now says the
   check reads written numerals, not computed numbers, and the gap is a debt entry under 0054.
5. **The check runs in linear time on a bounded draft.** `CSS_URL` matches a quoted or unquoted
   target with no lazy scan, every quantifier that could backtrack is possessive, and a draft
   longer than `SIMULATION_HTML_MAX_CHARS` (12,000, the prompt's limit, moved to
   `research/simulation_draft`) is a `SIZE` problem before any scan, so the redraft is told why; a
   reply past 200 KiB is off its schema. 8,000 unclosed `url(` now take milliseconds, not seconds.
6. **Every generated explainer shown can be hidden, and stays hidden.** `piece_store.kept_pieces`
   keeps a generated explainer from any section that built one, under its cross-craft
   `concept:<slug>` slot (`knowledge_pieces.concept_slot`), including an any-craft answer, a facet
   with no topic and a follow-up's deepened section (`BuiltSection.deepened`, whose other blocks are
   still not pieces). `set_simulation_hidden` finds the piece by the block's own id or reuse mark,
   then by its content hash (a block a later version carries), and otherwise keeps the block as its
   piece before marking it. `with_hidden_marks` marks a block hidden by its piece or by any hidden
   generated explainer piece with its content hash, and `GET /api/explainers/{id}` and
   `.../versions/{n}` now pass the stored explainer through it. Migration
   `0024_piece_content_hash_index` indexes `KnowledgePiece.contentHash`. A hidden explainer is left
   out entirely for readers below Professor (no wrapper, no reuse note), and Hide is offered only
   when the block can be a piece (its values rest on a claim, or it was placed from one).
7. **The ElevenLabs download is bounded before it is read.** `providers/elevenlabs_download`
   fetches a Flows `content_url` only from `storage.googleapis.com` (the reference's example host)
   over https with no credentials or port, refuses a declared `Content-Length` over the limit,
   streams the body and stops as soon as it passes 64 MB.
8. **Film mode reaches production.** The ask screen passes `config.filmScore` to `ExplainerView`,
   so Music and sound appears where `/answers/config` offers it. Mute sets `muted` on the bed and the
   cues as well as the narration (`filmSound.filmLevels`, `applyLevel`), so it holds on iOS. A
   score that fails to load turns the switch off and says why under it with `role="alert"`
   ("Couldn't load the music. Try again." or the route's detail), cleared on the next toggle.
   `FilmPlayer` is split into the dialog and `FilmPlayerBody` so the offer can be rendered in a spec.
9. **A zoom district missing from the shapes draws no map.** `ZoomDistrictMap` returns nothing
   when the district's LGD is not among the shapes; the level keeps its heading and cited sentence.
10. **The production E2E proves the phase.** A fourth known-answer question, "How does indigo turn
    blue on Kutch Ajrakh cloth?" at Expert depth, passes when every generated explainer the stream
    sends is drawn in a `sandbox="allow-scripts"` frame whose document opens with the policy, draws
    something and offers no peer connection, while every request from the frame is aborted and
    recorded and every load its policy refuses is recorded: none may be attempted. When the builder
    chose no concept the report notes it and does not fail. Each question now carries its depth.
11. **Not a defect any more.** `services/piece_store.py` had LF endings when this review started;
    the hygiene check passes on it.

## Consequences

- After the deploy, sections of the mechanism, process, materials and history fields show
  generated explainers, what-ifs, zooms and timelines; their costs are the builders' (one
  `COMPOSE` call for an explainer, one plan-model call for a what-if or a timeline, none for a
  zoom), all from the answer's headroom, Master Admins uncapped.
- The escape corpus holds 108 refused cases, each pinned to one rule; tests cover the self-closed
  script read as script, linear time on hostile markup, the frame's guard against a loopback STUN
  server (the same probe without the guard reaches it), the hidden mark through both read-back
  routes and through a carried block, the explainers of an any-craft answer and a deepened
  section kept as pieces, the bounded download, the score's message, the muted levels, the ask
  screen's offer reaching the player and the indigo question's outcomes. Database tests (marked
  `db`) cover hiding a block never kept and a carried block.
- Owner steps after the deploy: none beyond decision 0058's key permissions; dispatch E2E
  production with `questions=true` to prove the phase.
- Items left are in `docs/TECH_DEBT.md` under decisions 0054 and 0061.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
