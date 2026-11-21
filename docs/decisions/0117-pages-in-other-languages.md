# 0117. A page in another language is the same page, translated passage by passage

Every craft, family and category page can be read in the thirteen answer languages as its English
page translated passage by passage, its citations, names, numbers and formulas kept and every
passage not yet translated shown in English. Translations are open work, one `TRANSLATE` task per
page and language, given as a part of the page bundle `preview_page` and `propose_page` already
take, and reviewed by readers of the language under the trust tiers.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "The Hindi and the regional language pages,
the thing with that is that we need to create the seams for that to fit in. That should also go into
open tasks that people can contribute to."). Builds on decisions 0107 (articles in English, room for
translation), 0023 (answers in Indian languages and their verified translation), 0101 (open work)
and 0111 (the MCP tools, at most 22). The contracts are `docs/contracts/monograph-document.md` and
`docs/contracts/open-work.md`, each in Pages in other languages.

| For | Read |
|---|---|
| What it builds on | [0107 Craft articles are written in English, with room for translations](0107-craft-articles-in-english-with-room-for-translation.md): articles in English, room for translation |
| What it builds on | [0023 Answers in Indian languages](0023-multilingual-answers.md): answers in Indian languages and their verified translation |
| What it builds on | [0101 One knowledge architecture for every craft: facts, sections, components, monographs](0101-knowledge-architecture-for-every-craft.md): item 15's open work, which gains the `TRANSLATE` task kind |
| What it builds on | [0111 Twenty-one MCP tools in six groups, with small schemas](0111-fewer-mcp-tools.md): the MCP tools, at most 22, which gain no tool |
| How pages are translated, served and reviewed today | [monograph-document.md](../contracts/monograph-document.md), Pages in other languages |
| The `TRANSLATE` tasks as they stand | [open-work.md](../contracts/open-work.md), Pages in other languages |
| Every decision, by group | [README.md](README.md) |

## Context

Every craft, family and category page is one `MonographDocument` written in English (0107), and a
document already carries its `language`. Answers come in thirteen languages, translated under
checks that keep numbers, units and formulas and the target script (0023). Readers of a Gujarat
craft read Gujarati first, and contributors who read Hindi or Tamil have no way to give what they
know of the language. A translated article written apart from the English would drift from it and
lose its citations, and a page that silently mixes languages misleads its reader.

## Decision

1. **A translation is of a passage, never of an article.** The unit of translation is a text unit
   of the English document (a passage): its string leaves in order are its texts, and a translation
   gives one text for each. Names, botanical names, verbatim quotes and formula parts sit in fixed
   marks and are copied exactly; the masthead title, the craft's name, is never translated
   (principle 8: never transliterate a name ourselves). A passage is identified by the hash of its
   words and the claims it rests on, so renumbering the page's sources holds nothing, and a changed
   sentence holds its translation.
2. **Citations never translate.** The served passage takes every mark, citation and attribute from
   the current English passage and only its texts from the translation. Quotes stay in the popover
   in their source's language.
3. **The gates** are those of answers, applied to a passage: the English is current, one text for
   each, fixed texts unchanged, the citation's words not empty, every number, unit and formula kept
   and none added, the prose in the language's script, no longer than three times the English plus
   40 characters and no new link. No model judges a translation; a reviewer who reads the language
   does.
4. **Review by readers of the language, under the trust tiers.** A Professor or above names the
   languages they read; translations into them wait for them, and their own translations into them
   are approved at once. A proven account's are served at once, a fifth of them drawn for review; a
   newcomer's wait; the review switch decides the rest. No one reviews their own translation.
5. **The page falls back, and says so.** A passage without a current translation is served in
   English with `lang="en"` and the word English before it; the page's language note says how many
   passages read in the language. A language with no translated passage is not offered at all: its
   address redirects to the English page and no `hreflang` names it.
6. **The seam reuses what exists.** No new MCP tool (0111 keeps 22): a translation is a part of the
   page bundle, previewed with `preview_page` (authored pages too) and proposed with `propose_page`,
   and the site posts the same bundle. The URL and languages follow the answer pages': the thirteen
   answer language codes, `/crafts/<slug>/<code>` beside `/crafts/<slug>/v<N>`.
7. **Open work.** One `TRANSLATE` task per page and language: the language of the craft's home state
   first, at the page's priority, then Hindi one step lower (Hindi alone for a family or category).
   The passages of each page's English document are kept in an index written when that document is
   served and its tag changed, so listing open work counts passages without building a document; a
   claimed task lists up to 20 passages with their hashes, and the task closes when none is left.
8. **Owner rule kept**: articles are still written in English (0107). A variant is the English page
   in another language, never a separate article, and answers keep their languages.

## Consequences

- Any number of contributors can translate one page at once, passage by passage, at the cost of a
  hash comparison per passage; serving a variant reads one page's served translations.
- When the English changes, only the changed sentences fall back; a task lists them again and the
  reviewer sees whether a waiting translation's English is still current.
- Figures keep their specs: their own labels (axes, legends) stay English inside a translated page,
  while the text units placed in them translate. The draft (`edit_draft`) does not yet hold
  translation parts; bundles carry them.
- The state-to-language table covers the thirteen answer languages only: Konkani, Meitei, Nepali,
  Mizo and the other languages of the north-east join when answers do.
- The page in Urdu sets right to left per passage; mirroring the whole article region, as the
  board's Urdu answer does, follows when a page is first served in Urdu.
- `/preview/translation` draws Kutch Bandhani with a Hindi draft of its three lede sentences, built
  on the web from the served English page, so the variant's look can be captured before any
  translation is served.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/research/`
(`test_translation_passages.py`, `test_page_translation_gates.py`, `test_page_translation_variant.py`,
`test_translation_regions.py`, `test_document_language_seam.py`), `backend/tests/db/`
(`test_page_translations_db.py`, `test_translation_work_db.py`, `test_translated_documents_db.py`),
`backend/tests/test_page_translations_migration.py` and
`frontend/e2e/document-languages-unit.spec.ts`.
