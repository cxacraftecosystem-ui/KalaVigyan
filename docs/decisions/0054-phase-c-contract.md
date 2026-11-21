# 0054. Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode

Phase C's contract fixes version 1 of generated explainers, the what-if lab, the zoom story,
timelines and film mode: numbers enter the sandboxed frame only from claims or dataset rows, and the
static check names what it refuses. A zoom level is real or absent, dates are read and places looked
up, and film mode is derived on the client under an ElevenLabs score.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The lanes built to it | [0055](0055-generated-explainers.md), [0056](0056-what-if-lab.md), [0057](0057-zoom-story-and-timeline-map.md), [0058](0058-elevenlabs-music-sound-image-video.md), [0059](0059-sandbox-and-what-if-renderers.md) and [0060](0060-zoom-timeline-and-film-renderers.md) |
| The contracts it names | [explainer.md](../contracts/explainer.md), [media.md](../contracts/media.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase C of `docs/plans/answer-experience.md` ("Play", owner-approved, section 8 final) builds
sandboxed generated explainers, the what-if lab, film mode with ElevenLabs music and sound effects
under the narration, the powers-of-ten zoom, trade routes through time, and ElevenLabs image and
video as further media routes. Decision 0030 declared `simulation`, `what_if`, `zoom_story` and
`timeline_map` with provisional fields; none was ever produced, stored or drawn. Phase C runs as
parallel lanes with fixed numbers: 0055 generated explainers, 0056 what-if lab, 0057 zoom story
and timeline map, 0058 ElevenLabs music, sound effects, image and video, 0059 sandbox and what-if
renderers, 0060 zoom, timeline and film mode renderers, 0061 review fixes. As in phase B (0042),
the interface they share is agreed and built first and pinned on both sides by fixtures.

## Decision

1. **Version 1 is fixed now, not reinterpreted.** The four kinds keep `version: 1` with their final
   fields (`docs/contracts/explainer.md`, Phase C blocks), because no version-1 payload of them
   exists anywhere. They move to `research/blocks_play.py` (`simulation`, `what_if`) and
   `research/blocks_journey.py` (`zoom_story`, `timeline_map`); the client's shapes are
   `lib/explainerPlay.ts`, and `MediaRef` moved to `lib/explainerBlockBase.ts` so the zoom shape
   can use it without an import cycle.
2. **The kind keeps its name.** The generated explainer stays the `simulation` kind of the plan's
   block table; renaming a declared kind would touch both vocabularies for nothing a reader sees.
3. **Numbers into the frame come from claims or dataset rows.** A simulation value is a figure a
   cited quote states, with the quote's own words (`stated`), or a dataset row's value; labels and
   titles carry no other figure. The frame reads them from one JSON element the client writes,
   `kv-data`, so the stored HTML holds no data and stays the same for every reader.
4. **The static check names what it refuses.** `research/sandbox.sandbox_problems` returns
   `{rule, detail}` under six rules (`SIZE`, `MARKUP`, `ELEMENT`, `API`, `URL`, `NUMBER`), and the
   corpus `shared/sandbox.corpus.golden.json` pins each escape attempt to exactly one rule. It is a
   lexical check over a parsed fragment plus raw scans of the whole text (so a parser difference
   between Python and a browser cannot hide a tag), not a JavaScript parser: script strings are
   scanned like code, `\u` and `\x` escapes are decoded first, and anything that rebuilds markup
   from strings (`innerHTML`, `document.write`, `DOMParser`, `srcdoc`) is refused, so the markup
   checked is all the markup the frame has. Beyond the plan's list it refuses WebRTC (which the
   frame's policy does not govern), `location`, `constructor` reads, computed reads of globals,
   string timers, `Reflect` and `Proxy`, and every element whose text a browser parses
   differently from Python (`title`, `textarea`, `noscript`, `xmp`, ...).
5. **Layout constants are a short fixed set; shown numerals have none.** Script numbers may be
   small counts, binary sizes, angles, percentages, milliseconds, a colour channel or simple
   fractions; any numeral the reader sees must be a data value. CSS lengths and SVG geometry are
   layout and are not read.
6. **The frame is the boundary.** `sandbox="allow-scripts"` only, a fixed `srcdoc` whose first
   head element is the policy `default-src 'none'; script-src 'unsafe-inline'; style-src
   'unsafe-inline'; img-src data:`, no permission attributes, and `frame-src 'none'` in the site
   policy so a frame that navigates itself loads nothing. The check filters in front of it.
7. **Stored once, keyed by claim set and concept, hidden by a professor.** A simulation piece is
   cross-craft under `concept:<slug>`, reused only for the same claim set. Hiding marks the piece
   (`hiddenAt`, `hiddenById`, reuse refusal `HIDDEN`) and never rewrites its payload, whose hash
   must keep matching; the block's `hidden` is how a stored explainer is served back.
8. **A what-if rests on relationships.** One input per block; each option's outcomes are stored
   claims relating it to a result or a stored reaction of its compound; an option without one is
   unknown and stays unknown. Option labels from a model are allowed only when every outcome names
   them, and an unknown option carries no figure.
9. **A zoom level is real or absent.** Districts from the register with the boundary caption,
   pictures only under an open licence with their author, compounds only with their record and a
   kept conformer. A missing level is left out, never faked or filled with a link card.
10. **Dates are read, places are looked up, moves are stated.** `research/timeline` reads years,
    ranges, decades and centuries from the sentence and its quotes; a model only chooses among
    them. Coordinates come from Wikidata through the supply origins' placing rule (0047). A route
    needs one text saying `from <start>`, naming the end and using a movement word. The map draws
    the India district shapes under the caption and nothing of other countries.
11. **Film mode is derived on the client.** Scenes are the drawn blocks in reading order, timed by
    Listen's tracks or a fixed hold per kind, captioned with the words being read; reduced motion
    shows end states. Nothing is generated except the optional score.
12. **The score is ElevenLabs through the media router, cached per explainer and language.** One
    instrumental bed and at most one sound-effect cue per scene, from fixed prompts that never
    carry claims or names, reserved and settled as media spend, kept with a manifest per answer and
    language and content-addressed audio so later readers reuse it. `MUSIC` and `SOUND_EFFECT`
    become media tasks; ElevenLabs image and video become route choices only if a public API
    exists, which lane 0058 checks on the official reference before building anything.
13. **Fixture.** `shared/explainer.phase-c.golden.json` holds every phase C kind for Kutch Ajrakh,
    built only from seed claims and sources, the science seed, the LGD register, the phase A and
    region goldens and recorded PubChem and Wikidata responses (the Wikidata searches for Fustat,
    Sindh, Kutch and Ajrakhpur and two coordinate queries, recorded on 2026-11-18 from the public
    API). `shared/film.score.golden.json` scores the phase A document.

## Consequences

- The lanes build to `docs/contracts/explainer.md` (Phase C blocks, the static check and frame,
  Film mode) and `docs/contracts/media.md` (ElevenLabs routes); their fixtures and tests must keep
  the phase C fixture, the corpus and the score reproducing.
- Nothing a reader sees changes: the kinds are not built, and `piece_slot` and the reading order
  (`PIECE_BLOCK_ORDER`) only take effect once a phase C block can be stored.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
