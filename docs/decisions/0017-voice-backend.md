# 0017. Voice backend: sessions, the custom LLM, the relay path and upkeep

The voice backend is a `voice/` package: sessions bound to one user, one ElevenLabs adapter, a quota
ledger and a custom-LLM endpoint that answers each turn from a claim pack in one model call. Spoken
replies are cited, seconds are reserved and reconciled, the relay path uploads audio, and upkeep
runs without a worker.

Date: 2026-11-16. Status: accepted; item 12 superseded by decision 0025.

| For | Read |
|---|---|
| What amended part of it | [0140 Voice and Listen hold their state in the bucket, bill what they hear and read the lede first](0140-voice-and-listen-kept-true.md): upkeep in the worker, reply audio in the bucket, decoded billing, the form reader and the pack's ranking |
| What superseded part of it | [0025 Voice in every answer language](0025-multilingual-voice.md): item 12, the languages voice offers |
| The contract it was built to | [0014 Contracts for process science, region profile, voice and media](0014-science-region-voice-media-contracts.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| The contracts it names | [voice.md](../contracts/voice.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0014 fixed the voice contract (`docs/contracts/voice.md`) and lane 0020 built the voice dock
against it. PLAN 10 asks for a session bound to one user through a server-held nonce, a custom-LLM
endpoint answering from a claim pack with one model call per turn and the composer's per-sentence
checks, at most 60 spoken words, a filler after 700 ms, `VOICE_SECONDS` reserved per turn and
`end_call` when they run out, an encrypted and scrubbed transcript purged after 30 days, and the
relay fallback (speech to text, our pipeline, text to speech). The ElevenLabs spike of PLAN 10.1 has
not run, so header templating in custom-LLM requests, the URL suffix, the bearer form and tool calls
from a custom LLM are still unverified; the contract therefore defaults to `RELAY`. The owner rules
bind: no comments, no deploys or cloud changes, no secret values printed, guards fail closed, no gap
admissions on screens.

## Decision

1. **A `voice/` package.** PLAN 3 names `voice/` as a backend module. It imports `providers` (the
   router, the quota ledger, ElevenLabs), `services` (knowledge view, answer events, app settings,
   managed keys, the craft resolver), `composer`, `schemas`, `research`, `core` and `models`; only
   `api`, `scripts` and `main` import it (`LAYER_IMPORTS`). It cannot live in `services`, which may
   not import `schemas`, and voice speaks the voice contracts directly. The SQL is one class,
   `voice/store.SqlVoiceStore`, behind the `VoiceStore` protocol, so every rule is tested with an
   in-memory store and the SQL has its own database tests.
2. **One ElevenLabs adapter**, `providers/elevenlabs.py` (PLAN 3 lists ElevenLabs among the
   providers): conversation token, conversation details and deletion, speech to text, text to
   speech, and the provisioning calls (agents, client tools, workspace secrets). The key comes from
   the managed key store (`ELEVENLABS_API_KEY`); every failure is an `ExternalFailure` with the
   shared kinds and never carries the key. Models are the newest the models page lists on
   2026-11-16: `scribe_v3` for speech to text and `eleven_v4_turbo` for speech. Speech requests send
   no `language_code`, which the speech page documents only for some models. The relay voice is
   `AppSetting` `voice.voice_id`, by default the voice of ElevenLabs' own text-to-speech example.
3. **A quota ledger beside the budget rules**, `providers/quota.py`: units used today on the budget
   time zone's day, what a role has left, and idempotent ledger rows. It sits in `providers` because
   it needs `budget.day_start` and PLAN 9 reserves quota with spend; it names no resource, so the
   media lane can use it for images and videos.
4. **Binding.** The nonce is the contract's HMAC (`kvs1.<session>.<exp>.<mac>`), recomputed from the
   row on every request and compared with the stored SHA-256 in constant time; it is minted once per
   session, bound to one ElevenLabs conversation and never sent. `exp` is `expiresAt` plus
   `maxDurationSeconds`, so migration 0006 adds `transport`, `expiresAt` and `maxDurationSeconds` to
   `VoiceSession`. A session may start within 120 s (`START_WINDOW_SECONDS`). A session left open
   is closed at that hard end by the next start or the daily upkeep, so the one-live-session index
   never locks a learner out. Every failed check of the custom LLM is the same 401 `LlmError`, and
   the bearer is checked before the body is read.
5. **One turn, no planner.** The claim pack is `knowledge_view.claims_for` for the craft and mode,
   loaded when the session starts and held per process (`VoicePackStore`, 10 minutes, 64 packs,
   reloaded on a miss). Claims are ranked by the word stems they share with the question, leaving
   out the craft's own name and request words, so "tell me about Ajrakh" ranks the strongest claims
   and an unrelated question makes no model call. `VERIFIED` speaks stored claims word for word with
   no model, as the text answer does. `HYBRID` makes one `VOICE_TURN` call through the router as the
   session's user, with the composer's schema narrowed to one section of at most three sentences
   and its parsing and per-sentence checks; there is no regenerate. A session without a craft
   resolves one per turn with the craft resolver. No live web runs mid-turn.
6. **The spoken reply** is the checked sentences, word for word, then short spoken source labels
   ("GI Journal 188", first author and year for papers and books, otherwise the head of the title)
   within 60 words; a sentence that would pass 60 is left out. A filler from a fixed table streams
   when the turn is not ready after 0.7 s. Client tools are decided from the cited claims
   (`show_sources`; `show_on_map` for place claims and `open_stage` with `offer_image` for stage
   claims, only on the session's own craft) and sent in the transcript's `actions`, not in the
   agent stream, until the spike shows a reply may carry text and a tool call (unverified item 5).
   `end_call` alone ends a turn when the day's seconds, the 40 turns or the call's time are used up.
7. **Seconds.** An agent turn reserves the wall-clock seconds since the session started less what is
   already reserved, under `voice:<session>:<turn>`; two overlapping turns can reserve one interval
   twice, which the reconciliation refunds. A relay turn bills the heard audio (last word's end)
   under `voice:<session>:<turnId>` and the reply audio (bytes at 128 kbit/s) under
   `voice:<session>:<turnId>:speech`, both capped at what is left. The reply is synthesised during
   the turn so `done` carries exact seconds; the audio is held per process for 15 minutes and
   synthesised again on a miss, billed under the same key, so never twice.
8. **The relay upload** is read by `api/multipart_form.py`: the body is capped while it streams and
   exactly one `audio` part is taken byte for byte. `python-multipart` would be the usual reader, but
   the lockfile cannot be regenerated on this machine (no `uv`), and one field needs no dependency.
9. **Privacy.** What was heard is cleaned of invisible characters and of email addresses (written or
   spoken as "name at host dot com"), phone numbers and Aadhaar-like numbers by
   `research/evidence.without_personal_data`, the one home of those patterns, before it reaches the
   model or the transcript. The transcript is Fernet JSON (`version` 1, turns, sources) under
   `TRANSCRIPT_ENCRYPTION_KEY`, written under a row lock that renumbers the turn, so overlapping
   turns cannot lose each other. Retention is the end plus 30 days, planned from the hard end when the
   row is made. A voice `Answer` row is linked to a `Conversation` with channel `VOICE`; its question
   is the fixed text "Voice turn", and nothing of the learner's words enters logs or `AnswerTrace`.
10. **Upkeep without a worker.** No worker exists yet, so `app/scripts/voice_upkeep.py` runs first in
    the daily Coverage enrichment box run: it closes lapsed sessions, purges transcripts past their
    retention, and reconciles ended agent calls from `metadata.call_duration_secs` (a refund row
    `voice-refund:<session>` for any surplus, nothing more charged), then deletes the conversation at
    ElevenLabs.
11. **Provisioning.** `app/scripts/provision_voice_agent.py` is idempotent: it creates or updates the
    workspace secret `KALAVIGYAN_VOICE_LLM_BEARER`, the four client tools by name, and the agent by
    `ELEVENLABS_AGENT_ID` or its exact name (two agents of that name stop the run). The agent is
    private, uses `custom-llm` at `<PUBLIC_API_URL>/api/voice/llm/v1` (ElevenLabs' examples give an
    OpenAI-style base URL and call `/chat/completions` under it; unverified item 2), sends
    `X-KV-Conversation-Id: {{system__conversation_id}}`, takes no client override, has the PLAN 10.4
    turn settings and system tools, records no voice, keeps conversations two days (one daily
    reconciliation plus margin) and is limited to `voice.max_live_sessions` (default 5, the voice
    load of PLAN 3.3; the bought plan's limit is unverified). `--dry-run` prints the body. It has not
    been run.
12. **Languages.** Voice offers the contract's `offered_voice_languages()` limited to the languages
    the voice turn composes in itself (`VOICE_TURN_LANGUAGES`, English): Hindi answers now come from
    the translation step of the text pipeline, which the voice turn does not call yet, and a Hindi
    call would only say that nothing was found.
13. **Availability.** `/answers/config` sends `VoiceAvailability`: configured only for a learner who
    may use voice (the `VOICE` capability and a verified email), when the transport's keys are set
    and ElevenLabs answers `/v1/user` (checked at most once a minute per process). Anything less
    hides voice.
14. **Secrets.** `seed_secrets.py` generates `VOICE_LLM_BEARER`, `VOICE_SESSION_HMAC_KEY` and
    `TRANSCRIPT_ENCRYPTION_KEY` like the other generated keys and copies `ELEVENLABS_AGENT_ID`;
    Deploy backend syncs all four from GitHub. Session starts are limited to 10 per user in 10
    minutes.

## Consequences

- Voice appears for verified learners once the keys exist and ElevenLabs answers; it runs as `RELAY`
  until the owner runs the spike and the provisioning script and sets `voice.transport` to `AGENT`.
- The ElevenLabs fixtures follow the documented shapes of 2026-11-16, not captured traffic; the
  spike replaces them with recorded responses.
- Hindi voice, the T2 passages and claim embeddings in the voice pack, a voice settings screen and
  a real worker are in `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
