# 0157. A translation is read back before it is shown, and every fixed word in another language is sourced, reviewed data

An answer's translation is read back into English through the same `TRANSLATE` route and refused
when its reading no longer says what the English says. The fixed words of the answer screen, the
stream and the voice in each answer language are kept as data with their source and their review,
and a word reaches a reader only once a reader of that language has reviewed it.

Date: 2026-11-23. Status: accepted (the lead's round 7 brief, languages lane). It amends
[decision 0023](0023-multilingual-answers.md), items 3 and 4 and its consequences, and
[decision 0025](0025-multilingual-voice.md), item 5. The contracts are
`docs/contracts/research.md` (Translation), `docs/contracts/frontend.md` (`/answers/config`) and
`docs/contracts/voice.md` (the turn's fixed phrases).

| For | Read |
|---|---|
| The translation and its figure check it amends | [decision 0023](0023-multilingual-answers.md), items 3 and 4 |
| The voice phrases it amends | [decision 0025](0025-multilingual-voice.md), item 5 |
| The stance markers the checks share | [decision 0120](0120-grounded-sentences.md) |
| The board and the monograph its first words come from | [decision 0092](0092-design-system.md), [decision 0145](0145-monograph-pages-and-speed-without-debt.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Five entries of the debt register were the languages lane's on 2026-11-22. A translation was
checked for its figures, formulas, units, script and stance, never for what it says. A Verified
answer's headings and follow-ups, and every status line, stayed English in every language. Voice
in other languages was checked by text alone: its phrase table was written by the voice lane and
read by no native speaker. No browser had drawn a right-to-left answer. The Urdu board shows five
of the essay's interface words in Urdu where the app shows English. The owner's rules: no machine
text shown unreviewed, no invented words, nothing run on the laptop, the native-speaker parts are
the reviewers'.

## Decision

1. **Read back, then compare.** `answer_store.build_answer_translation` wraps the
   `ModelTranslator` in `composer/translation_meaning.ReadBackTranslator`. After the mechanical
   check, every translation into a language other than English is sent once more through the same
   `TRANSLATE` model with `READ_BACK_SYSTEM_PROMPT`, which asks for the most literal English and is
   never shown the original. `research/translation_meaning.meaning_problems(english, reading)`
   holds the reading to the English: `translation_problems` on the pair (no figure, formula, unit
   or pH lost or added, the reading in Latin script, the negation and the hedge kept), no negation
   or hedge the English lacks, and, for an English text of three content stems or more, at least
   half of its stems back (`READ_BACK_TERMS_KEPT_MIN`, the quote overlap floor
   `QUOTE_OVERLAP_MIN`). A translation whose reading fails, or that has no reading, keeps its
   English, as a failed figure check always has; renderings into English (a question for search)
   are not read back. A model judge comparing the two was the alternative: it needs a calibration
   of its own and its verdict cannot be checked again, where the comparison is reproducible and
   errs towards English.
2. **The cache is keyed to the checks.** `ClaimTranslation.sourceSha256` is the SHA-256 of
   `TRANSLATION_CHECKS_EDITION` (`read-back-1`) and the claim's text
   (`translation_cache.checked_source_sha256`), so a row made under the figure check alone no
   longer matches and is made again, read back, the first time it is asked for. A migration that
   empties the cache was the alternative; it would drop rows nobody may ask for again and needs no
   less code.
3. **Fixed words are data, by the English they translate.** `backend/app/data/interface_words/`
   holds one file per answer language other than English (`data/interface_words.py`, schema 1).
   Each entry gives `key` (where it shows: `essay.provenance`, `essay.actions`, `stream.status`,
   `stream.heading`, `stream.followUp`, `voice.*`), `english` (the exact English the code shows,
   with its `{placeholders}`), `text`, `source`, an optional `note` and `review` (`{by, on}` or
   `null`). The English keeps its one home in the code that shows it. A word is shown only while
   its entry is reviewed and its `english` is the code's English now, so a changed English stops
   its translation at once. A group (the provenance rail, the actions row) is shown in a language
   only when every word of it is; else the whole group stays English, never mixed.
4. **Where reviewed words go.** `/answers/config` and `/answers/languages` give each language its
   reviewed `essay.*` words as `words: [{key, english, text}]`, absent when it has none, and
   `lib/answerLanguages` accepts them; `lib/interfaceWords.wordedIn` draws the rail and the
   actions in them with `lang`, `dir`, `data-script` and the `ui` face, only while the essay is
   shown translated. The stream reads `ExplainerStream.words`: the status lines
   (`services/status_lines`, the language named by its own name), and in a stored answer the
   section headings (`stored_explainer.shown_stored_heading`, the English kept as `original`)
   and the templated follow-ups. A researched answer keeps translating its headings and
   follow-ups through the checked, read-back `TRANSLATE` call (decision 0023, item 3).
5. **The review path is a reviewed change to the file.** A reader of the language reads each
   entry (the English, the text, the source and the note), corrects the text where it is wrong,
   and records `"review": {"by": "<their name>", "on": "<YYYY-MM-DD>"}` on each entry they
   approve; the change lands as a pull request the owner approves, and the checks hold every file
   to its shape, its placeholders and its script. The translation review queue of decision 0117
   was the alternative: it reviews page passages keyed to a page's text units and would need a
   page kind and a migration for a few dozen words that change with the code that shows them.
6. **The first words are sourced and unreviewed.** The Hindi and Urdu essay words come from the
   Kutch Ajrakh monograph's answer panels and the Urdu answer on the design board. Both were
   approved by the owner, yet they disagree (“44 ذرائع سے” beside “7 ماخذوں سے”; answered beside
   compiled), so approving a design is not reviewing its words: every entry waits for its reader,
   with the other reading in its note. “Saved”, “Saving”, “Removing” and one source have no source,
   so the actions row and the rail stay English until a reader supplies them.
7. **Voice reads its phrases from the same files.** `voice/phrases.py` keeps the English and reads
   each language's phrase from its file, reviewed or not: a call cannot switch to English mid-call
   (decision 0025, item 4), so the phrases are spoken before review, and a reader's review of the
   `voice.*` entries is the native sign-off. Voice offers only a language whose every phrase is
   written (`phrases.phrased_languages`). What a test can check is checked: every phrase says no
   in every offered language exactly where its English does (so the stance markers learn Odia's
   fused ନାହିଁ, Telugu's negative verbs in -లేను and -లేకపోయాను and Assamese নগ'ল and নহ'ল, and
   stop reading Bengali আপনি and তিনি, whose ending is the negative's, as a negation;
   `research/stance_marker_words`), and a relay turn in every offered language sends Scribe its
   code, speech its code and speaks the source word of that language.
8. **An Urdu answer runs in production.** The production E2E asks a fifth known-answer question,
   the mordant in Urdu, and holds it, live at 1440 and in its saved explainer at 834 and 390 in
   light and dark, to at least one translated sentence, an article that reads right to left in
   Urdu, every Urdu paragraph set in Noto Nastaliq Urdu and that face loaded
   (`e2e/production/languageChecks.ts`), besides every screen's audit for sideways scroll and
   overflowing text.

## Consequences

- A translated block costs one more `TRANSLATE` call, and a voice turn's reply translation one
  more within the call's deadline; a cached claim costs none.
- Translations cached before this change are made again when next used.
- No new word shows on any screen until a reader records a review; the debt register keeps the
  readers' parts.
- The not-enough-evidence message and the errors stay English: they are composed sentences that
  carry what was searched.
- The production questions run, with the materials and history questions of the same round, takes up
  to 92 minutes, and its job up to 110.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/research/test_translation_meaning.py`,
`backend/tests/composer/test_translation_meaning.py`,
`backend/tests/db/test_translation_cache_db.py`, `backend/tests/test_interface_words_data.py`,
`backend/tests/answering/test_interface_words.py`, `backend/tests/voice/test_phrase_checks.py`,
`backend/tests/voice/test_relay_languages.py`, `frontend/e2e/interface-words-unit.spec.ts` and
`frontend/e2e/production-languages-unit.spec.ts`.
