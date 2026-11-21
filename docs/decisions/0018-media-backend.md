# 0018. Media backend: stage illustrations and clips through the router, the job queue and S3

Stage illustrations and clips are made only on an explicit press, through the media router's walk, a
job queue served by a worker, and the private S3 bucket. The claim set comes from the server, the
prompt is versioned, and what the official Gemini pages did not confirm is handled fail-closed.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [media.md](../contracts/media.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the media contract (`docs/contracts/media.md`) and lane 0021 built the craft
page's Image and Video buttons against it. PLAN 11 asks for jobs made only by an explicit press, a
claim set the server derives from the stage (never from the client), a versioned prompt with fixed
bans and a filtered style hint, Gemini image and video models on separate queues (4 and 2), a
4-minute timeout with 2 retries, BLOCKED outputs refunded, an HMAC bundle the worker checks, a
`promptHash` cache for shared assets, labelled assets in the private bucket under PLAN 14.3 names,
and the PLAN 12 daily units under the media sub-cap. PLAN 0 and the owner rules bind: no comments,
no deploys or cloud changes, no secret values printed, guards fail closed, no gap admissions on
screens, every user-facing fact cited.

## Verified on 2026-11-16 (official Gemini API pages)

- Image and video generation both run on the Interactions API: `POST /v1beta/interactions` with
  `x-goog-api-key` and `Api-Revision: 2026-05-20`; `GET /v1beta/interactions/{id}` polls a
  background run (`background: true` needs `store`, the default). Statuses: `in_progress`,
  `requires_action`, `completed`, `failed`, `cancelled`, `incomplete`, `requires_continuation`.
- Output arrives in `steps[]`: a `model_output` step whose `content[]` holds blocks of
  `type: "image" | "video"` with `mime_type` and `data` (base64) or `uri`. Usage is `usage`
  (`total_input_tokens`, `total_output_tokens`, `output_tokens_by_modality[{modality, tokens}]`).
- Image `response_format`: `type: "image"`, `aspect_ratio`, `image_size` (`1K` upper case).
  Video `response_format`: `type: "video"`, `aspect_ratio` (`16:9` | `9:16`), `resolution`
  (`720p` default), `duration` (`"3s"`-`"15s"`), `delivery` (`inline` | `uri`).
- Gemini Omni Flash (`gemini-omni-1.2-flash`) makes clips with native audio; no option to turn
  audio off is documented. Veo 3.1 preview was shut down on 2026-10-22.
- The image page now calls `gemini-nano-banana-2.1` the recommended model and
  `gemini-3.1-flash-image` the previous generation. The routes keep PLAN 9's order (3.1 Flash Image
  first, Nano Banana 2.1 second); the order is editable at `/admin/routing`.
- A `uri` is guaranteed only in the creation response or the stream; a later
  `GET /v1beta/interactions/{id}` returns inline base64. URI files download from
  `/v1beta/files/{id}:download?alt=media`.
- Prices (Standard): `gemini-3.1-flash-image` $0.50 / M input, $60 / M image output, 1,120 tokens
  per 1K image ($0.067); `gemini-nano-banana-2.1` $1.50 / M input, $30 / M image output ($0.0336
  per 1K image); `gemini-omni-1.2-flash` $1.50 / M input, $12 / M output, 5,792 tokens per second
  at 720p (about $0.0695 a second, $0.556 for 8 s). These are now in the model catalogue.
- Sources: ai.google.dev (now aistudio.google.com/docs) pages `image-generation`, `omni`,
  `video-generation`, `background-execution`, `pricing` and the Interactions API reference.

## Unverified (marked, handled fail-closed)

1. **Blocked outputs.** The reference shows no finish reason or safety field for interactions. The
   wire treats as BLOCKED: a 400 whose message speaks of safety, policy or blocking; a `failed`
   interaction whose `errors` say so; and a finished interaction with no image or video block
   (the model answered in text only). Everything else is an error that may be retried.
2. **The image output type.** The image `response_format.mime_type` enum lists only
   `image/jpeg`; no default is stated. We send none and accept only a PNG (signature and IHDR);
   anything else fails the attempt and is retried, then refunded.
3. **The delete route.** The SDK has a delete call; the REST path `DELETE /v1beta/interactions/{id}`
   is assumed. A background video interaction is deleted after it is read, best effort, logged on
   failure.
4. **Clip duration.** A clip must last at most 8 s by the contract; the video track's own
   duration (its `mdhd`) is checked after the audio track is removed. If Omni overshoots by a
   frame, every video fails and is refunded: watch the first runs.
5. **Interaction ids** are percent-encoded into the path; their alphabet is not documented.
6. **Fixtures** in `backend/tests/media/fixtures/` follow the documented shapes with real PNG and
   MP4 bytes, not captured traffic: no paid call was made from this machine.

## Decision

1. **A `media/` package** (PLAN 3 names it): claim set, prompt, bundle, MP4 and PNG checks, names,
   the API steps (`jobs.py`), the worker steps (`runner.py`), the queue loop (`queue.py`) and the
   SQL (`store.py`, `queue_store.py`, `rows.py`) behind the `MediaStore` and `QueueStore`
   protocols, so every rule is tested with in-memory stores and the SQL has database tests. It
   imports `providers`, `services`, `schemas`, `research`, `core`, `models`; only `api` and the
   worker import it (`LAYER_IMPORTS`).
2. **One Gemini wire for media**, `providers/gemini_media.py` (`GeminiMediaWire`) over httpx, used
   by `GeminiAdapter.generate_image`, `start_video`, `poll_video` and `forget_media`, which the
   `Adapter` base declares (other providers answer `unavailable`). The google-genai SDK keeps the
   text calls; media uses the REST shapes the pages document, so the fixtures are the wire's JSON.
3. **The router walk for media** is `providers/media_router.MediaRouter`: it reads `RoutePolicy`
   for `IMAGE` or `VIDEO` (`gemini-3.1-flash-image` then `gemini-nano-banana-2.1`;
   `gemini-omni-1.2-flash`), reserves each call with `router.reserve` (one `UsageEvent` per call,
   `isMedia`, so the media sub-cap and the monthly ceiling refuse there), falls through on the
   router's next-route kinds and stops on refusal or bad request. Cost is settled from the billed
   tokens at catalogue prices; without usage it is the unit price. A cost more than 20 % off the
   configured unit price logs `media price drift` (PLAN 11's alert). A call cut off by the timeout
   is settled `CANCELLED` at its estimate, since the provider may have billed it.
4. **Images** run as one synchronous interaction with `store: false`; **video** runs in the
   background (`background: true`), polled every 5 s and deleted after it is read. No `delivery`
   is sent: the polled answer carries the clip inline; a `uri` block is still downloaded, and only
   from the Files API host, so the key never goes elsewhere.
5. **Silence.** Any audio track is removed from the MP4 before storage by rewriting the `moov` box
   without `soun` tracks and moving the chunk offsets when `moov` precedes `mdat`; a fragmented
   MP4 is refused. This needs no ffmpeg on the box.
6. **The claim set** is the contract's, read from stored rows in three queries: the stage
   concept's claims (concept `OPEN`) and its `StageMaterial` claims; not `DRAFT`, `REJECTED` or
   `RETRACTED`; sensitivity `OPEN`; no citation from a `RESTRICTED` source or chunk; level
   `VERIFIED` or `REVIEWED` with a citation the asker may read, or `PROVISIONAL` with a `PASS`
   quote the asker may read (a `RESEARCHER` chunk counts only for `READ_RESEARCHER_QUOTES`
   holders); hypotheses never. Order: level, own before material, id; at most 8. PLAN 13a keeps
   community and caste names out of prompts; with no register of names, a claim using a group
   word (community, caste, jati, samaj, tribe, clan, gotra, biradari, adivasi) is left out of the
   set, and a stage name using one is left out of the prompt.
7. **The prompt** `media-prompt/v1`: one opening line per kind, the stage name, the claims as
   numbered facts introduced as reference data, the seven bans, then the style hint (refused again
   by `style_hint_problem`). `promptHash` is SHA-256 of the canonical JSON of version, kind, the
   first route's model, the claim ids with texts and the hint. A `CRAFT_SHARED` asset whose
   producing job has the same hash answers at once: a new `SUCCEEDED` job with `attempts` 0, no
   unit, no hold. If that asset is later unshared, the cached job answers 404.
8. **Jobs and the queue.** `POST` checks the capability, answers a repeated key (the key is
   SHA-256 of the user and the client key, so keys never meet across users), derives the claim
   set, checks units and open jobs, holds the first route's estimate with `router.reserve`
   (503 with the router's sentence when the media cap or ceiling refuses), then in one
   transaction under a per-user advisory lock re-checks the key, the 3 open jobs and the day's
   units, writes `MediaJob`, the `media:<jobId>` unit and a `Job` row (`media.image` or
   `media.video`, three attempts). A losing race releases the hold.
9. **The worker** is the existing `kv-worker` unit: `app/worker.py` makes its
   `ConditionPathExists` true, so blue/green starts it after the switch and stops it for
   migrations. No new unit, timer or service. It claims `Job` rows with
   `FOR UPDATE SKIP LOCKED` under a per-queue advisory lock that counts running rows, so 4 image
   and 2 video run at once across processes. Each attempt: open the bundle, release the hold,
   generate under `asyncio.timeout(240)`, check the output, name it, upload it, store the asset.
   Refusals end `BLOCKED`; bad requests, budget and route absence end `FAILED`; anything else is
   retried after 15 s × attempts until three attempts are spent. Final failures write one
   `media-refund:<jobId>` row. A `RUNNING` row older than 6 minutes is handed back as an attempt
   that counted. Without its bucket or bundle key the worker logs the missing name once and waits.
10. **The bundle** is canonical JSON of tool `media.generate/v1`, args (kind, stage, claim ids,
    prompt hash, the prompt's SHA-256, model, hint), requester (user, role at creation), target
    (job, stage) and an expiry 24 h out, with a base64url HMAC-SHA256 under
    `MEDIA_BUNDLE_HMAC_KEY` (32 characters at least). The worker refuses a missing, forged,
    mismatched or expired bundle before any model call and refunds the unit.
11. **Names and storage.** `services/naming.py` is the one name helper (PLAN 14.3, the naming
    skill), with rows in `shared/naming-golden.json`: Subject is the stage name cut at a word to
    40 characters, then the 150-character fit trims Subject, Craft, Place. Place is the craft's
    strongest location (point, then district, then state; then level), else its first state of
    practice. Keys are `media/<requester>/<uuid32hex>/<name>`; uploads use SSE-S3. The S3 client
    is `services/object_store.py`, presigning GETs for 900 s on the regional virtual-hosted host
    with `inline; filename=...; filename*=UTF-8''...`, and refusing any other host.
12. **Labels.** `MediaAsset.model` (migration 0008) holds the model that made the asset, so the
    label stays true for cached readers; `MediaJob.assetId` (same migration) links a job to the
    asset it shows, its own or a shared one, so `cached` is "the asset was made by another job".
    `depictsNamedCluster` is true when the prompt names one of the craft's located places, and
    true when the craft has no located place to compare with.
13. **Options** list a kind only when the role holds it, units are left, the bundle key and
    bucket are set, a route has a key, and the budget would allow one more; otherwise nothing is
    offered and no button is drawn.
14. **Secrets.** `seed_secrets.py` generates `MEDIA_BUNDLE_HMAC_KEY` like the voice keys; Deploy
    backend syncs it from GitHub to Parameter Store. Media stays hidden until it exists.

## Consequences

- Media appears once `MEDIA_BUNDLE_HMAC_KEY` exists (re-run `seed_secrets.py`) and the next
  release ships `app/worker.py`; `GEMINI_API_KEY` and `S3_BUCKET` already exist.
- The first live runs must confirm the unverified items above, especially PNG output, the clip
  duration and how a safety block reads.
- Debt: the stage image as a video's first frame, captured fixtures, the KalaVigyan token in the
  cross-portal naming document, refunds counted on the refund's day, and voice upkeep moving into
  this worker (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
