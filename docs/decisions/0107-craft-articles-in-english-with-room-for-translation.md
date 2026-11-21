# 0107. Craft articles are written in English, with room for translations

Craft, family and category articles are written in English only for now, with room in the document
for translations later. Answers keep their thirteen languages.

Date: 2026-11-20. Status: accepted (owner: "every craft needs to maintain the entire article only in
english for now, we can add the scope for adding translation for a craft too"). Builds on decisions
0106 (one monograph template) and 0023 (answers in Indian languages).

| For | Read |
|---|---|
| What it builds on | [0106 One monograph template for every page, reached through fragments](0106-one-monograph-template-for-every-page.md): one monograph template |
| What it builds on | [0023 Answers in Indian languages](0023-multilingual-answers.md): answers in Indian languages, which keep their languages |
| What built on it | [0117 A page in another language is the same page, translated passage by passage](0117-pages-in-other-languages.md): articles in English, room for translation |
| Every decision, by group | [README.md](README.md) |

## Context

Every craft, family and category page is now one `MonographDocument`, stored for authored pages
and generated from published sections for the rest (decision 0106). Answers are already written in
thirteen languages with verified translation (decision 0023), so the question was whether a page
follows the reader's language too.

## Decision

1. **One language for articles: English.** Every stored and generated document is written in
   English. Craft pages offer no language picker and carry `lang="en"`.
2. **Room for translation.** A document carries its `language` (`en` today) and stored documents
   are keyed by subject, slug, language and version, so a translated document can be stored later
   beside the English one without a schema change. The monograph routes take an optional `lang`
   and answer every request with the English document and `Content-Language: en` until a
   translation exists.
3. **Answers keep their languages.** Decision 0023 is unchanged: a question asked in Hindi is
   answered in Hindi, and its citations open the same English sources.

## Consequences

- Translating an article later is a new lane: a translated document per language, built from the
  English units with the verified-translation path of decision 0023, reviewed before it is served,
  and a language choice on the page.
- Native names in their own scripts stay as they are: they are names, not translations.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-20; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
