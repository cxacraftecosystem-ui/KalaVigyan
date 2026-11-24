# 0189. Paid media lost after the provider took it is counted at its estimate, an artisan's recording is kept only with its row, voice refunds are dated to their hold, relief bands are drawn from the grid as read, and an agent turn waits for its bind

A clip or picture whose poll or download fails after the provider took the work is settled at its
estimate, so the media ceiling counts it; an artisan's recording and its row are written as one
piece of work, and the recording is deleted again when its row cannot be; a Listen or relay refund
is dated to the moment its hold was taken; the relief bands a place's elevation is read from are
drawn from the ETOPO1 grid without smoothing; and a custom-LLM call whose ElevenLabs conversation no
session holds yet reads the record again for up to 2 s, and its refusal names the header's shape.

Date: 2026-11-24. Status: accepted (the lead's review-fix round of 2026-11-24, lane media, on
findings a reviewer reported and a second reviewer traced through the code, and one the lead saw on
production). It amends [decision 0018](0018-media-backend.md) (how a failed media call settles),
[decision 0083](0083-students-and-artisans.md) (where an artisan's recording is kept),
[decision 0140](0140-voice-and-listen-kept-true.md) (the relay and Listen refunds) and
[decision 0184](0184-a-measured-rubric-floor-the-recorded-clip-one-open-acl-and-a-named-refusal.md)
(item 4, the refused agent turn's log). The contracts are `docs/contracts/media.md` (Quotas, spend
and refunds), `docs/contracts/roles-and-contributions.md` (Audio), `docs/contracts/voice.md` (the
binding, point 5; the relay turn; Listen's seconds) and `docs/DATA_SOURCES.md` (Relief bands).

| For | Read |
|---|---|
| The media router and its reserve and settle | [decision 0018](0018-media-backend.md) |
| A call cut off settled at its estimate | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| Media refunds dated to their job | [decision 0154](0154-ai-media-and-film-scores-kept-true.md) |
| Artisan conversations and their recordings | [decision 0083](0083-students-and-artisans.md) |
| Relay billing and Listen's hold | [decision 0140](0140-voice-and-listen-kept-true.md) |
| Seconds unlimited for every role for now | [decision 0093](0093-no-caps-for-now.md) |
| The refused agent turn's log | [decision 0184](0184-a-measured-rubric-floor-the-recorded-clip-one-open-acl-and-a-named-refusal.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **A lost clip cost nothing on the ledger.** `MediaRouter._call` settled every `ProviderError` at
  $0 (`route_store.settle`'s default), and only a call cut off by its caller was charged its
  estimate. Several failures come after the provider has taken, and may have billed, the work: a
  poll of a started Gemini clip or ElevenLabs generation that answers 503 or never arrives, the
  Files API or `storage.googleapis.com` download of a finished output, a finished body off the
  documented shape, an ElevenLabs image still unfinished after its 90 polls. The interaction was
  then deleted, the route walk tried the next route and the runner retried the job up to twice, each
  clip about $0.56, while `current_spend` counted none of the lost ones, so the media sub-cap and the
  monthly ceiling `reserve` enforces undercounted real spend.
- **A recording could outlive its row.** `_ArtisanTurn._kept_turn` put the upload in the bucket at
  `media/<userId>/<uuid>/…_<District>_<Craft>_Recording_T<nn>.<ext>` and only then called
  `save_turn`, the only writer of its `ArtisanConversationAudio` row. An artisan who closed the tab
  in between cancelled the stream (and the PUT, which runs in a thread, completed anyway), and a
  `save_turn` that failed (the conversation gone, a database error) was only logged. Retention and
  withdrawal delete recordings through those rows, and no lifecycle rule covers `media/<userId>/`, so
  such a recording, named by district and craft, was kept for good.
- **Refunds landed on the day they were written.** A Listen hold, a relay turn's minute and an
  artisan turn's minute were dated when written, and their refund or settle when the narration or
  speech to text finished. A hold at 23:58 IST settled at 00:02 put its refund, say −400 s, on the
  next day, where `used_today` nets it against that day's use. `VOICE_SECONDS` is unlimited for
  every role for now (decision 0093), so today Usage only misdated the seconds; with an allowance set
  on the AI budget screen the reader would have had that much speech past the next day's allowance.
  The agent's settle and the media refund were already dated to the call's start and the job's
  creation (decisions 0140 and 0154).
- **A place's elevation was read from a drawing.** `relief_body` drew the hypsometric bands from
  `_halved(_smoothed(_smoothed(ETOPO1)))`, two 3 by 3 means and a 2 by 2 block mean of the 1
  arc-minute grid (a footprint of about 9 to 11 km), each band then simplified at 0.018 degree. The
  API's place ground reads a place's band from those same bands (`ground_measure.elevation_band`)
  and the craft page shows it as the place's elevation under the ETOPO1 note. A valley floor one
  cell wide at 1,200 m between 3,000 m ridges reads 2,400 m after the first mean alone, so it was
  shown in the 2,000 to 4,000 m band. The dataset guide forbids smoothing a value; the 0.018 degree
  tolerance is the `RELIEF_BANDS` class's.
- **The agent's turns were refused at the session record check.** On production on 2026-11-24
  (release db1efa4a, paid check run 45304855493) the check created an `AGENT` session at
  01:25:07.44 and bound it to its 33-character `conv_` conversation before it spoke; ElevenLabs
  called the custom LLM three times between 01:25:08.71 and 01:25:09.32, and each call passed the
  bearer and was refused because no session held the conversation. Two causes fit: the header
  arrives unsubstituted (`{{system__conversation_id}}`, 27 characters), or ElevenLabs calls the
  model at the conversation's start, before the bind commits. Decision 0184's log could not tell
  them apart.

## Decision

1. **Lost paid work is counted at its estimate.** `providers/base.BilledFailure`, a
   `ProviderError` with the same kind, status and retry hint, marks a failure after the provider
   took the work; `billed_on_failure()` turns any `ProviderError` raised inside it into one.
   `gemini_media` raises it for a failed poll of a started clip, a finished output it cannot
   download or read (no data and no Files API link, an empty download, a block off its type), an
   interaction in a status it does not know and an image the synchronous call left open;
   `elevenlabs_media` for a failed poll or download of a started generation and an image
   unfinished after 90 polls. `MediaRouter` settles a `BilledFailure` `ERROR` (or
   `REFUSED_PROVIDER`) at the route's estimate and every other failure at nothing: a create that
   failed, and the provider's own verdict (a refusal, a `failed`, `cancelled` or moderated
   generation), which providers do not bill. The route walk, the deletion of the interaction and
   the job's retries are unchanged. Rejected: a flag the router sets once `start_video` returns,
   which misses the one-call image paths and would also charge the provider's verdicts; and
   retrying a failed poll before deleting the clip, which would save a second clip's cost but
   hides nothing from the ceiling now and waits for a measured need.
2. **A recording is kept only with its row.** `_kept_turn` runs the PUT and `save_turn` as one
   `ShieldedWork` task (`artisan turn kept`), so an artisan who leaves cannot split them, and a
   `save_turn` that fails, or is cancelled, deletes the object again through `AudioBucket.delete`
   (the S3 adapter's `delete`) before the error goes on; a delete that fails is logged with the
   conversation's id, never the key. Rejected: a lifecycle rule on `media/<userId>/`, which would
   also delete the recordings kept testimony needs, whose retention the rows decide; and a sweep of
   objects without rows, which would list every account's prefix.
3. **A refund is dated to its hold.** `voice/seconds.ledger_entry` and `ListenAsk.entry` take a
   `counted_at`. A relay or artisan turn dates its minute's hold and its refund to the moment of its
   claim; Listen dates its hold, refund and settle to the moment of the hold
   (`ListenHold.counted_at`). `QuotaLedger.createdAt` is then that moment, as for the agent's settle
   and the media refund. Speech made later (a reply, a replay) is still dated when it is made.
4. **Relief bands are drawn from the grid as read.** `tools/maplayers/relief.relief_bands(grid,
   india)` draws each band from the ETOPO1 values as read, simplified at `BAND_TOLERANCE` (0.018
   degree) and nothing else; `_halved` is gone, and `_smoothed` (one 3 by 3 mean) serves the shaded
   relief alone, which is drawn and never read. The map and the API keep reading one file, mirrored
   byte for byte. `tools/tests/test_maplayers_relief.py` measures a one-cell valley through the
   API's own reader; it runs where numpy and rasterio are installed (the build's environment), and
   is skipped by Backend checks, whose environment has neither.
5. **An agent turn waits for its bind, and its refusal names the header's shape.**
   `authorised_session` reads the session of a header that starts `conv_` again up to four times,
   half a second apart (`BIND_REREADS`, `BIND_READ_SECONDS`: 2 s at most), before it refuses; any
   other header is read once, and every refusal is still the one 401 `unauthorized`. A
   session-record refusal for want of a session logs the header's length and whether it starts
   `conv_` (`no session holds this conversation (27 characters, does not start with conv_)`, or
   `no session held this conversation within 2 s (33 characters, starts with conv_)`), never the
   header. The ElevenLabs agent is not changed. `authorised_artisan_session`, the artisan agent's
   check, still reads its record once; it is not the check that was refused.

## Consequences

- Usage shows a lost clip or picture as an `ERROR` row with its estimate as its cost, and the media
  month, the month and the user's day count it, so the ceiling holds against clips the provider
  may have billed. A provider that turns out not to bill a lost read is overcounted by its estimate,
  which errs toward the ceiling.
- No migration and no change to any payload the web reads.
- The relief files in the repository (`frontend/public/layers/relief.json` and its mirror in
  `backend/app/data/layers`) were built before this rule and still hold the smoothed bands. A run of
  `tools/maplayers_build.py` with the downloads `tools/maplayers/sources.py` names, in the etl/geo
  environment and off this development machine, rewrites and mirrors them; that change states the
  new file's size, which grows with the bands' detail, and replaces the sentence in
  `docs/DATA_SOURCES.md` (Relief bands) that says so. Until then a place near a band's edge in steep
  relief may still read the smoothed band.
- After this release the voice check is run again with the call switched on: a refusal that names
  27 characters not starting `conv_` means the agent's request header is sent unsubstituted, which
  is the agent's configuration and an owner's change at ElevenLabs; a turn answered after the wait,
  or a refusal naming a `conv_` id held by no session within 2 s, settles the other cause.
- The register is the lead's: this record adds and removes no entry.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-24; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/media/test_media_router.py`, `backend/tests/media/test_gemini_media.py`,
`backend/tests/media/test_elevenlabs_media.py`, `backend/tests/db/test_media_router_db.py`,
`backend/tests/voice/test_artisan_relay.py`, `backend/tests/voice/test_relay.py`,
`backend/tests/voice/test_listen.py`, `backend/tests/voice/test_agent_turn.py` and
`tools/tests/test_maplayers_relief.py`.
