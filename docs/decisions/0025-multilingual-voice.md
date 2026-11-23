# 0025. Voice in every answer language

Voice speaks every answer language its speech models support: one derivation lists them, each turn
is ranked and composed through English and translated under the call's deadline, and every fixed
phrase exists in every offered language. A sentence whose translation fails twice is left out.

Date: 2026-11-16. Status: accepted. Supersedes item 12 of decision 0017.

| For | Read |
|---|---|
| What it supersedes in part | [0017 Voice backend: sessions, the custom LLM, the relay path and upkeep](0017-voice-backend.md): item 12, the languages voice offers |
| What amended it | [0157 A translation is read back before it is shown, and every fixed word in another language is sourced, reviewed data](0157-translations-read-back-and-reviewed-interface-words.md): item 5, the fixed phrases kept as reviewed data |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked for voice in the same languages as text answers, not only English. Decision 0023
writes answers in English, Hindi, Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam,
Odia, Punjabi, Assamese and Urdu: composed and checked in English, then translated by
`services/answer_translation` with a mechanical check (numbers in any script, formulas, units,
script) and a per-claim cache. Voice offered English only (`VOICE_TURN_LANGUAGES`), because the voice
turn ranked English claims with the heard words and composed in the session language. The client
hard-coded `en` and `hi`. Speech goes through ElevenLabs: `scribe_v3` for speech to text and
`eleven_v4_turbo` for speech (decision 0017). PLAN 10.3 caps a spoken reply at 60 words and streams
a filler after 700 ms. The owner rules bind: no comments, no provider call with a real key, the
provision script is not run, concise copy, hide what cannot work.

## Evidence

Read on the ElevenLabs documentation on 2026-11-16:

- Speech to text, `elevenlabs.io/docs/overview/capabilities/speech-to-text#supported-languages`:
  the list "applies to Scribe v3 and Scribe v2" and names each language with a three-letter code; its
  accuracy bands are measured on Scribe v2. `api-reference/speech-to-text/convert`: `language_code`
  is "an ISO-639-1 or ISO-639-3 language_code"; null means the language is detected.
- Speech, `elevenlabs.io/docs/overview/models`: Eleven v4 and v4 Turbo share one list of 90+
  languages with two-letter codes, and "the `language_code` parameter accepts ISO 639-1 two-letter
  codes for most languages". v4 Turbo is the page's model for real-time agents (median about 100 ms).
  `api-reference/text-to-speech/stream`: `language_code` (ISO 639-1) enforces the language and its
  text normalisation; a model that does not support the code ignores it.

| Language | Scribe v3 code | Scribe v2 accuracy band | `eleven_v4_turbo` code |
|---|---|---|---|
| English | `eng` | excellent (≤ 5% WER) | `en` |
| Hindi | `hin` | high (5-10%) | `hi` |
| Bengali | `ben` | high (5-10%) | `bn` |
| Tamil | `tam` | high (5-10%) | `ta` |
| Telugu | `tel` | high (5-10%) | `te` |
| Marathi | `mar` | high (5-10%) | `mr` |
| Gujarati | `guj` | high (5-10%) | `gu` |
| Kannada | `kan` | excellent (≤ 5%) | `kn` |
| Malayalam | `mal` | excellent (≤ 5%) | `ml` |
| Odia | `ori` | high (5-10%) | `or` |
| Punjabi | `pan` | good (10-20%) | `pa` |
| Assamese | `asm` | good (10-20%) | `as` |
| Urdu | `urd` | moderate (25-50%) | `ur` |

Every answer language is on both lists, so all thirteen are offered. The configured speech model
lacks none of them, so no language needs another model.

## Decision

1. **Support tables beside the model ids.** `providers/elevenlabs.py` holds `STT_LANGUAGE_CODES`
   (each checked answer language to the code the Scribe list gives) and `TTS_LANGUAGES` (the
   two-letter codes the v4 Turbo list gives), next to `STT_MODEL` and `TTS_MODEL`. Speech to text
   sends the Scribe code as `language_code`; speech sends `language_code` with the session language,
   which v4 Turbo accepts. Either call refuses a language its table lacks before any request, so a
   model change cannot quietly speak a language nobody checked.
2. **One derivation.** `voice/languages.VOICE_LANGUAGES` is the answer languages, in their order,
   that both tables carry (`heard_and_spoken`). Sessions refuse any other language, the agent lists
   them, and `/answers/config` sends them in `voice.languages` as full options (`code, label,
   autonym, script, direction`) built by `research/vocabulary.language_option`, the builder the
   answer languages now share. The contract's `VoiceLanguage` is any answer language; `VOICE_LANGUAGES`,
   `VOICE_LANGUAGE_LABELS` and `offered_voice_languages` leave `schemas/voice.py`, and
   `VOICE_TURN_LANGUAGES` leaves `voice/sessions.py`.
3. **The turn.** The heard text is cleaned as before (`voice/privacy.heard_text`). The craft is
   resolved from it as the text pipeline does. The pack is ranked with
   `answer_translation.english_question` (one `TRANSLATE` call only when the text is not in Latin
   script). The reply is composed and checked in English exactly as before (`ComposeRequest.language`
   is the canonical English; the composer still gets the question as heard). Then an English pass of
   `spoken_reply` picks what fits 60 English words, `translated_sentences` translates those
   sentences with the cited claims' texts, so a claim sentence is served from `ClaimTranslation`
   while its text is unchanged, and `spoken_reply` runs again in the session language: the 60-word
   cap counts the words actually spoken. Source labels stay names ("GI Journal 188", "Shah 2019");
   only the word before them (`SOURCE_WORDS`) is in the session language. A translated sentence
   carries `translated` and `original`, as in text answers, in the transcript, the stream and the
   `Answer` row.
4. **A sentence whose translation fails twice is left out**, and the next sentence may take its
   place within the cap. A text answer shows such a sentence in English, marked `lang="en"`, where
   the reader sees the switch and can open the English original. Speech cannot: one speech request
   carries one `language_code`, which also drives text normalisation, so an English sentence inside a
   Tamil reply would be read with Tamil normalisation. A learner who chose Tamil may not follow
   English, and the transcript must say exactly what was spoken (`VoiceTurnView`), so the sentence
   cannot be shown either. When nothing translates (the translator fails, every sentence is refused
   twice, or the call's time runs out), the turn says `UNSAID_REPLIES` in the session language
   ("I could not prepare that answer just now. Please ask again.") and saves no `Answer`, rather than
   claiming nothing was found.
5. **Fixed phrases.** `voice/phrases.py` holds every fixed spoken phrase for every offered language:
   the filler (ending `... `), no evidence, no craft, the unsaid reply, the two `end_call` messages
   and the source word. A test fails when a table misses an offered language or a phrase is not
   written in its language's script.
6. **Time and seconds.** `TurnAsk.seconds_left` is the time to the call's hard end
   (`SessionRecord.hard_end`) when the turn began; both translations run under that deadline. A
   question rendering that runs out ranks with the heard text; a reply translation that runs out
   says the unsaid reply. Seconds are unchanged: a relay turn bills heard and reply audio only, and
   an agent turn bills wall-clock time between turns, so translation adds no ledger rows and is paid
   for as call time, as composing is. A turn makes at most one `TRANSLATE` call for the question and
   one for the reply (plus one resend of the refused items), and none for cached claims.
7. **Where the filler fires.** The 700 ms timer starts with the custom-LLM stream, after the bearer
   and binding checks, and covers the whole turn: begin, reservation, craft, pack, English rendering,
   ranking, compose, translation, cap and save. A test with fakes holds a Hindi `VERIFIED` turn's
   reply translation open and shows the Hindi filler streaming while that `TRANSLATE` call is in
   flight, then the first real sentence in Hindi. Counting model calls before the first real
   sentence: English `VERIFIED` none, English `HYBRID` one, another language `VERIFIED` one (cached)
   or two, another language `HYBRID` two (cached) or three; so in every non-English turn the filler is expected
   during the first model call. The relay path streams `status` instead of a filler. The stored
   `latencyMs` includes translation, so the gate measures the first real sentence the learner hears.
8. **The agent path, still behind `RELAY`.** `voice/agent.agent_body` lists every offered language
   but English (the agent's own language) under `conversation_config.language_presets`, each
   `{"overrides": {"tts": {"model_id": "eleven_v4_turbo"}}}`, the shape `LanguagePreset` has on
   `api-reference/agents/create`; `provision_voice_agent.py` prints the languages it provisioned. It
   was not run.
9. **The client.** `lib/voiceContract.ts` has no language list: `voice.languages` is parsed with the
   answer languages' own shape. The dock reads the Ask preference (`kalavigyan_preferences.
   answerLanguage`) through `useThemePreferences`, and `voiceLanguage` resolves it with Ask's own
   `resolvedLanguage` over the voice languages: a chosen language, or Auto by the script of the Ask
   box's text (English on the craft page). While no call runs (consent, ended, failed) and more than
   one language is offered, the dock header carries the same `LanguagePicker` (moved to
   `components/`, now used by two areas, labelled "Voice language"); choosing writes the shared
   preference, so Ask follows. During a call it is hidden, since a session's language is fixed. The
   transcript gives heard text, sentences and the muted reply `lang` and `dir` (`attributesForText`,
   `SectionBlock` with the session language), so Urdu runs right to left; the script faces are the
   ones already in every font stack.

## Unverified

1. Scribe v3's accuracy per language: the bands above are Scribe v2's. Urdu's band is moderate.
2. That Scribe accepts the three-letter codes sent and v4 Turbo the two-letter ones for all thirteen;
   both are read from the documentation, not from a call.
3. That the relay voice (`AppSetting` `voice.voice_id`) sounds natural in each language.
4. The fixed phrases in twelve languages were written by this lane and not read by a native speaker.
5. The agent: how a session's language reaches it (the token takes no language, client overrides
   are off, `language_detection` switches by speech), whether `scribe_realtime` hears each language,
   and whether a preset with only a speech model override is accepted. The agents language page
   (`eleven-agents/customization/language`) refused the fetch; its markdown twin says the "All"
   option covers 31 languages and that additional languages switch to "the v2.5 Multilingual model",
   which may predate v4.
6. Real latency: where the filler fires on production models (the spike's time to first sentence).

## Consequences

- Voice is offered in thirteen languages as soon as voice itself is configured.
- A non-English turn costs one or two `TRANSLATE` calls more than an English one, fewer as claim
  translations are cached.
- Debt: Urdu speech-to-text accuracy, native review of the phrase tables, the agent's language
  binding (`docs/TECH_DEBT.md`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
