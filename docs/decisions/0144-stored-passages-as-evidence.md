# 0144. A stored passage is evidence an answer and a voice turn may cite, kept as a fact of its own source

The composer is offered every stored passage its reader may read, in the passage's own words,
beside the stored claims and the documents read; a sentence that cites one is written back as a
fact of that passage's own source with the quote it verified, filed and gated as every write-back
is; a hybrid voice turn asks the stored search for passages, offers them, and speaks a
sentence citing one only once its fact is written; and a one-word alias that is an ordinary English
word, or a word several crafts' names share, no longer files a fact under another craft.

Date: 2026-11-22. Status: accepted (the lead's round 7 debt-clearing brief, stored passages lane:
"Both entries are one seam ... Clear it end to end"). It amends [decision 0010](0010-composer.md)
(the composer's candidates), [decision 0124](0124-live-research-write-back.md) (what a write-back
keeps and who finds it), [decision 0140](0140-voice-and-listen-kept-true.md) (what a voice
turn ranks and speaks) and [decision 0136](0136-write-backs-filed-by-their-source.md), item 1
(what names another catalogued craft; on the lead's direction of 2026-11-22 after the filing report
of answer 504968ea-49cc-469c-88f9-205a2ea90e8a). The contracts are `docs/contracts/research.md` (the composer; The writer
and the coverage job), `docs/contracts/knowledge-writes.md` (The research write-back) and
`docs/contracts/voice.md` (Languages, the turn).

| For | Read |
|---|---|
| The composer whose candidates it widens | [decision 0010](0010-composer.md) |
| The write-back whose evidence and finders it widens | [decision 0124](0124-live-research-write-back.md) |
| The voice turn whose ranking it widens | [decision 0140](0140-voice-and-listen-kept-true.md) |
| Who may read a quote | [decision 0121](0121-quote-visibility.md) |
| The filing every write-back follows, whose naming of another craft it narrows | [decision 0136](0136-write-backs-filed-by-their-source.md) |
| The screen for passages about another craft | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| The composer's candidates and the writer | [research.md](../contracts/research.md), The composer and The writer and the coverage job |
| Stored passages in the write-back | [knowledge-writes.md](../contracts/knowledge-writes.md), The research write-back |
| The voice turn | [voice.md](../contracts/voice.md), Languages |
| Every decision, by group | [README.md](README.md) |

## Context

The stored search returns passages (T2 `ChunkHit`s) beside claims, and it reads only passages of
sources a visible fact already cites, or field interviews (decision 0124). An answer counted them
in its research summary but offered only the field interviews to the composer: a sentence citing
any other passage could not be kept, because the write-back kept read documents and field voices
only and a stream citation names a claim. A voice turn ranked claims and offered no passage at
all. So a passage that states the answer, and is not yet a fact, was never said. Both entries of
the debt register were the same seam.

## Decision

1. **A stored passage is offered in its own words.** `composer/candidates.passage_candidates`
   offers every stored passage of the pack, in search order, as an `EVIDENCE` candidate whose
   text is the passage itself (`stored_passages:<chunk id>`, label `stored passage: <title>,
   <locator or passage n>`, level `PROVISIONAL`); field interviews keep their own label. The
   passage is the verified text: a quoted span is checked against it, and the write-back's quote
   is that span. A passage too short to quote (`quotes.trivial_quote`, under 20 characters once
   folded) is not offered, field or stored, since no sentence could quote it. The alternative,
   offering only the quotes the passage's facts already carry, was refused: they say what is
   already a fact.
2. **It is kept as a fact of its own source.** `services/write_back_stored.stored_documents`
   names each cited passage's `Source` row as the evidence item (its https address, else its DOI
   link; its reliability as the grade; its licence, year and reading date), so the claim writer
   re-finds that row by DOI or address, links the quote to the passage that holds it, and a
   passage's access decides who reads the quote (decision 0121). A source with neither address,
   or no reading date, is not cited (logged), and a sentence resting only on evidence that could
   not be kept is skipped (`SKIP_UNKEPT`). A second citation shape naming a source id directly
   was refused: it would give the write-back contract and the claim writer two ways to name a
   source.
3. **It is filed and gated as every write-back.** A stored passage answered the whole question,
   not one facet, so `write_back_plan` packs it with every facet of the plan: its sentence takes
   the facet of its section's discipline, else the first. The filing ladder of decision 0136 reads
   the sentence, its quote, the passage's paragraph around the quote and the source's title, so a
   passage about another craft files its fact under that craft; the candidate gates, the closed
   fact check and the `RESEARCH` switch apply unchanged (`IN_REVIEW` under `AUTO`).
4. **A reader is offered only what the reader may read.** An answer's stored pack holds `PUBLIC`
   passages only (`OPEN_CHUNK_ACLS`), as an answer can be shared. A voice turn is private to its
   reader, so it asks with the reader's access (`chunk_acls_for(role)`): a `RESEARCHER` passage
   is offered to a researcher and never to a student.
5. **A hybrid voice turn writes a passage back before it speaks it.** It asks the stored search
   for passages, offers at most `PACK_PASSAGES` (3, as a reply speaks at most three sentences)
   beside the ranked claims, screens them as an answer's passages are (`off_question`, no
   comparison), and before speaking writes back the composed sentences through
   `store_live_research` (`voice/passage_store.SqlTurnPassages`). A turn has no plan, so its
   facts are filed under the concept of the first ranked claim that has one (a one-facet plan of
   that concept's type and name), where the question's own words would have made a new concept
   per question. A sentence is spoken citing the fact written for it; a refused, held or failed
   write-back leaves it unsaid. A `VERIFIED` turn reads no passage.
6. **A voice turn is a finder of its own.** `FOUND_BY` gains `VOICE`. A `VOICE` write-back names
   no answer: the turn's `Answer` row is written after it is spoken, and the citation's answer is
   a foreign key; the row lists the fact among its claims. Writing the `Answer` row first and
   updating it after was refused: a turn that then ends unsaid would leave a row with no reply.
   The write-back report and the filing report read `VOICE` facts with the others.
7. **An ordinary word names no other craft.** The filing report of answer
   504968ea-49cc-469c-88f9-205a2ea90e8a (Khurja Pottery) filed three general clay facts under
   Metal Casting ("modern equipment such as clay mixers and pug mills streamline clay
   preparation", "synthetic and polymer clays offer greater consistency, durability, and ease of
   use", and the porcelain-firing sentence): Metal Casting has the one-word alias "casting", and
   their source's passage or title said "slip casting". For filing, a catalogued craft is now named
   only through `write_back_names.filing_index`: by its full name, by a name or alias of two words
   or more once stop words are dropped, by a native-script alias, or by a one-word alias that is
   neither an ordinary English word nor a word three or more master crafts use in their names
   (`COMMON_NAME_USES`, the rule decision 0135 gave a craft's own name words). The ordinary English
   words are SCOWL's size-50 lists, vendored as `data/english_words.scowl.txt` by
   `tools/english_words_build.py` (62,862 words; `docs/DATA_SOURCES.md`). So casting, weaving,
   carving, printing, pottery and embroidery name no other craft, Kalamkari (three crafts' names)
   names none of them, and Bidri, Ajrakh and Bandhani still name theirs. A hand-picked list of
   technique words was refused: it would miss the next alias. The craft resolver is unchanged; the
   off-question screen of decision 0138 reads the same names, so a passage saying "slip casting" is
   offered to a pottery answer.

## Consequences

- More facts are written: an answer's, a coverage job's or a voice turn's sentence citing a
  stored passage becomes an `IN_REVIEW` fact of that passage's source, as a read document's
  does. The quote of a passage of a closed page stays researcher-only.
- A voice turn that cites a passage spends one more embedding call (the gates' vectors) and a
  short database transaction before it speaks.
- A `VOICE` fact's citation names no answer; its voice turn's `Answer` row links the two.
- The voice pack's own claims are read with every access, as before this record; only the
  passages and the facts written for them follow the reader.
- The three Khurja facts now file as general clay facts would: the porcelain sentence to the clay
  family's science, the other two held for a reviewer. Facts already filed under Metal Casting
  stay there until a reviewer re-files them from the filing report.
- No migration and no stored fact changes.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/write_back/test_stored_passages.py`, `test_filing_names.py`,
`backend/tests/voice/test_turn_passages.py`, `tools/tests/test_english_words.py`,
`backend/tests/field_voices/test_citing_rules.py` and `backend/tests/db/test_stored_passages_db.py`.
