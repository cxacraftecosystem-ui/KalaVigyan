# 0058. ElevenLabs music, sound effects, image and video

ElevenLabs makes the film score, an instrumental bed and sound-effect cues under the narration,
through one adapter and router wrapper on its newest models, cached per explainer and language. Its
image and video generation are route choices, not defaults.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0054 Phase C contract: generated explainers, the what-if lab, zoom, timelines and film mode](0054-phase-c-contract.md) |
| The review that fixed it | [0061 Phase C review fixes](0061-phase-c-review-fixes.md) |
| The contracts it names | [media.md](../contracts/media.md) |
| The score made once under a lease, timed by the heard narration, cued by stored facets (version 2) and swept | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0058 of phase C (`docs/plans/answer-experience.md` section 5, decision 0054 point 12) builds
the film score (one instrumental bed and sound-effect cues under the narration of film mode) and
checks whether ElevenLabs offers image and video generation that could join the existing `IMAGE`
and `VIDEO` route choices. Owner rules bind: Master Admins have no caps; every other caller spends
from the media sub-cap and the monthly ceiling; no paid call while building; prompts never carry
claims, names or model output; no connection held across an HTTP call (decision 0040); the key is
restricted to the server's address and holds the music, sound effects and image and video
permissions.

## What the official reference says (read 2026-11-18)

Sources: the API reference pages for compose music, create sound effect, create image and video
generations, get generation, the OpenAPI document `https://elevenlabs.io/docs/openapi/api-reference-2.json`,
the music and sound-effect capability pages, `https://elevenlabs.io/pricing/api`,
`https://elevenlabs.io/scale-tier`, the Image and Video quickstart and `https://elevenlabs.io/music-terms`.

- **Music.** `POST /v1/music`, JSON `{prompt (at most 4,100 characters), music_length_ms (3,000 to
  600,000), model_id, force_instrumental}`, query `output_format` (default `auto`, which is
  `mp3_48000_192` for the v2 models), answer `application/octet-stream` audio. Models
  `music_v1`, `music_v2`, `music_v2_5`; `music_v1` is deprecated and removed on 2027-01-31. The
  capability page caps a song at 5 minutes. The API is for paid plans.
- **Sound effects.** `POST /v1/sound-generation`, JSON `{text, loop, duration_seconds (0.5 to 30),
  prompt_influence (0 to 1, default 0.3), model_id}`, query `output_format` (default
  `mp3_44100_128`), binary audio. Models `eleven_text_to_sound_v2` (default, deprecated, removed
  2027-03-01) and `eleven_text_to_sound_v3`; "40 credits per second when duration is specified".
- **Image and video ("Flows").** A public API exists: `POST /v1/flows/image` and `POST
  /v1/flows/video` answer `{id, status: "pending"}`; `GET /v1/flows/{image|video}/{generation_id}`
  answers `pending`, `generating`, `completed` (`content_url`, a signed link that expires about
  an hour later, and `content_mime_type`) or `failed` (`failure_reason` one of `timeout`,
  `model_error`, `moderated`, `invalid_parameters`, `dependency_failed`, `charging_failed`,
  `internal_error`; failed generations are not charged). Image models include
  `gemini-3.1-flash-image` (`aspect_ratio` including `1:1`, `resolution` `512`, `1K`, `2K`, `4K`);
  video models include `veo-3.1-fast-generate-001` (`duration_secs` `"4"`, `"6"`, `"8"`,
  `resolution` `720p` to `4K`, `generate_audio`, `enhance_prompt`, both default true). Polling no
  more often than every 2 s for images and 10 s for video. It needs a Pro plan or above (402
  `paid_plan_required` below it) and a key with the Image & Video (or Flows) permission.
- **Prices.** The API pricing page lists music at $0.150 a minute and sound effects at $0.120 a
  minute (its FAQ says sound effects are "billed per generation"); the scale-tier page lists music
  at $0.275 a minute, sound effects at $0.060 a minute, Nano Banana 2 at 1K at $0.07 an image and
  Veo 3.1 Fast at $0.10 a second without audio. The pages disagree.
- **Licence.** Eleven Music's terms: outputs may be used under the plan's media rights; paid plans
  need no attribution; API access needs a paid plan; prompts must not name artists, songwriters,
  songs, albums, publishers or labels or quote lyrics; output must not be compiled into a music
  library or resold as a model. No separate licence is published for sound effects or Flows
  outputs beyond the general terms.

## Decision

1. **The newest models are the defaults.** The contract named `music_v1` and
   `eleven_text_to_sound_v2`; both are deprecated with removal dates, so the seeded routes are
   `music_v2_5` and `eleven_text_to_sound_v3` (the owner's latest-version rule), with `music_v2`
   offered as a choice. The score fixture names the new models.
2. **One adapter, one router wrapper.** `providers/elevenlabs.py` gains `music`,
   `sound_effect`, `start_generation`, `generation` and `download`; its answer parsing moved to
   `providers/elevenlabs_shapes.py` so the adapter stays under 400 lines. The media router
   reaches them through the registry: preset and kind `elevenlabs`,
   `providers/elevenlabs_media.ElevenLabsMediaAdapter` translating `MediaRequest` into those calls
   and every `ExternalFailure` into a `ProviderError` (a refused body `bad_request`, `moderated`
   `refusal`, `timeout`, `dependency_failed` and `internal_error` retryable `unavailable`, others
   `error`). `Adapter.generate_audio` is the new hook for `MUSIC` and `SOUND_EFFECT`.
3. **Requests.** Music asks `mp3_44100_128` explicitly (so the 128 kbps length check holds),
   `force_instrumental` true and the length in milliseconds; sound effects ask the same format,
   the duration, prompt influence 0.5 and `loop` false. Lengths outside 3 to 300 s (music) and
   0.5 to 30 s (sound) are refused before any call. Images ask the media contract's `1:1` at `1K`;
   video asks `"8"` seconds at `720p`, `16:9`, `generate_audio` false and `enhance_prompt` false,
   so ElevenLabs never rewrites a prompt whose bans come last. Images are polled every 2 s up to
   90 times inside the adapter; video through the media router at
   `max(router pace, adapter pace)`, 10 s for ElevenLabs. The signed content link is fetched only
   over https, without the key, following no redirect, at most 64 MB.
4. **Image and video are route choices, not defaults.** `ELEVENLABS` joins `AiProvider` and the
   catalogue lists `gemini-3.1-flash-image` (IMAGE) and `veo-3.1-fast-generate-001` (VIDEO) under
   it, so an admin can add them to the `IMAGE` and `VIDEO` chains in Settings; the seeded chains
   stay Gemini only. Every rule of `docs/contracts/media.md` is unchanged: the claim set, the
   prompt and its bans, the bundle, the queue, the PNG and silent MP4 checks, naming, quotas and
   refunds. Flows report no model, so the label names the requested model id.
5. **Prices.** Because the published pages disagree, the catalogue carries the higher figure per
   unit, so the ceiling errs towards refusing: music $0.275 a minute, sound effects $0.12 a
   minute (both per second), $0.07 an image, $0.10 a second of video; every ElevenLabs price is
   `price_verified` false until a real invoice is compared, and the admin price overrides apply.
6. **The score.** `GET /api/answers/{answerId}/film-score?language=` (`api/routes/film.py`, VOICE,
   10 in 10 minutes, Master Admin unlimited) reads the asker's explainer with hidden simulations
   marked, in one short session, and answers `FilmScore`. `voice/film_scenes.py` makes the scenes
   (drawn blocks by section order, a hidden simulation left out, each timed by its narration
   estimate at 1,000 characters a minute or `FILM_SCENE_SECONDS`), the scenes hash and the bed
   length (the film rounded up to 10 s, 30 to 180 s). `voice/score_prompts.py` holds the fixed
   prompts (`SCORE_PROMPT_VERSION` `film-score/v1`): one instrumental bed, and a cue per block
   kind and section field (ladder, water prose in a geography section, river story, reaction,
   seasons, map layer, molecule), at most 12 in reading order. No prompt carries a claim, name,
   place, figure or model output.
7. **Two caches.** A clip is content-addressed: its cache id is the SHA-256 of
   `kalavigyan-score`, the prompt version, the task, the model, the prompt and the length joined
   by U+001F, and it lives at `media/score/<cacheId>/` with its MP3 and `clip.json`. The score per
   answer and language is the manifest `media/score/<answerId>/<language>/score.json`, answered
   again while its scenes hash matches. A second reader, language or explainer that needs the
   same clip makes no call. Clips are made three at a time; any failure, refusal or wrong-length
   audio (more than 1 s from the asked length) stores no manifest and no clip for that call, while
   clips already made stay for the next ask. Without a sound-effect route the score is the bed
   alone. The making runs under the app's shielded work, so a reader who leaves still fills the
   cache.
8. **Spend.** Each clip is one media router call: reserved and settled per second against the
   media sub-cap and the monthly ceiling, with Master Admins allowed by `budget.evaluate`.
   `/answers/config` adds `film {score}`, true when the bucket is set, the reader holds VOICE and
   a 30 s bed could be made now.
9. **Schema.** Migration `0022_elevenlabs_media` adds `ELEVENLABS` to `AiProvider`, `MUSIC` and
   `SOUND_EFFECT` to `AiTask`, the `ELEVENLABS` provider row on `ELEVENLABS_API_KEY` and the two
   score routes. `throttled_voice_user` (`api/listen_deps.py`) is now shared by Listen and the
   score.

## Consequences

- Nothing changes for readers until lane 0060 draws film mode; the route and the config offer are
  live after the deploy. A first score costs from about $0.14 (a 30 s bed) to $0.90 (a 180 s bed
  and twelve cues) at the catalogue prices, $0.42 for the Kutch Ajrakh fixture; later readers of
  the same explainer and language cost nothing.
- Settings shows Film music and Film sound effects in the routing page and on Usage, and offers
  the ElevenLabs image and video models as further choices.
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
