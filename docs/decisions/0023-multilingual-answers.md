# 0023. Answers in Indian languages

Answers are written in English and twelve Indian languages: composed and verified in English, then
translated in one `TRANSLATE` call per answer and checked mechanically. Translations are cached per
claim and language, and a question may be asked in any of the languages.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| What built on it | [0107 Craft articles are written in English, with room for translations](0107-craft-articles-in-english-with-room-for-translation.md): answers in Indian languages, which keep their languages |
| What built on it | [0117 A page in another language is the same page, translated passage by passage](0117-pages-in-other-languages.md): answers in Indian languages and their verified translation |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked for answers in Indian languages, not only English, since current models handle
them well. Every check that makes an answer trustworthy was written for English: the verbatim quote
check, the citation rule, the figure check and the quote overlap of decision 0013, whose stop list
and four-letter stems are English. PLAN 6 builds search queries from the craft name and English
facet targets, the reference adapters fetched Wikidata and Commons in English only, stored claims
are ranked by an English full-text query, and PLAN 10.6 limits voice to English and Hindi.
`/answers/config` offered English alone. PLAN 0 asks for accuracy over speed and a citation on every
sentence; the frontend skill asks for local fonts and concise copy.

## Decision

1. **One list of languages.** `research/vocabulary.ANSWER_LANGUAGE_SPECS` holds English, Hindi,
   Bengali, Tamil, Telugu, Marathi, Gujarati, Kannada, Malayalam, Odia, Punjabi, Assamese and Urdu,
   one line each (`AnswerLanguageSpec(label, autonym, script)`), so adding a language is one line.
   The script (ISO 15924) decides the text direction (`RIGHT_TO_LEFT_SCRIPTS`: Arabic, so Urdu is
   right to left) and which Noto Sans face draws it. `/answers/config` lists them as `{code, label,
   autonym, script, direction}`; the ask route accepts exactly these codes.
2. **Verification stays on English.** The composer writes and checks canonical English sentences
   with every existing check unchanged: `ComposeRequest.language` now refuses anything but
   `CANONICAL_LANGUAGE`, with a message naming the translation service, so a caller cannot ask the
   composer for Hindi and have every sentence fail the overlap check. The learner's question still
   reaches the composer as written.
3. **One TRANSLATE call per answer, then a mechanical check.** A non-English answer translates the
   verified sentences, the model-written headings and the follow-ups in one call
   (`composer/translation.ModelTranslator`, routed as `AiTask.TRANSLATE`, which the catalogue already
   had: Gemini 3.8 Flash first, then Claude Sonnet 5.5 and GPT-6.1 Terra, 8,192 output tokens, seeded
   by migration 0007). Each item is checked by `research/translation.translation_problems`:
   - every number of the English text appears in the translation and no new number appears, after
     `quotes.fold_digits` turns Devanagari, Bengali, Gurmukhi, Gujarati, Odia, Tamil, Telugu,
     Kannada, Malayalam, Arabic-Indic and Extended Arabic-Indic digits (and the Arabic decimal and
     thousands separators) into ASCII, and grouping commas are dropped, so `1,20,000` equals
     `120,000`;
   - chemical formulas, mhchem `\ce{}` and `\pu{}` spans and units (°C, °F, %, ‰, pH, and SI-style
     symbols after a number such as g/L, mm, kg, mol) are the same set on both sides, compared after
     Unicode NFKC, the normalisation every quote check already applies (so `H₂O` and `H2O` are the
     same formula; a byte comparison would have refused a translation for a subscript the source
     itself may use);
   - the prose (protected tokens removed) is mostly written in the target script, so an
     untranslated reply is not labelled as Hindi;
   - no link, markup or personal data appears that the English did not have.
   A failing item is sent back once with its problems in an untrusted block; one failing twice is
   shown in English. Citations are copied from the English sentence by the service, never written by
   the model; quotes stay verbatim in their source language in the source dialog.
4. **What is translated where.** Researched answers translate sentences, headings and follow-ups.
   Verified answers translate only the claim sentences: their headings ("Materials and tools") and
   templated follow-ups are the app's own labels and stay English with the rest of the interface, so
   a fully cached Verified answer makes no model call. A translated sentence carries
   `translated: true` and `original` (the English); a translated heading carries `original`;
   `exclude_if` keeps both off the wire otherwise, so every golden file is unchanged. A new `status`
   step `TRANSLATING` says "Translating the answer into Hindi".
5. **Cache per claim and language.** `ClaimTranslation (claimId, language, sourceSha256, text)`,
   unique on claim and language, with RLS and no anon grants (migration 0007). A sentence is
   cacheable only when it cites one claim and its text is exactly that claim's text, which covers
   every Verified sentence and the composed sentences the composer copied word for word. A row is
   used only while `sourceSha256` matches the claim's current text, so an edited claim is
   re-translated rather than served stale.
6. **Questions in any of these languages.** The plan call receives the question as written and
   returns, besides English queries, up to `ModePolicy.max_native_queries` (Hybrid 2, Deep 3,
   Verified 0) queries in the answer language for its Wikipedia and Wikidata, the craft's name in
   that script (`nativeCraftName`, which anchors those queries the way the English name anchors the
   others), and `englishQuestion`. Native queries are `T3` queries with `SearchQuery.language` set,
   counted apart from the English limit, and run only on `NATIVE_QUERY_SEARCHERS` (Wikipedia,
   Wikidata); the language must have a Wikipedia (`WIKIPEDIA_LANGUAGES`). Stored claims are searched
   with an English rendering: the question itself when it is written in Latin script
   (`answer_translation.needs_english_rendering`, over `data/craft_text.script_of`), else the plan's
   `englishQuestion` in Hybrid and Deep, and one TRANSLATE call into English in Verified, which keeps
   zero model calls for English questions.
7. **The language travels in the item id, not a new `fetch` argument.** Wikidata and Commons items
   found in a language other than English carry it, as Wikipedia ids already do:
   `wikidata:hi:Q267813`, `wikimedia_commons:hi:60897367`; English ids keep their old form, so stored
   sources and fixtures are unchanged. `fetch` reads the language from the id
   (`mediawiki.language_and_native`) and renders labels, descriptions and SPARQL statement labels in
   it. Changing `SourceAdapter.fetch` would have touched every adapter and made the reader guess, per
   item, which query's language found it; the item already knows.
8. **Voice.** `services/answer_translation.translated_sentences(sentences, language=, translation=,
   claim_texts=)` turns verified English `AnswerSentence` payloads into the session language through
   the same translator, check and cache, and `answer_store.build_answer_translation(sessions,
   model=)` builds the collaborator. The voice turn composes English and calls it; the voice lane
   keeps its own `VOICE_TURN_LANGUAGES` gate until it does.
9. **The client.** A language picker on Ask (`components/ask/LanguagePicker.tsx`, the
   `SearchableSelect` the frontend skill requires for a choice), defaulting to Auto, which follows
   the question's script (`lib/answerLanguages.detectedLanguage`; Bengali script with ৰ or ৱ reads
   as Assamese, Devanagari as Hindi). The choice is remembered in `kalavigyan_preferences` as
   `answerLanguage` and synced through `PUT /preferences/me` (a `UserPreference.answerLanguage`
   column, `auto` by default), because the theme provider already writes the whole preferences
   object to the server and would otherwise lose it or be refused. Sentences, headings and
   paragraphs carry `lang` and `dir` (`rtl` for Urdu), an English fallback sentence inside a
   translated paragraph keeps `lang="en" dir="ltr"`, and a two-way segmented control (the language's
   own name, English) shows the English original. Ten Noto Sans variable faces (SIL Open Font
   License 1.1, the script subsets Google Fonts serves, about 1 MB together), one per script, are
   local files in `frontend/fonts/` loaded by `next/font/local` (`app/scriptFonts.ts`) with their
   script's `unicode-range` and no preload, after
   Inter in every font stack, so a page downloads a face only when it draws that script. UI strings
   stay English; the per-sentence "Translated" tag is gone, since the control says it once.

## Consequences

- A native-language passage can be cited only beside an English passage that carries the
  sentence's wording: the overlap check is unchanged, so an English sentence resting on a Hindi
  quote alone is dropped. Native sources add corroboration and verbatim quotes in their language.
  Recorded in `docs/TECH_DEBT.md`.
- Translations are checked for figures, formulas, units, script and links, not for meaning. Number
  words, and a unit spelt out in the target language, fail the check and fall back to English.
- A Hindi Hybrid answer costs one plan call, one or two compose calls and one or two translate
  calls; a Hindi Verified answer at most two translate calls (question, then uncached claims) and
  none once its claims are cached.
- The not-enough-evidence message, errors and status lines stay English.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
