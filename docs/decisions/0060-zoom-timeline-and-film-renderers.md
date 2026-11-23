# 0060. Zoom, timeline and film mode renderers

The zoom draws one level at a time, the timeline is a slider over the moments its texts date, and
film mode plays the drawn blocks as scenes over Listen's narration with an optional score. Scenes
and their clock are pure and shared with the server's numbers, and the player works by keys and on a
phone.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| The film's bed and cues through one Web Audio gain where the element volume is fixed | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Phase C of `docs/plans/answer-experience.md` ("Play", owner-approved, section 8 final) asks for the
powers-of-ten zoom (feature 1), trade routes through time (feature 4) and film mode (feature 3).
Decision 0054 fixed the `zoom_story` and `timeline_map` fields and film mode's client derivation,
score route and payload; decision 0057 registered both builders, waiting for their renderers.
This lane draws the two kinds through the renderer registry and plays the explainer as a film,
and edits no backend file. The boards are `Explainer`, `Map`, `Voice` and `Learn` of the design
project. Rules that bind: every fact the reader sees is cited, real geometry under the boundary
caption on every map, nothing widens a 390 px phone page, reduced motion has a static end state,
map and film code stay off `/ask` until used, and no how-it-works copy reaches a screen.

## Decision

1. **Registered through one module, loaded on demand.** `components/answer/journey/
   journeyRenderers.tsx` spreads `zoom_story` and `timeline_map` into `BLOCK_RENDERERS`, each a
   `lazyBlock` with the map placeholder, so the zoom, the timeline, `IndiaMap` and the projection
   stay out of the eager graph of `blockRenderers`. `BUILT_BLOCK_KINDS` is unchanged on both
   sides: decision 0042 point 11 adds a kind on both sides in one change and this lane edits no
   backend file, so the review (0061) joins the two kinds, as for decision 0059.
2. **The zoom draws one level at a time and moves the camera at the district.** A rail of the
   block's levels (aria-pressed buttons), the level's name, its picture or map or molecule, and
   its cited sentence; Zoom out and Zoom in through `ActionGroup`. Levels change with
   `zoomThrough` (the outgoing level grows and fades, the next one settles in). The district
   level is `IndiaMap` over the district shapes with the register's polygon filled, outlined and
   tagged, and the map moves into it (`journeyGeometry.districtFrame`: the polygon's projected
   box with room around it, at most 3 times, never showing past the frame's edge) under
   `cameraMove`. Each level carries its credit: the district the boundary caption and the shapes
   row (`MapAttribution`), a picture its author, licence and site (`ImageStrip.PictureView`), the
   molecule the PubChem record chip (`MoleculeView` over the level's compound, the conformer
   route and 3Dmol.js only when it nears the view). A picture that fails to load, a molecule
   without WebGL and a district missing from the shapes file draw no visual; the cited sentence
   stays. Under either reduced-motion switch every level is listed in zoom order, with no rail,
   buttons or camera move.
3. **The timeline is a slider over the moments its texts date.** Points and routes are one list
   in time order (`lib/timelineView.timelineEntries`), each with its span as the texts state it
   (`yearSpanText`: a year, a range, a decade, an ordinal century or centuries, the server's
   `years_named` spans read back), its places (pin numbers where placed, an arrow for a route)
   and its cited sentence. The slider's stops are the distinct first years, labelled by the first
   entry starting there; it opens at the last stop, so everything shows, and an entry is past,
   current or later at the chosen year (a later one is dashed, never faded below contrast).
   With one moment there is no slider.
4. **Placed places are pins; a place beyond the frame is a signpost.** The map is `IndiaMap`
   over the district shapes with the boundary caption and the shapes row; places with a Wikidata
   item and coordinates are numbered in order of first use and each links its item. A place inside
   the India frame is a pin, on the plain ground when it lies outside India's shapes; a place
   outside the frame (Fustat) is a signpost at the frame's edge at its own latitude or longitude
   with an arrow toward it and its number and name (`journeyGeometry.edgePost`), never another
   country's outline. A route is a line between two placed ends, drawn once its year is reached.
   With nothing placed there is no map, only the list.
5. **Film mode is a player over the drawn blocks.** `ExplainerView` offers Film exactly where
   Listen is (after `done`, with an answer id, in a Listen language) and loads
   `components/answer/film/FilmPlayer` only when it starts; starting a film stops Listen. The
   player is a `FieldDialog` (focus held, Escape closes) holding the stage, the caption, the
   timing, the buttons and, when `/answers/config` offers it, Music and sound.
6. **Scenes and their clock are pure and shared with the server's numbers.** `lib/filmScenes`
   derives the scenes (sections by `order`, blocks in order, drawn blocks only, a hidden
   simulation left out), times each by its Listen tracks or `FILM_SCENE_SECONDS` (4 s a step of a
   reaction player or region story, 3 s a picture, 6 s any other block, the server's
   `schemas/film.FILM_SCENE_SECONDS`), and steps one clock (`filmStep`: play, pause, toggle,
   next, previous restarting a scene played over 2 s, choose, a tick of a held scene, the
   narration's time and track ends, a stale scene's report ignored, the end and Play again). A
   `take` counter remounts the narration and the cue on every restart.
7. **Each scene plays its block's own animation.** The stage renders the block through
   `renderBlock` inside `FilmSceneProvider` (`components/answer/FilmScene`, the scene's progress
   from 0 to 1): the ladder fills with it, the reaction player steps with it and hides its own
   controls, the zoom moves level by level, the timeline slides stop by stop (`stepAt`,
   `sceneStep`); the region story's river flows as it enters view. Under either reduced-motion
   switch scenes swap with no motion and every block shows its static end state, while the clock
   keeps the narration's pace.
8. **Narration is Listen's script and audio.** The player fetches the Listen script once, plays
   each scene's tracks through `ListenAudio` (which gained `muted`), and marks the sentence and
   word being read in the block (`ExplainerReading.listen`, through `listen.trackMark`, now the
   one home of a track's mark). The caption is that sentence in the answer language with the word
   marked (`filmCaption`, Listen's words, whatever text the page shows); a silent scene is
   captioned with its section's title. A script that fails to load or audio that breaks says
   "Couldn't start the film." or "Couldn't play the narration." with Try again, which keeps the
   film's place; a refused autoplay pauses.
9. **The score is optional, asked once and mixed by fixed rules.** Music and sound is a `Toggle`,
   off by default; turning it on asks `GET /answers/{answerId}/film-score?language=` once
   (`fetchFilmScore`, checked by `checkedFilmScore`); the film keeps playing and the score joins
   when it arrives; any failure turns the switch back off and plays on. `lib/filmSound` mixes it:
   the bed loops at 0.25 of the music volume, fades to silence over the film's last 2 s and is
   put back in step when it drifts over 1.5 s from the film's place; a scene's cue plays once at
   its offset at 0.8 of the effects volume; Mute silences narration, music and effects and
   leaves the captions. The status line credits the score ("AI music and sound", its models and
   date). `/answers/config` `film {score}` is read by `filmScoreOffered`; absent or off the
   contract, no control is drawn.
10. **Keys, phone and focus.** Space and K play or pause (Space leaves a focused button its own
    press), the arrows and J and L step scenes, M mutes; form fields keep every key
    (`filmKey`). The play button stays focusable while the film loads (`aria-disabled`), so it
    takes the dialog's first focus. On a phone the stage scrolls inside 46% of the screen's
    height, the caption sits under it and the controls stack; every row uses shrinkable columns.

## Consequences

- Readers see the zoom and the timeline once the review joins the two kinds to
  `BUILT_BLOCK_KINDS` on both sides; readers see Film on every finished answer with Listen as soon
  as this ships, and Music and sound once lane 0058's `/answers/config` `film` offer is on.
- `e2e/journey-renderers-unit.spec.ts` parses the phase C fixture and checks the registry and its
  lazy loading, the numbering, the levels one at a time and as a list, each level's credit, the
  camera on the real Kachchh polygon, spans of years, time order, the slider, the signpost and
  pins with routes, the empty states and the shrinkable columns.
  `e2e/film-mode-unit.spec.ts` checks the scenes and holds against the phase A document, the
  Listen and score goldens and the server's `FILM_SCENE_SECONDS`, the clock, captions in the
  answer language, keys, the mix, the offer, the stage with the ladder and reaction player
  following the scene, the controls and the lazy player.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
