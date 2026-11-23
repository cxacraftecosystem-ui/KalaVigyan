# Technical debt register

What is knowingly below standard, why it was left, and what clears it. Add an entry in the same
change that takes the shortcut; delete it in the change that clears it. Engineers and reviewers read
it before changing an area. The number of entries may only fall: `tools/hygiene_check.py` fails a
change that leaves more `### ` entries than `tools/hygiene_baseline.json` records (decision 0163).

| For | Read |
|---|---|
| Why an area is built the way it is | [decisions/README.md](decisions/README.md) |
| Where the work stands | [PROGRESS.md](PROGRESS.md) |
| The hygiene baseline of files and functions over budget, and of this register's entries | `tools/hygiene_baseline.json` |

```mermaid
%%{init: {"theme":"base","fontFamily":"Inter, ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif","themeVariables":{"fontSize":"15px","primaryColor":"#F2E9FE","primaryTextColor":"#1E1B2E","primaryBorderColor":"#9148D2","secondaryColor":"#FAEECD","secondaryTextColor":"#1E1B2E","secondaryBorderColor":"#CD9200","tertiaryColor":"#F3F1FA","tertiaryTextColor":"#1E1B2E","tertiaryBorderColor":"#A7A3BC","mainBkg":"#F2E9FE","nodeBorder":"#9148D2","nodeTextColor":"#1E1B2E","lineColor":"#AA69E9","textColor":"#857F9E","edgeLabelBackground":"#F9F5FF","clusterBkg":"#F9F5FF","clusterBorder":"#D6B6FB","titleColor":"#762CB1"}}}%%
flowchart LR
  S([A shortcut taken]) --> E[An entry<br/>what, why, what clears it]
  E --> C[The work that clears it]
  C --> D([The entry deleted<br/>in the same change])
  classDef accent fill:#762CB1,stroke:#5F1C93,color:#FFFFFF
  class E accent
```

Last reviewed: 2026-11-22.

## Infrastructure

### CloudFront to origin is plain HTTP

- **What:** CloudFront reaches nginx on the EC2 box over HTTP on port 80 (`docs/RUNBOOK.md`,
  `infra/terraform/cloudfront.tf`). The origin is protected by the CloudFront-only security
  group and the `X-Origin-Verify` header, but the hop between CloudFront and the box is not
  encrypted. The designer and documentation portals use the same pattern.
- **Why left:** TLS ends at CloudFront; there is no custom domain or origin certificate yet, and
  the pattern matches the portals so they can be changed together. Deferred by the owner on
  2026-11-22 ("we will take care of it later on") as D43 of the cross-portal list of decisions
  deferred to launch (`C:/dev/IIT/docs/DEFERRED_FOR_LAUNCH.md`).
- **Clears it:** an origin certificate (custom domain with certbot, already installed and
  unused on the box) and `https-only` origin protocol, done for all three portals in one change,
  with a certificate-expiry check in each post-deploy run.

## Backend structure

### Scholarly adapters: what waits on keys and Wiley's token (decisions 0005, 0139)

- **What:**
  - Fixtures that are not recordings: `semantic_scholar_search.json` wraps two recorded paper
    records in the search envelope (search answered 429 without a key);
    `springer_nature_search.synthetic.json`, `springer_nature_jats.synthetic.xml`,
    `springer_nature_jats_none.synthetic.xml` and `elsevier_article.synthetic.xml` are hand-written
    from the documented shapes (`backend/tests/sources/fixtures`); CORE's `journals` is tested on the
    recorded work with the documented field added, since the recording carries none.
  - The configured `ELSEVIER_API_KEY` may search Scopus but not read abstracts or full text
    without an institution token, so `elsevier` fetch is `not_found` for every record.
  - OpenAlex without `OPENALEX_API_KEY` allows $0.10 a day per address, about 100 searches; after
    that it answers 429 until midnight UTC and the shared hold pauses every process.
  - The planner reads a closed DOI from its publisher (`LiveSources.publisher`, decision 0167), but
    no publisher is built until `ELSEVIER_INSTTOKEN` or `SPRINGER_NATURE_API_KEY` is set.
  - Wiley TDM is not read: it serves PDF only, behind a redirect, with its token, and the fetcher
    sends no keys.
- **Why left:** no `OPENALEX_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` or `SPRINGER_NATURE_API_KEY` and
  no Elsevier institution token exist yet (the owner's to obtain); Wiley's PDF needs the fetcher to
  carry one host's token.
- **Clears it:** the owner sets the three keys (Springer Nature's with text-mining terms) and
  `ELSEVIER_INSTTOKEN`, each tested from the settings screen, and the fixtures are recorded then
  (CORE's with `journals`); read Wiley's PDF once the fetcher can carry one host's token.

### Web search and fetcher: recordings and the box (decisions 0007, 0139)

- **What:** the SearXNG and Brave fixtures (`backend/tests/sources/fixtures/*.synthetic.json`) are
  hand-written to the documented shapes, and `kv-fetcher` with its parser processes has not been
  smoke-tested on the box.
- **Why left:** SearXNG runs only on the box, there is no Brave key on the laptop, and the box is
  reached only through a deploy.
- **Clears it:** after the next deploy, check `/health`, one HTML and one PDF fetch, the parser
  processes staying under the 768 MB cap and the `WebFetch` row an answer writes; then record one
  SearXNG and one Brave answer to replace the synthetic fixtures.

### Stored-knowledge retrieval: what is left (decision 0008, round 4)

- **What:** round 4 cleared stamps per embedding model with re-embedding, cleared vectors on a text
  change, embedding after the seeds on every release, the Indic text ranking and the seed import's
  passages (`docs/contracts/retrieval.md`); decision 0166 stamped knowledge pieces and made the
  gates and the piece store compare vectors of one model. Left: the Wood Handbook import has no
  passages, because the repository holds no text of the cited edition (FPL-GTR-190).
- **Clears it:** vendor the pages of FPL-GTR-190 (a US government work), or give FPL-GTR-282 its
  own source and re-cite the wood claims after a quote check.

## Checks not automated yet

- **Nesting depth** (budget 3) is not measured by the hygiene check.
- **Frontend size budget** (about 150 lines per component file): 33 `.tsx` files are over it on
  2026-11-16, the largest `components/ui/SearchableSelect.tsx` (1243),
  `app/(protected)/admin/access/page.tsx` (813), `components/forms/DateTimeField.tsx` (743).
  Many are ports from the designer portal.
- **Frontend import boundaries** are not linted.
- **Geo ETL tests** (`etl/geo/tests`) run, with ruff, only at the start of a Geo ETL dispatch
  (decision 0043); a push that changes `etl/geo` is not tested until the next dispatch.
- Clears it: a lint rule set for size and boundaries with a baseline for the existing files, a
  nesting count in `tools/hygiene/budgets.py`, and a push-triggered test job for `etl/geo`.

### Planner and tiered research: gaps left on 2026-11-16 (decision 0009)

- **What:** (1) The pack holds documents, not quotes: the `WEB_READ` reader that extracts
  verbatim quotes for the composer is not built. (2) References are followed only as DOIs written
  in the text, through Crossref, which returns abstracts only; links in pages and reference lists
  without DOIs are not followed. (3) Facet coverage counts claims that share a word with the
  target; it does not judge whether they answer it. (4) Every query runs on every source of its
  tier, including Commons and PubChem for questions they cannot serve (each answers quickly with
  no hits). Every answer writes its `AnswerTrace` rows since decision 0146, and a question's facet
  targets are embedded in one call since decision 0166.
- **Why left:** the `WEB_READ` reader is a model call per document read, and the owner's rule of
  2026-11-23 keeps each answer's model calls at today's while answers are measured (decision
  0165); a better coverage judgement and the routing need the known-answer checks to calibrate
  against; the OpenAlex adapter does not read `referenced_works` yet.
- **Clears it:** the reader turns documents into quoted evidence once the owner allows its calls;
  follow reference lists through OpenAlex `referenced_works`; route facet types to the sources that
  can serve them once the checks show which do.

## Science, region, voice and media contracts (decision 0014)

### ElevenLabs behaviour not yet verified

- **What:** the voice binding rests on `custom_llm.request_headers` substituting
  `{{system__conversation_id}}` and on `custom_llm.api_key` arriving as a bearer, neither on
  ElevenLabs' official pages; also unverified are the URL suffix, custom-LLM tool calls reaching
  `end_call` and client tools, Hindi in agents, CSP hosts and the plan's retention minimum
  (`docs/contracts/voice.md`). Relay text to speech cannot run with zero retention
  (`enable_logging=false` is enterprise only).
- **Waits on:** the agent spike, which is the switched-off voice call (decision 0035), not another
  paid run: the paid check of 2026-11-23 (run 45112123057) refused its agent turn because no
  ElevenLabs agent, agent key or voice session key is provisioned. Once the spike provisions them,
  the paid check's agent turn settles the header, the bearer and the suffix (commit its
  `agent_turn_events.json` as `backend/tests/voice/fixtures/agent_turn_events.json`;
  `voice.transport` stays `RELAY` until it passes). Tool calls, Hindi in agents, the CSP hosts and
  retention need a browser call on the box; retention also needs an enterprise plan or the Gemini
  voice.

## Voice backend (decision 0017)

### Voice in other languages is not yet heard or read by its speakers (decisions 0025, 0157)

- **What:** what a test can check is checked for every offered language: a relay turn sends Scribe
  and speech their codes and speaks the language's source word, and every phrase whose English says
  no carries its language's negation (decision 0157, item 7). No call with a real key has run in a
  language other than English, and Scribe's published accuracy is Scribe v2's: Urdu's band is
  moderate (25-50% word error), so an Urdu question may often be misheard. The spoken phrases (the
  `voice.*` entries of `backend/app/data/interface_words/`) were written by the voice lane and no
  native speaker has reviewed them. In `AGENT` nothing yet tells the agent a session's language: the
  token takes none and client overrides are off, so the agent hears in its own language until
  `language_detection` switches; the presets are not provisioned.
- **Why left:** a recorded turn needs the owner's ElevenLabs key, and a review needs a reader of
  each language.
- **Clears it:** a reader of each language records a review on the `voice.*` entries of its file,
  correcting any phrase first (decision 0157, item 5); the spike records one relay turn per language
  and one agent call in Hindi; if Urdu misses too often, drop `ur` from `STT_LANGUAGE_CODES` (voice
  then stops offering it) or try `scribe_v3` with Hindi as a `secondary_language_codes` hint; the
  spike decides whether the agent gets an `agent.language` override or one agent per language.

### An agent call cannot be hung up from our side

- **What:** after an `AGENT` call's row ends, the ElevenLabs call can run on to the agent's 600 s,
  which reconciliation charges, so the user may go below zero for the call's day (the settlement
  row counts on that day, decision 0140).
- **Why left:** ending a conversation needs an ElevenLabs endpoint the spike has not confirmed; it
  is bounded by the day's seconds, the turn and replay limits and the 40-turn cap (decision 0022).
- **Clears it:** end the ElevenLabs conversation when the row ends, once the spike shows how.

## Voice UI (decision 0020)

### The live agent call has not run in a browser

- **What:** the release check `e2e/production/voice.spec.ts` drives the dock on `/design/voice`
  at desktop and phone widths in both themes: the notice, a relay turn recorded from Chromium's
  fake microphone, sent, answered from the relay goldens and played, and the end, with the dock
  inside the screen and its contrast checked (decision 0140). The `AGENT` path (the ElevenLabs
  WebRTC call joining a LiveKit room, the server writing each turn to the transcript as it is
  spoken) has not run, nor has the dock above the bottom island, since no page with the island
  mounts it while the call is switched off (decision 0035).
- **Why left:** an `AGENT` call needs a real ElevenLabs agent and conversation (the spike); the
  dock's page comes back with the call.
- **Clears it:** one real `AGENT` call once the spike passes, and the same check run on the page
  that mounts the dock when `VOICE_CALL_ENABLED` brings the call back.

### The dock's recorded bit rate is unmeasured in Safari

- **What:** the relay recorder asks `MediaRecorder` for the session's `audioBitsPerSecond`
  (32 kbit/s) and sends a turn at nine tenths of `maxAudioBytes`, so a full minute fits only at
  36,000 bit/s or less. The browser smoke measures Chromium on every pull request
  (`frontend/e2e/voice-rate.smoke.spec.ts`: `audio/webm` at 28,269 and 28,245 bit/s on 2026-11-23,
  decision 0161); Safari records `audio/mp4` (AAC), and whether it keeps to the asked rate is
  unmeasured.
- **Waits on:** a Safari run, which no GitHub runner has (Playwright's WebKit is not Safari's media
  stack): a person with a Mac runs the smoke spec in Safari once. If it records above 36,000 bit/s,
  raise the `audio/mp4` byte ceiling in `docs/contracts/voice.md` and `schemas/voice.py` by its
  measured rate.

## Science engine (decision 0015)

### Seeded crafts without a cited reaction, a firing stage or a stated temperature

- **What:** reactions now come from the science seed (Kutch Ajrakh, Bagh, Machilipatnam) and
  from the curated dossiers of nine crafts (those three, Bagru, Sanganeri, Bastar Dhokra, Agates
  of Cambay, Firozabad Glass, Cane and Bamboo, through `services/curation_structure`). What is
  left: Dabu (its dossier holds no reaction) and Akola stages have materials and tools but no
  reaction, because no source the seed or a dossier holds states one; no craft has a process with a `FIRE` stage, so kaolinite dehydroxylation has no
  reaction (the terracotta seed is sub-category mechanism chains); four stage concepts state no
  ordinal (Akola mud soaking and paste preparation, Machilipatnam and Sanganeri block carving) and
  get no stage, since no `PRECEDES` edge joins them to their craft's ladder: the seed's only one
  among them says mud soaking precedes paste preparation (`tests/science/test_seed_stage_order.py`);
  and no seed claim states a temperature or pH, so no seeded reading is checked against an
  envelope.
- **Why left:** reactions, readings and a stage's place are written only as a cited quote states
  them; the sources still to find are a GI application or a chemistry paper on Dabu mud resist and
  on Akola's mud and indigo work (and where its mud stages fall), a source placing block carving in
  the Machilipatnam and Sanganeri processes, a curated clay craft's firing schedule, and a dyeing
  source stating a bath temperature or pH. Finding them is research through the KalaVigyan MCP
  server (`search_sources`, `read_source`, then `propose_structure` for a reaction or a stage).
- **Clears it:** a dossier or seed reaction for Dabu and Akola from such a source, a curated clay
  craft with a `FIRE` stage and its stated temperature, and each unordered stage's place written
  from a source that states it (its ordinal, or a stated `PRECEDES` edge to a ladder stage, which
  `claim_seed.stage_rows` would then be taught to read).

## Answers in Indian languages (decision 0023)

### The read-back check is not yet calibrated by readers

- **What:** a translation is read back into English and refused when its reading loses a figure,
  a negation or a hedge, adds one, or keeps fewer than half the English's terms (decision 0157,
  item 1). That half is the quote overlap floor, chosen without a reader: no speaker of Hindi or
  Tamil has yet judged which sentences drifted, so the check may refuse a faithful sentence (it
  then shows in English) or keep a drifted one whose reading happens to share the English words.
- **Why left:** the calibration needs a reader of each language.
- **Clears it:** a reader of Hindi and one of Tamil read a known-answer answer in their language
  (the production E2E's Known Answers report gives each translated sentence beside its English;
  the Tamil one is asked on the site), and for every sentence they record, as a case in
  `backend/tests/research/test_translation_meaning.py`, the English, their own literal English of
  the translation and whether it kept the meaning; `READ_BACK_TERMS_KEPT_MIN` is then set so the
  check decides every recorded case as its reader did.

### Interface words in other languages wait for their readers

- **What:** the fixed words of the answer screen (the provenance rail and the actions), a stored
  answer's headings and follow-ups and the status lines are shown in an answer language only from
  a reviewed entry of `backend/app/data/interface_words/` (decision 0157, items 3 to 6). The Hindi
  and Urdu essay words are sourced from the Kutch Ajrakh monograph and the Urdu board (جواب, ماخذوں
  سے, محفوظ کریں, اس جواب کا حوالہ دیں and the rest) but no entry is reviewed yet, "Saved",
  "Saving", "Removing" and one source have no source, and the other languages, the headings, the
  follow-ups and the status lines have no entries. The not-enough-evidence message and the errors
  are composed in English and have no entries at all. A craft's name stays as it is written in
  English, as the monograph writes it.
- **Why left:** a reviewed word needs a reader of its language; approving a design is not
  reviewing its words (the board and the monograph disagree on two Urdu words).
- **Clears it:** a reader of each language supplies the missing words and records a review on
  each entry they approve (decision 0157, item 5), the Urdu reader first, choosing between the
  board's and the monograph's readings; then the templates of the not-enough-evidence message and
  the errors join the lists the same way.

## Media backend (decision 0018)

### Gemini video not yet seen live

- **What:** the paid check of 2026-11-23 saw an image made live
  (`backend/tests/media/fixtures/image_completed.json`, decision 0161); no clip has been made yet,
  so the video fixtures follow the documented shapes, not captured traffic. The paid checks' `gemini_video` step (`scripts/paid_check_video.py`, decision
  0179) makes one 8 s `gemini-omni-1.2-flash` clip through `GeminiMediaWire` with the job's
  requested output and keeps, as fixtures to be, the start, the first open poll and the finished
  interaction (`video_started_recorded.json`, `video_polling_recorded.json`,
  `video_completed_recorded.json`), the `DELETE /v1beta/interactions/{id}` reply
  (`video_deleted_recorded.json` and its status), the clip (`gemini_video.mp4`) with its exact
  duration, size and whether it came silent (`silentAsAsked`), how long it took
  (`secondsToFinish`, against the job's 240 s attempt) and whether `media/output.checked_output`
  would store it. Still unseen after that run: the shape of an `image` input that would make the
  requester's stage image the clip's first frame, because the documented shape is ambiguous (an
  `image` block before the text in `input`, with `generation_config.video_config.task`
  `image_to_video` shown only as an optional fallback; no field names the first frame, which the
  position and the prompt imply; and the examples wrap `input` both as a plain list of blocks and
  in a `user_input` step), so videos stay `text_to_video`, since a wrong input fails every clip;
  and how a safety block reads, which no paid call can be made to show.
- **Waits on:** the lead dispatching the step once, after this release is on the box, with only the
  clip (`gh workflow run paid-checks.yml -R cxacraftecosystem-ui/KalaVigyan --ref main -f video=true
  -f narration=false -f music=false -f image=false -f speech=false -f agent=false`, the owner's
  approval of 2026-11-23), then committing the recorded replies over the documented fixtures in
  `backend/tests/media/fixtures` (the clip's base64 cut to a small MP4, as the image's was) and
  correcting `gemini_media` and `MEDIA_OUTPUT` where they differ.

### Community and caste names caught by group words only

- **What:** a claim, stage name or style hint is kept out of a prompt when it uses a group word in
  the singular or plural (`schemas/media.NAMED_GROUP_WORDS`, decision 0022); a community named
  without one (a surname or cluster name alone) still passes, and
  `depictsNamedCluster` compares only the craft's located place names.
- **Why left:** no register of community and caste names exists; PLAN 13a names them only from
  cited sources.
- **Waits on:** the owner's and the governance lane's decision to keep the named practitioners per
  craft as cited data; the claim set and the named-cluster flag then check against it.

## Yahoo sign-in (decision 0026)

### Yahoo sign-in not yet seen running

- **What:** the Yahoo app is registered and live: `YAHOO_CLIENT_ID`, `YAHOO_CLIENT_SECRET` and
  `NEXT_PUBLIC_YAHOO_CLIENT_ID` were set on 2026-11-16 and production's `/auth/config` reports
  `yahooEnabled` (checked 2026-11-23). No account has signed in with Yahoo yet (production has
  password and Google accounts only), so the token endpoint's acceptance of the secret in the form
  body and of the PKCE parameters is still taken from DR, where it has run since 2026-10-10.
- **Clears it:** one sign-in with a rostered Yahoo address on the production login page.

## First-password proof (decision 0028)

### First-password proof not yet seen in a browser

- **What:** the route tests (`backend/tests/db/test_first_password_db.py`, the Google and Yahoo
  proofs, the two-step order, a recovery code and a locked second factor) and the card's unit spec
  (`frontend/e2e/first-password-unit.spec.ts`) run on every push, and migration
  `0011_first_password_proof` runs on Postgres in Backend checks, but no person has yet added a
  password in Settings through the real Google or Yahoo round trip.
- **Why left:** the round trip signs in to Google or Yahoo in a browser with a real account, which
  no check in the repository can do.
- **Clears it:** after a deploy, a person adds a password in Settings from a Google-only account and
  from a Yahoo-only one.

## Understanding and depth (decision 0031)

### Comparison questions research the lead craft only

- **What:** since decision 0064 a comparison sets up to three crafts beside the lead one and each
  section shows a `compare` block, but live research and composition still run for the lead craft;
  the compared crafts' cells come from what is already stored about them.
- **Why left:** researching every compared craft multiplies the answer's spend; the curation run
  fills the stored claims each craft's cells read.
- **Clears it:** a per-craft research share inside the answer's budget for compared crafts with
  few stored claims in the section's field.

## Asking screen (decision 0036)

### Dictation languages not yet tried on each browser

- **What:** the plan (2.5) asks for each answer language to be checked on each target browser
  before it is offered. The screen offers dictation in all 13 answer languages (`<code>-IN`
  locales, `lib/dictation.ts`) wherever the browser has the Web Speech API, hides a language the
  browser reports unavailable (`SpeechRecognition.available`) or refuses
  (`language-not-supported`), but nobody has yet dictated in Odia, Punjabi, Assamese or Urdu on
  Chrome, Edge and Safari, or checked Android Chrome's continuous mode, which is known to repeat
  final words.
- **Why left:** nothing runs on the laptop, and the production E2E drives a headless browser with
  no microphone.
- **Clears it:** after the deploy, dictate one sentence per language on Chrome, Edge and Safari
  (desktop and Android Chrome) and record what each does here; switch Android Chrome to
  single-utterance mode if its repeats show.

## Pictures and terms (decision 0034)

### Relevance is by text only

- **What:** plan 2.7 asks for one cheap vision call on the top candidates; every picture is
  chosen by its words against the claim text (`relevance: TEXT`), so a picture whose title and
  description happen to share two words with a claim is shown even if it depicts something else.
  A picture stored for a claim is now reused rather than searched again (decision 0166), so a
  vision verdict would be paid once per picture, not once per answer.
- **Why left:** a `CAPTION` call on the top two candidates of every section adds two model calls
  and their image tokens to every answer, and the owner's rule of 2026-11-23 keeps each answer's
  model calls and input tokens at or below today's while answers are measured against Opus and
  Sonnet (decision 0165).
- **Waits on:** the owner's choice after that measurement; then a `CAPTION` route call on the top
  two candidates per section, recorded as `VISION` on `MediaRefClaim`, dropping a picture the model
  says does not show the claim (`section_images.stored_items` already serves a stored `VISION`
  verdict).

## Listen and the switched-off call (decision 0035)

### Narration heard in English and Hindi only

- **What:** the paid check of 2026-11-23 heard `eleven_v4` on `/with-timestamps` in English and
  Hindi: accepted, the alignment spelling the text code point for code point, 882 and 765 characters
  a minute (`backend/tests/voice/fixtures/narration_with_timestamps.json` and its Hindi sibling,
  decision 0161). It also showed Hindi skipping square-bracketed words as an audio tag, so Listen now
  sends them as parentheses; that a parenthesis is read in Hindi, and the alignment in the eleven
  other languages, are unheard. A mismatch fails loudly, and Listen then reads with the Gemini voice.
- **Waits on:** the next paid check, whose narration step now sends the text as Listen does and
  reports `parenthesisedSeconds`; the other languages wait on a reviewed sentence in each for
  `paid_check_steps.NARRATIONS`, as interface words are reviewed (decision 0157).

### The Gemini read-aloud has not reached Gemini

- **What:** Listen's fallback voice (`GeminiMediaWire.read_aloud`, decision 0161) follows the
  speech page of the Gemini documentation read on 2026-11-23: `POST /v1beta/interactions` with
  `gemini-3.8-flash-tts`, the voice in `generation_config.speech_config`, and a RIFF WAV of 24 kHz
  mono 16-bit PCM in the last `audio` block of the `model_output` step. No request has reached
  Gemini, so that shape, whether the `Api-Revision` header the media wire sends is accepted, the
  real speaking rate behind the 1,000-characters-a-minute hold, and whether a cited sentence's
  angle brackets are read as text rather than as an inline speech tag are unverified.
- **Waits on:** the paid check run by the lead (`.github/workflows/paid-checks.yml`, decision 0154),
  whose `gemini_speech` step reads one sentence and parses it as Listen does; commit its
  `speech_completed.json` as a fixture of `backend/tests/media/test_gemini_speech.py`. A refusal
  there names what to change in `providers/gemini_media.py`.

## Expert panel (decision 0046)

### The reading share does not steer queries

- **What:** each seat's preferred kinds take every other early read of what was found, but which
  kinds are found depends on the queries the plan call writes; GI journals and government reports
  come mostly from the web tier and only when a query looks for them.
- **Why left:** the plan call is told each seat's kinds; reserving queries per tier would split an
  already small section share further.
- **Clears it:** a measured look at which kinds Expert sections read, then a tier share in
  `planned_queries` if seats' kinds are missed.

### The panel call has not met Claude Sonnet yet

- **What:** the seat, retake and difference calls are tested on their route (the builder compose
  model, `answer_routes.BUILDER_TUNING`, Claude Sonnet 5.5 on the answer's headroom;
  `tests/experts/test_panel_retakes.py`) and against recorded replies, but no production answer
  has been read for its views and an "Experts differ" card.
- **Why left:** it needs a paid production run, which only the lead dispatches.
- **Clears it:** the production questions run dispatched with `questions=true`: its Expert answer
  carries a note of the panel's views and Experts differ pairs (`e2e/production/expertPanel.ts`),
  read with the `COMPOSE` spend of that answer in Usage.

## Phase C contract (decision 0054)

### Numbers the explainer computes are not checked

- **What:** the static check reads the numerals a generated explainer writes (decision 0061 added
  figures against letters, list starts and CSS counters), not the numbers its code computes. A
  value worked out from data values and an input's position (the fixture's `n *
  data.fallLowFeet`, which shows 20 to 150 feet as the slider moves), a numeral assembled from
  allowed constants (`'1' + '8' + '6' + '8'`, `1000 + 12 * 12 * 6`) or a unit conversion
  (`data.depth * 9 / 5 + 32`) reaches the reader without being a cited value.
- **Why left:** a frame guard that refused every shown numeral missing from `kv-data` (a
  `MutationObserver` and wrapped `fillText`) would hide the fixture's own explainer the moment
  its slider moves, since 20 is not a data value; telling a derived figure from an invented one at
  run time needs a rule the plan does not have.
- **Clears it:** an owner rule for derived figures (for example, only products of a data value and
  an input step the data object names), then that runtime guard in `lib/sandboxFrame`'s prelude
  posting a refusal that `SandboxFrame` turns into hiding the block. Waits on the owner's rule
  (checked again on 2026-11-22: the static check covers code numerals since decision 0061).

## Generated explainers (decision 0055)

### A redraft can run past the builder's wait

- **What:** the generated explainer drafts within `SIMULATION_BUDGET_SECONDS` (60 s) and redrafts
  only when the time left is at least what the first draft took (decision 0142), so the registry's
  wait no longer cuts a redraft, but a slow route can still leave a section without its explainer:
  the builder then records `OUT_OF_TIME` or `NO_TIME_TO_REDRAFT` under `Answer.plan.builds`.
- **Why left:** how often that happens is a production measurement. Checked 2026-11-23: no
  production answer has `plan.builds` yet, because the record shipped late on 2026-11-22 and no
  answer has finished since (the two later rows are production checks stopped mid-stream).
- **Clears it:** the lead reads `plan->'builds'` of a week of Expert answers on production. If
  `OUT_OF_TIME` and `NO_TIME_TO_REDRAFT` are a large share of the `simulation` outcomes, build the
  explainer after `section_done` as a late block, which needs a stream event the contract does not
  have yet; otherwise delete this entry.

## What-if lab (decision 0056)

### Temperatures and water sources are not offered as inputs

- **What:** inputs are only a stage's stored materials. A temperature (a stage condition's
  readings) or a water source held only as a concept ("Iron content of process water") is never
  an input, so the plan's "temperature" and "river or well water" examples appear only when the
  waters are stored materials with alternatives.
- **Why left:** no stored row relates a condition's stated range, or one water source, to an
  outcome; a what-if over them would need numbers or outcomes a model would have to supply.
  Checked 2026-11-23 (decision 0160): the dossier model holds no stage conditions and the science
  seed's conditions carry readings and no outcome; it waits on condition ranges a source ties to
  outcomes, found and cited through the KalaVigyan MCP research tools and curated.
- **Clears it:** curation storing condition ranges with the outcomes a source ties to each, or
  water sources as materials with their relations; then an input kind over them in a version 2.

## Zoom story and timeline map (decision 0057)

### No open-access paper figure is searched for the fibre level

- **What:** the fibre level comes only from Commons and Openverse micrographs; the contract's
  "open-access figure whose `sourceId` is the stored paper" has no adapter (no figure search in
  Europe PMC or a publisher's open figures), so most crafts show no fibre level.
- **Why left:** no figure source exists to reuse, and a new adapter needs its own recorded tests
  and licence reading per figure.
- **Clears it:** one figures adapter over an open-access full-text source (for example the
  figures of Europe PMC's open-access articles, each with its article's licence), checked on
  recorded responses, and the fibre search asking it after Commons and Openverse.

### Picture levels are read from English words

- **What:** a picture's level is read from its title and description against short English word
  lists (`zoom_pictures.LEVEL_WORDS`), and the craft's fibre from a list of fibre names
  (`FIBRE_NAMES`); a picture titled in another language or with an unlisted word ("hand block
  print", "karigar") finds no level, and a fibre material named only by a local word ("kora")
  gives no fibre level.
- **Why left:** a vision call per candidate would spend from the answer for a picture the reader
  may never open; the lists hold the words the stored pictures use.
- **Clears it:** the glossary's terms tagged with a zoom level, or a vision check of the top
  candidate per level within the answer's headroom.

## ElevenLabs music, sound effects, image and video (decision 0058)

### ElevenLabs prices are unverified

- **What:** the API pricing page, its own FAQ and the scale-tier page disagree (music $0.150 or
  $0.275 a minute, sound effects $0.120 or $0.060 a minute or per generation); image and video
  prices appear only on the scale-tier page. The catalogue keeps the higher figure per second or
  image (`providers/catalogue_specs.py`, `_ELEVENLABS`), so Usage may show more than ElevenLabs bills.
- **Waits on:** the paid check run by the lead and the ElevenLabs invoice of that month: compare
  the invoice with the check's `paid_checks_report.json` and Usage, then set the confirmed prices
  and `price_verified` true, or set admin price overrides.

### Flows content is fetched only from the host the reference shows

- **What:** since decision 0061 a finished image or video is fetched only from
  `storage.googleapis.com` (`providers/elevenlabs_download.DOWNLOAD_HOSTS`), the host of the
  reference's example; the OpenAPI document describes `content_url` only as a signed URL and
  promises no host, so a move to another host fails every ElevenLabs picture and clip loudly.
- **Why left:** an unpinned host could stream any body into the API box; ElevenLabs image and video
  are route choices no seeded chain uses.
- **Waits on:** one paid ElevenLabs image or video, which the owner's approval of 2026-11-22 does
  not include; if it names another host, add it to `DOWNLOAD_HOSTS` after checking the reference.

## Zoom, timeline and film renderers (decision 0060)

### A place beyond the India frame is a signpost, not a pin

- **What:** the timeline draws a placed point outside the India frame (Fustat in the fixture) as
  a signpost at the frame's edge pointing toward it, so the reader sees its direction and its
  Wikidata item but not its distance or neighbourhood.
- **Why left:** the frame is fixed by `components/map/projection.ts`; widening it for one point
  would shrink India on every timeline, and drawing other countries is refused.
- **Clears it:** an inset frame for points abroad (the same projection, its own bounds, the plain
  ground only), chosen by the timeline when it places a point outside the India frame.

### Film volumes on iPhones and iPads not yet heard

- **What:** where a browser fixes `HTMLMediaElement.volume` (iOS Safari), the bed and the cues now
  play through one Web Audio gain each (`components/answer/film/FilmSound.tsx`, decision 0154),
  loaded with CORS from the media bucket (`cors_allowed_origins` holds the site's origin). The unit
  specs check the detection and the levels; the production E2E's Chromium never takes that path.
- **Waits on:** a person playing a film with music on an iPhone or iPad and moving both sliders.

## Climate and risk, and ask the map (decision 0065)

### Groundwater values only for Rajasthan, and not yet loaded

- **What:** `climate_risk.groundwater` can show stored groundwater figures only for Rajasthan's 33
  districts as on 31 March 2023 (`OGD_GW_RESOURCES_RAJASTHAN_2023`); a craft in any other state shows
  groundwater only through cited claims. None is loaded yet: the Geo ETL run of 2026-11-23 (run
  45088759547) could not connect to `api.data.gov.in` from GitHub's runners (`ConnectionError` on
  every try, the part failed as it should), while the same address answers from India.
- **Why left:** the India data portal holds no all-India district table of the Dynamic Ground Water
  Resources assessment as an API resource (searched 2026-11-23): the Ministry of Jal Shakti's
  assessment catalogues there are empty, the National Compilation gives district tables only in PDF
  annexures, and the portal's other district-wise tables are Rajya Sabha answers for single states or
  urban areas (Delhi and Bengaluru by assessment unit).
  The portal refuses connections from GitHub's runners.
- **Clears it:** one `groundwater` extract and load from a network the portal answers (for example a
  self-hosted runner in India, or the portal's allowance for GitHub's addresses); then a district table
  for more states on the portal (each a new dataset row and a table in
  `etl/geo/geo_etl/layers/groundwater.py`), or the owner's choice to load the National Compilation's
  district annexure another way (for example a transcription recorded as its own dataset).

### Ask the map lists every year of the series

- **What:** ask the map lists each district value, so Climate shows 45 years of CHIRPS annual
  means (with their 10th and 90th percentiles) and 45 years of GHCN CAMS means beside the normals
  and trends. The region route no longer does: a place there sends only its facets' headline
  values (`geo/headline.HEADLINE_SERIES`, decision 0153).
- **Why left:** ask the map gives a district's values as stored (contract); folding a series is a
  screen choice.
- **Clears it:** the map screen folds a yearly series into one row with a sparkline (each year a
  dataset value), or a contract change that leaves yearly rows out of its facets.

## Public transcripts and share links (decision 0097)

### The `SIGNED_IN` chunk ACL is read by everyone

- **What:** since decision 0179 a field transcript's speaker-labelled windows are written `PUBLIC`
  with the chunk kind `WINDOW` (`Chunk.kind`, migration `0097_chunk_kinds`), the quote recheck and
  the citation contexts read `PASSAGE` chunks only, a search reads windows only when it names
  `WINDOW` in `KnowledgeQuery.chunk_kinds`, and `SIGNED_IN_CHUNK_ACLS` is gone. The windows
  written before that release still carry `SIGNED_IN`, so `OPEN_CHUNK_ACLS` (what every reader and
  every loader that names no reader reads) still holds `PUBLIC` and `SIGNED_IN`, and the
  migration's insert trigger (`Chunk_kind_window_mark`) marks a `SIGNED_IN` chunk the release
  before writes as a window.
- **Why left:** a label is dropped only after a release that no longer writes it is live
  (`docs/contracts/infra.md`, decision 0151), and the release before decision 0179 still writes
  `SIGNED_IN`.
- **Clears it:** once the release carrying decision 0179 is live, a migration that sets every
  `SIGNED_IN` chunk to `PUBLIC`, drops the trigger and its function, and drops the `SIGNED_IN`
  label from `ChunkAcl`, with `OPEN_CHUNK_ACLS` back to `PUBLIC` alone, `SIGNED_IN_CHUNK_ACL` and
  `CHUNK_ACLS`' third value removed in the same change.

### Kutch Ajrakh's timeline pins and named river are not yet seen, and three why claims describe steps

- **What:** job step 1 (`app.scripts.build_craft_chapters`, nightly from Coverage enrichment) stored
  the curated places' Wikidata points on production on 2026-11-19 (run 44452306889, `pointsKept`
  46; every later run found none missing), so Khavda, Barmer, Sindh and Pethapur have their
  `timeline_map` pins; Ajrakhpur and Dhamadka have no Wikidata item that names them. A region story
  now names its river from the river names datasets and is offered the rivers its statements name
  first (decision 0153), but no capture of Kutch Ajrakh's timeline map or of a Kutch Ajrakh water
  answer's region story has been taken on production. Several curated `whyClaimId`s (C062, C080,
  C088) describe a step rather than explain it.
- **Why left:** a capture needs a browser on production (the production E2E's water question,
  `e2e/production/waterStory.ts`, after the river load of decision 0153); the why claims are dossier
  content a reviewer rewrites (the curation lane, one agent per dossier).
- **Clears it:** the production E2E's capture of the timeline map and the water story after the
  river reload; the three why claims reviewed in the dossier.

### The craft page's film score and its AI media on the monograph

- **What:** AI images and clips now get a page copy, join their craft's chapters as `ai_media` and
  are served at `GET /api/crafts/media/{assetId}` (decision 0154). Left: the page's film score (job
  step 5 and `GET /api/crafts/{slug}/film-score`) is not built, and the monograph document the craft
  page renders for a curated craft does not draw the chapters' `ai_media` part.
- **Why left:** the media-and-film lane of 2026-11-22 built the producer side; the page's film and
  the monograph's picture slots are the craft page's and the monograph's own work.
- **Clears it:** job step 5 with the route, and an AI media slot in the monograph document.

## Track 1, round 1 (decision 0101, 2026-11-19)

### Gate thresholds are first guesses

- **What:** the duplicate gate's 0.8 cosine floor and its neighbour counts (8 compared, 12 for
  novelty) were chosen without data; facts with no embedding are matched only by identical text.
- **Clears it:** tune them on the first month of proposals and record the values in a decision.

### A component card's kicker stays English in non-English answers

- **What:** a component card's title is translated with the answer's sentences (decision 0159), but
  its kicker ("Figure from the <craft> monograph" on the site, the kind's words in the MCP answer
  view) and its link ("Open the figure") are English chrome, not interface words.
- **Why left:** interface words are shown in another language only from a cited source a reader has
  reviewed (decision 0157), none holds these words yet, and the site's block renderers are not given
  the answer's language.
- **Clears it:** an interface word group for the card (kicker and link) with sourced, reviewed
  words, the answer's language passed to `components/answer/blockRenderers.ts`, and the answer view
  reading the same words from the ask result.

## Track 1, round 3 (decision 0106, 2026-11-19)

### Fragments are a bridge

- **What:** 7 of Kutch Ajrakh's 80 components still draw from their fragments (73 are native since
  decision 0164, `monographs/Kutch-Ajrakh/native.json`). The ground figure
  (`kutch-ajrakh/geography/why-here`, decision 0151) is the React page's drawing with the app rules
  that draw it, captured by **Capture screens** with `figure`, because its map
  (`components/map/place-context/GroundFigure`) fills the neighbouring countries and sizes its pins
  only after it is drawn in the browser, so its view's first drawing is not the figure readers see;
  once the stored document carries it, a change to the ground data reaches the page only through a
  new capture. The six page tools' views draw their own markup, behaviour and legacy scope for the
  React shell, so inside the authored shell they would nest a second `div.bx` scope and differ from
  the approved markup the native proof compares element for element. The kit's script still drives
  the native views' behaviour by ids and classes, and a generated page still reuses a borrowed
  component's fragment when it has no spec (every Kutch Ajrakh component has one, so the path
  serves only a future authored monograph).
- **Clears it:** the ground map drawing its neighbours and pins in its first drawing (the map is the
  place builders' `components/map`), then the figure listed in `native.json`; the six tools drawn
  natively once the React shell draws the page (the next entry but one); then the kit's behaviour
  moved into the views and the fragments and the generated pages' fragment reuse retired.

### A plate's crop is a class or a focal box

- **What:** three of Ajrakh's plate specs carry a crop class (`natural-dye-materials-photo` `tall`,
  `banni-grasslands-photo` `r32`, `madder-roots-and-dyed-silk-photo` `r43`), which the kit draws as
  the frame's aspect ratio (3 / 4, 3 / 2, 4 / 3, `.ph.tall`, `.ph.r32`, `.ph.r43`); a generated plate
  carries the layout's focal box, which `SpecPicture.focalPosition` draws as `object-position` only
  and which sets no frame. Two ways to say one thing, and a focal box cannot yet say what a class
  says. It cannot be cleared while the authored shell holds (checked 2026-11-23, monograph shell
  lane): the native proof (`e2e/monograph-native-unit.spec.ts`) needs each native plate to draw the
  approved markup element for element, and the approved page writes `div.ph.tall`, `.ph.r32` and
  `.ph.r43`, so a frame set by a style fails it; and stored document versions are never changed
  (`monograph-document.md`, Versions), so the editions stored before the change keep `crop`.
- **Clears it:** once the shell retires (the next entry), a focal box that also sets its frame's
  aspect ratio (the box's width and height times the picture's), the three crops written as such
  boxes (each picture's own ratio is its class's: 1280 by 1707, 853 and 960, so each box is the
  whole picture) and `crop` dropped from `component_specs_plates` and `PicturePlateView`, proven by
  Monograph parity (`check=all`) and a generated page's capture, since every generated plate with a
  focal box would then be framed by it; the web keeps drawing `crop` for the stored editions that
  carry it unless the owner lets them be stored again.

### Kutch Ajrakh's React page draws the authored shell

- **What:** `MonographDocument.shell` carries the approved page's main markup with its units filled
  and the seven components "Fragments are a bridge" names inlined from their fragments, so the
  React page matches the approved one by construction (decision 0106, the first parity run); 73
  components are native views inside it and the rail takes the content's chapter names (decision
  0164). Besides components the shell holds hand-made markup that `MonographDocumentPage` does not
  draw: the masthead with its tools and counts (44 sources plus 24 for the kin crafts, where the React
  masthead counts every cited source, 64), the answer's table of contents, margin notes with fixed
  entries, the sources chapter's five groups (the React shell draws one numbered list), and each
  chapter's own wrappers (screens, articles, spreads, the chemistry sub-rail, the colour key).
- **Clears it:** the React shell drawing the masthead and its counts (the kin crafts' sources are
  the ones the `kin-craft-sources` component lists), the table of contents, the margin notes, the
  sources chapter through the page's own `source-list` and `kin-craft-sources` components (whose
  specs carry the groups) and each chapter's wrappers, proven by Monograph parity (`check=all`),
  then the shell retired. The wrappers are hand-made per chapter, so this needs either a port of
  the template's main markup into structure the document carries, or the owner's leave to let a
  React drawing become the approved reference, as the ground figure's capture did (decision 0151).

### The authored shell keeps the app's CSS out by name

- **What:** the React page draws the approved markup inside the app, so the app's CSS reached it:
  Tailwind's preflight (heading sizes, sub and sup, button and list resets) and seven class names
  the shell shares with the app (`kv-btn`, `kv-tabs`, `kv-cite`, `kicker`, `panel` and the
  utilities `grid`, `inline`, `ring`). `components/monograph/authoredShell.css` reverts preflight
  in the base layer and gives the colliding names `all: revert` in a layer above the utilities,
  outside native views (`[data-kind]`). A new app class with a name the shell uses would leak
  again; the parity run's drift finder names it.
- **Clears it:** retire the shell (the previous entry: every component a native view, the kit's
  styles in the views), or prefix the kit's classes so no name can collide, which renames classes in
  the approved page's markup and so needs the owner's leave (decision 0100 serves it as built).

### Curated craft documents: what they do not carry yet

- **What:** a generated craft document draws its curated plates, its contributed plates and its
  record (key facts as the fact grid, the record strip), and its page draws the reviewed field
  photographs and quotes after the chapters (`FieldVoicesPart`, decision 0156), but not its kin
  crafts (`relatives`), which `GET /crafts/{slug}/page` still carries in its chapters. AI images and
  videos made from a craft's claims are not carried either.
- **Why left:** a `related_crafts` spec per generated document needs each kin craft's swatch, shared
  materials and cited sentence from stored rows (Kutch Ajrakh's are authored), and a capture of a
  generated page; AI imagery on a page waits on the owner's ruling on principle 9 (see the production
  E2E defects below).
- **Clears it:** a `related_crafts` component in the kin chapter of a generated document, from the
  page's relatives, with its tests and a capture; the owner's ruling for AI media.

## Round 6 (2026-11-20)

### Review cards not yet seen in a browser

- **What:** the review page's STRUCTURE card (a category's proposal and an alternative among them,
  decision 0169), its READINGS card and its LAYERS card are covered by unit specs of their shapes and
  lines only; no one has seen them drawn at the acceptance widths in light and dark.
- **Why left:** the capture needs a Professor's and an Admin's signed-in browser on a release that
  carries these cards and a waiting item of each kind; production holds no reading outside its range
  and no map layer proposal yet.
- **Clears it:** a signed-in capture of `/admin/review` with one item of each kind at 360 and 1440,
  light and dark, against the design system's boards.

### Defects the production E2E suite found in round 6

- **What:** on Kutch Ajrakh, the labels under the equation's species ("leucoindigo, on the fibre")
  overflow their 15ch box (`white-space: nowrap` on `.bx-chem .eq .side` in the kit's
  `monograph.css`), and at 360 the ion charges spill out of the formula; Kutch Ajrakh's document
  carries aria-labels that begin "AI illustration:", which principle 9 (no AI imagery) may not
  allow. The answer essay check waits for one paid `questions=true` run to save an answer. (The
  Textiles hub draws its science from the category's own monograph, served since round 7.)
- **Why left:** the kit is the owner-approved page's stylesheet, so a fix changes the approved page
  at 360 and needs the owner's sight of it beside the parity run; the labels wait on the owner's
  ruling; the paid run is the lead's.
- **Clears it:** a kit fix shown to the owner at 360 and proven by Monograph parity; the owner's
  ruling on the illustrations' labels; the lead's paid run.

## Round 7 (2026-11-20)

### Live research write-backs skipped the candidate gates

- **What:** on production since 2026-11-21 every live-research write-back is `IN_REVIEW` with
  `CandidateCheck` rows (47 claims, 220 checks), so this is left only for the older approved
  write-backs, stored `APPROVED` with no checks before the write-back went through the gates.
- **Why left:** stored facts on production are a person's to review; no lane changes them.
- **Clears it:** a reviewer re-checks them with the filing report
  (`python -m app.scripts.write_back_filing`, whose summary lists the facts with no `CandidateCheck`
  rows, decision 0136) and `python -m app.scripts.write_back_report --gate-less`, then rejects or
  re-files each in the review queue.

### Speed left after the quality lane

- **What:** on a phone (Lighthouse at 360, median of three, 2026-11-22) Kutch Ajrakh scores 78 with
  an LCP of 5.7 s against the 2.5 s target: about 1 MB is requested before its masthead picture
  paints, namely the six first-screen font files the layout preloads (364 KB, Newsreader italic
  143 KB and roman 128 KB among them), the kit stylesheet (78 KB, render-blocking) and about
  400 KB of scripts. Signed out, `/ask` lands on the sign-in page (83, LCP 4.7 s), whose photograph
  shares the first round with Google's sign-in script (104 KB). The Textiles hub scores 100 (LCP
  1.5 s).
- **Why left:** what the entry named is in: Newsreader subset to weights 300 to 600 and its kept
  features (`tools/webfonts`), the arrow on Plex's symbols face, the uncurated page and (decision
  0145) the answer renderers loaded on demand, curated documents split like Ajrakh's shell, and
  `/ask` drawn before its scripts. Before and after this lane Ajrakh measured 78 and 5.7 s on the
  phone (TBT 112 ms to 83 ms, 1.39 MB to 1.35 MB). What is left is a choice of which first-screen
  bytes wait: the first-screen faces are preloaded by choice (round 7, so the first screen never
  swaps its type), and the kit stylesheet is the owner-approved page's.
- **Clears it:** the owner's or lead's choice of the faces to preload and of a kit stylesheet split
  by chapter, then the change proven by Monograph parity and Lighthouse at 360.

### The geo ETL stays on Python 3.14

- **What:** the backend, the tools and the craft ETL run on Python 3.15 (decision 0118), but
  `etl/geo` and `geo-etl.yml` stay on 3.14, because `exactextract` 0.3.0, its newest release, has
  wheels for cp39 to cp314 only.
- **Why left:** building `exactextract` from source needs GEOS and GDAL headers on every runner.
- **Clears it:** when `exactextract` publishes a cp315 wheel, move `etl/geo/pyproject.toml` and
  `geo-etl.yml` together; `backend/tests/test_python_version.py` keeps the two agreeing.

### Leftovers of the design-conformance lane

- **What:** the Sources differ readings open in a `<details>` after their paragraph and the claim
  stores what they differ on (`Claim.differsOn`, decision 0156), but three seams are open. An
  answer sentence never receives it, because `knowledge_view.ClaimView` carries no `differs_on`
  (`section_blocks.explainer_sentence` reads it through `DIFFERS_ON_FIELD`), so answers show a plain
  "Sources differ" summary; a flag the write-back's duplicate judge sets stores no subject, because
  the judge names none; and the matter and what-if hosts
  (`components/answer/matter/ReactionStepList.tsx`, `StepDetail.tsx`,
  `components/answer/play/WhatIfLab.tsx`) draw a flagged sentence's tag without its readings. A
  drawing stored without server variants (the kind fixtures on `/design/kinds`) shows a sunk
  placeholder until it hydrates.
- **Why left:** filling `ClaimView.differs_on` also gives the craft page's sentences their
  `differsOn` (the Kutch Ajrakh page gains three, renumbering its paragraphs), so it lands with the
  refresh of `shared/craft.page.golden.json` and a re-baseline of the approved page's parity, which
  the final clean-up and monograph lanes held while decision 0166 ran; the judges and their callers
  (`write_back_gates`, `fact_proposals`) and the matter hosts were other lanes' files; the
  fixtures are delivered specs, which may not carry `themes` (`component_specs_general_delivery`),
  and the page bundles them instead of asking the server, which adds the variants.
- **Clears it:** `ClaimView.differs_on: str | None` filled from `Claim.differsOn` in `cited_view`,
  with the craft page golden regenerated and the parity re-baselined; the duplicate judge naming
  what two facts differ on and passing it as `candidate_writes.mark_sources_differ(..., about=)`;
  `SentencesDiffer` after the paragraph in the three hosts; serve the kind preview's specs through the backend, which adds the four variants
  with `services/drawing_themes.themed_spec` as it does for a delivered drawing.

### Goldens that do not yet show every field

- **What:** `backend/tests/contracts/unshown_fields.json` still lists the fields of a served payload
  that no golden in `shared/` shows, each waiting on data the repository does not hold
  (`test_golden_fields.py` fails on any other unshown field and on a listed one that is shown, so
  the list only shrinks; decision 0168 left out what the web never parses and showed the DOI, the
  understanding's basis, a translated answer and the craft page's voices and field photos):
  - `GroundwaterValue`: the climate fixtures are Kachchh's, and groundwater is stored only for
    Rajasthan's districts and not loaded yet ("Groundwater values only for Rajasthan, and not yet
    loaded"); no Geo ETL run has recorded a groundwater row (decision 0178 recorded Kachchh's CHIRPS
    monthly normals from run 44204618054 for the seasons fixture).
  - `MeasureRegion`, `ReactionStep.delta_h` and `StepEnergy`: no stored claim states a regional
    factor (decision 0163's kept limit) or a step's ΔH (decision 0152).
  - `ReactionStep.formula_basis` and `formula_sources`: only the craft page's chapters infer
    formulas (`services/chapter_balance`), and the web drops the chapters; an answer's reaction
    player never sets them.
  - `SourceRef.container_title`, `PageSource.container_title` and `NumberedSource.container_title`:
    only live research stores a journal name (a dossier writes its journal into `publisher`), and no
    live-research answer with a paper is recorded here; recording one is a paid answer run, which
    decision 0165 keeps from adding calls while answers are measured.
  - `AnswerSentence.original`: only the category page's lede is a plain answer sentence, and
    category pages are not translated.
- **Why left:** a golden shows recorded or stated data, never a value made up for the test.
- **Waits on:** a Geo ETL run that loads groundwater for a fixture's district; a curated quote
  stating a regional factor or a ΔH; an answer's reaction player that infers a step's formula from a
  stored compound record, or the owner's choice to keep those two fields to the chapters; a recorded
  live-research answer citing a paper with its journal, from a run the lead pays for after the
  measurement; and the owner's decision on translated category pages. Then empty the list.

### The rubric floor waits on a run that shows the quantities table

- **What:** run 45112746194 (release 1ab422fe, 2026-11-23) found decision 0147's table built once
  and dropped, since every row's sentence was a ladder stage sentence already shown. Decision 0168
  shows such a table: the claim ledger keeps those rows with `shownIn`, the view draws them with
  the sentence's citation and without saying it again, and the judge, the rubric and Listen read
  the sentence once. No run has yet measured it, so `rubricMean` in
  `backend/app/data/eval/floors.json` is still the 0.82 decision 0147 set. Decision 0174 made the
  rubric's everyCited part a share of the shown sentences; run 45161982883 scores 0.920 under it
  (0.754 as run), so the next run's mean is measured under the share.
- **Why left:** the floor is re-based on a measured run, and answer-quality is a paid run only the
  lead dispatches.
- **Clears it:** the lead runs answer-quality on the same questions and raises `rubricMean` to the
  run's mean less 0.05, rounded down.

### The answer did not name the oxides behind Khurja's blue and turquoise glazes

- **What:** answer 504968ea-49cc-469c-88f9-205a2ea90e8a was asked what gives Khurja's glazes their
  blue and turquoise colours and named no oxide. An open-source search on 2026-11-23 found none that
  names them for Khurja: the GI record (application 178) lists a statement of case of 2009 and a reply
  of 2013 as PDFs the text fetcher does not reach; the RIPA Khurja leaflet names only cupric oxide for
  the hand-painted designs and is all rights reserved; khurjaceramic.com (a maker's site) says
  "cobalt for blue" without a licence; the cobalt and copper account of blue and turquoise (imp-art.org)
  is about Jaipur blue pottery.
- **Why left:** the colourant must come from a source that names it for Khurja and can be cited, and
  Khurja Pottery's facts are written through the MCP server, not a dossier.
  The planner now searches the colourant oxides when a question asks what gives a glaze its colour
  (decision 0167), so a citable source that names them is found once one is open to the fetcher.
- **Clears it:** a person opens the two statement-of-case PDFs of application 178 at
  search.ipindia.gov.in in a browser, reads the glaze and colour section, and proposes its sentence
  (cobalt, copper, or whatever it names) through `propose_facts` with `supply_source` for the PDF.

### Write-backs filed before decision 0135

- **What:** the 19 facts answer 504968ea-49cc-469c-88f9-205a2ea90e8a wrote stay under Khurja
  Pottery's concept in the review queue, among them the Khorezm, Nigerian, porcelain, kiln-schedule
  and polymer-clay sentences; earlier live-research facts were filed by the old rule too.
- **Why left:** stored facts on production are a person's to review; no lane changes a stored row.
- **Clears it:** a reviewer runs `python -m app.scripts.write_back_filing --answer
  504968ea-49cc-469c-88f9-205a2ea90e8a` (and `--since` for the older ones), which prints where each
  fact is against where today's rule files it (decision 0136), and approves each under the craft it
  names (approve with `craft`), approves it where it is, or rejects it.

## How this document is kept true

| Change | What to do here |
|---|---|
| A shortcut is taken | add its entry, with what is wrong, why it was left and what clears it, in the same change, and clear another entry there so the count does not rise; when none can be cleared, that change's decision record says why and raises `registerEntries` in `tools/hygiene_baseline.json` by hand (the check never raises it) |
| A shortcut is cleared | delete its entry in the change that clears it |
| A limit is kept on purpose | move it to a decision record of limits kept by choice (decisions 0137, 0163) |
| A round ends | the lead re-reads the round's entries, updates "Last reviewed" and lowers the recorded count with `tools/hygiene_check.py --update-baseline` |

An entry is true only while its "What" still describes the code; when a change makes it untrue,
rewrite or delete the entry in that change.
