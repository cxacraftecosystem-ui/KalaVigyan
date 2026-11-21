# 0014. Contracts for process science, region profile, voice and media

The contracts for process science, the region profile, voice and media are HTTP bodies in
`backend/app/schemas/`, each model refusing a body that breaks its rule, with one golden file per
shape. They settle the readings PLAN 7, 10 and 11 left open and fix the numbers 0015 to 0022 for the
batch built to them.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The lanes built to it | [0015](0015-science-engine.md), [0016](0016-region-profile.md), [0017](0017-voice-backend.md), [0018](0018-media-backend.md), [0019](0019-craft-page-and-region-panel.md), [0020](0020-voice-ui.md) and [0021](0021-media-ui.md) |
| The review that fixed it | [0022 Voice spend fails closed, a filtered style hint, region sources and one home per rule](0022-batch-3-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The next batch builds the science engine (0015), the region profile (0016), the voice backend
(0017), the media backend (0018), the craft page and region panel (0019), the voice UI (0020),
the media UI (0021) and a review pass (0022), partly in parallel. They meet at four HTTP
interfaces that PLAN 7, 8, 10, 11 and 14 describe but do not pin: which fields each answer
carries, how a level is derived, how a voice call is bound to one user, and which media
requests are accepted. The practice skills ask for the interface to be agreed and the shared
piece built first, with tests that pin both sides. PLAN 0 asks for a citation on every fact
and no review gates; the owner asks for no gap admissions on screens and no code comments.

## Decision

1. **Where the contracts live.** The four answers are HTTP bodies, so their models go in
   `backend/app/schemas/` (`science.py`, `region.py`, `voice.py`, `voice_llm.py`, `media.py`).
   They reuse the answer stream's `Citation`, `SourceRef`, `CraftRef` and `AnswerSentence`
   instead of copying them, so `schemas` may now import `research` (`LAYER_IMPORTS`;
   `research` imports only `core` and `models`, so no cycle is possible). The new literal types
   (`StageType`, `MaterialKind`, `MaterialRole`, `ReactionKind`, `EnvStat`, `MediaKind`) join
   `research/vocabulary.py`, the one place enum tuples become types. The models derive from
   `ContractModel` (frozen, unknown fields refused, camelCase on the wire), the style of every
   response contract; `APIModel` stays for the older request bodies. The OpenAI-compatible
   voice wire uses OpenAI's own snake_case and ignores unknown inbound fields, because
   ElevenLabs owns that request and adds fields; what we send back is strict.
2. **Rules live with the shapes.** Each model refuses a body that breaks its rule: a citation
   must carry its claim and level; a derived level is the weakest input (`weakest_level`); a
   balanced reaction has formulas, coefficients with greatest common divisor 1 and a checker
   version, an unbalanced one no coefficients; the equation string must equal
   `mhchem_equation(species)`; a condition's "sources differ" flag must equal the rule; a
   region value's aggregation must match its stat; a media job's asset, failure, refund and
   polling must match its status. The science engine and the services import these rules
   rather than re-implementing them.
3. **PLAN 7 readings.** An equation with every formula known that does not balance is capped at
   `HYPOTHESIS` with reason `unbalanced`. A reaction with a species that has no formula (an
   alizarin lake) is species-only: no equation, no cap, because it claims no stoichiometry.
   "More than 15 % (or 25 °C)" is read as 25 °C for temperatures, where a percentage of a
   Celsius value means nothing, and 15 % of the larger value for every other quantity,
   comparing range midpoints. Durations are in hours, concentrations in g/L, pressures in kPa.
   Stage columns without a cited claim (`durationText`, `tempMinC`, …) are not sent at all.
4. **Region readings.** A place is a district (from a cited `CraftLocation`) or a state of
   practice without a district place (cited to the master list). A district without a polygon
   shows its state's aggregates and says why. State aggregates exist only for stats that
   aggregate honestly (area-weighted means and shares, sums, minima, maxima); percentiles and
   uncertainty bounds are not invented for a state. `depthOrPeriod` is split by one pattern,
   and each value carries the grid it was read at (WorldCover is read at 40 m, not 10 m).
   Facets come from a dataset-to-facet table checked against the ETL catalogue. The boundary
   caption is PLAN 8's text, sent by the server so it has one home.
5. **Voice binding.** ElevenLabs' token endpoint returns the conversation id with the token, and
   clients cannot set `system__` variables. The server therefore binds the session to that id
   when it mints the token, and the agent's `custom_llm.request_headers` carries
   `{{system__conversation_id}}` back on each request. The nonce of PLAN 10.2 is an HMAC over
   user, session, conversation id and expiry whose hash is stored on the row and re-checked on
   every turn. It never leaves the server, so the browser receives only the token and
   non-secret session facts. A browser-carried nonce (dynamic variable or extra body) was
   rejected: the browser that holds it already holds the conversation, so it adds no protection
   and widens what the client holds. The client extra body and all overrides are off and never
   read. Header templating in custom-LLM headers is not on ElevenLabs' official page, so the
   transport defaults to `RELAY` (speech to text, our pipeline, text to speech) and the owner
   switches to `AGENT` only after the spike shows it. Every other unverified ElevenLabs
   behaviour is listed in the contract.
6. **Voice routes.** CloudFront forwards every path and nginx proxies `location /`, but the app
   mounts only `/api`; the custom LLM is `/api/voice/llm/v1/chat/completions`, called at the
   CloudFront origin rather than through the web proxy, which refuses cross-site calls. A test
   reads the Terraform and nginx config so a later routing change breaks it.
7. **Voice billing and privacy.** Seconds are reserved per turn from the server's clock since the
   last reservation, then reconciled to ElevenLabs' `call_duration_secs` with a refund; relay
   turns bill measured audio. The user's words live only in the encrypted transcript, so a
   voice `Answer` row stores no question text. Voice offers only languages the answer pipeline
   writes (English now).
8. **Media readings.** Since PLAN 0 made `APPROVED` the default status, PLAN 11's "APPROVED
   claims plus provisional claims with quote check PASS" is read as reviewed or verified
   claims, plus provisional claims with a passing quote; hypotheses never enter a prompt. A
   prompt needs at least 2 such claims and uses at most 8. A style hint is a small character
   set with a banned-word list, refused with a sentence rather than silently cleaned. At most 3
   active jobs per user. Options are their own route, so the craft page's process answer stays
   free of quota state and buttons are drawn only for what is listed.
9. **Golden files and the client.** One hand-written golden file per response shape in
   `shared/`, built from real Kutch Ajrakh rows (seed claim ids, GI Journal and Mingei sources,
   stage ordinals, `EnvDataset` rows) where real data exists. Backend tests reproduce each byte
   for byte from the models; the region values and media URLs are hand-written shapes. The
   client gets a small runtime shape kit (`frontend/lib/shape.ts`) instead of a schema
   dependency: each shape is typed against its TypeScript type, so the compiler checks the
   shape covers every field, and parsing refuses unknown fields and values, which a cast would
   not. Frontend checks now run when any `shared/*.golden.*` file changes.
10. **Decision numbers** for the batch are fixed: 0015 science engine, 0016 region profile, 0017
    voice backend, 0018 media backend, 0019 craft page and region panel UI, 0020 voice UI, 0021
    media UI, 0022 review fixes.

## Consequences

- No route, service or screen exists yet; each lane builds against these models and must make
  its handler produce the golden file.
- Lane 0015 adds storage for condition readings and a reaction-to-claim link; lane 0016 adds
  `DistrictEnvValue.resolution`; lane 0017 runs the ElevenLabs spike before `AGENT` is offered.
  These are in the debt register until built.
- A badly formed stored row fails its answer loudly instead of reaching the screen.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
