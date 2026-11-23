# 0080. An answer renders each claim once: the claim ledger

An answer renders each claim once: one ledger per answer, applied where blocks are sent, drops
repeats and rebuilds the finished answer once in reading order. Sources count as works rather than
records, expert seats earn their place, and covered sections are not drawn.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| The ledger hears only of blocks the stream can send, and a section's pictures meet its final blocks | [decision 0182](0182-pictures-of-shown-claims-a-hit-area-on-the-page-and-our-own-frames.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The answers audit of 18 Nov (E2E run 44260797709) found the Expert Indigo answer repeating 45 of
its 117 sentences word for word. Two material cards described one compound (both C16H10N2O2), in
two sections; the 3D molecule and the shared-science graph were drawn twice; cards replayed the
prose above them; four expert seats mostly restated the prose; the same two photographs recurred
in nearly every section beside shop listings and an Instagram post; and Sources listed GI Journal
No. 188 and Frater's essay twice each. The causes were local: every builder, every section and
every picture search decided alone, and nothing remembered what the answer had already shown.
Build plan task 3-01 asks for an answer-wide ledger.

## Decision

1. **One ledger per answer, applied where blocks are sent.** `services/claim_ledger.ClaimLedger`
   lives on the `ExplainerStream`. Sections run in parallel, so the stream is the one place that
   sees every block in the order the reader does. `ExplainerStream.blocks` returns what it let
   through and every caller keeps only that, so the stored document starts as the page.
2. **The finished answer is rebuilt once in reading order.** `explainer_document` passes the
   document through a fresh ledger (`ledgered_explainer`), which also folds in the metadata of
   sources the stream had already merged away. Stored answers are not rebuilt when read: reading
   must return what was stored (explainer versions and saved answers compare them), and answers
   kept before this change stay as they were.
3. **Two kinds of repeat.** A restating block (prose, card facts, expert takes) drops a sentence
   whose text is already shown or whose every claim an earlier block showed. Every other kind that
   carries sentences is a story block (the process ladder's stages, region story, supply map,
   zoom, timeline, concept graph, seasons, measure, compare, what-if, market and climate facts and
   the rest, walked through each model's own `SENTENCES`). A story block is built around its
   claims, so it drops an item only for repeated text, and in one call it is admitted before the
   restating blocks, so a card yields its sentence to the concept graph rather than breaking the
   graph. An item left with no sentence goes (a ladder stage, a practice note, a concept node), a
   ladder stage that keeps some sentences takes the level of what it keeps, a compare cell whose
   sentence was shown is left blank and a row left with fewer than two crafts goes, and a block
   whose own sentence (not an item's) was shown is left out. Two seats' "experts differ" pair goes
   from both seats when either view was already shown. Repeats within a prose block are judged by
   text only, because a composer may split one claim over two sentences.
4. **No "see above" link yet.** A link back to where a claim first appeared needs the ledger to
   record that place (it keeps only sets of shown texts, claims, materials, molecules, terms and
   pictures today) and a sentence field the client reads, so a repeat is dropped rather than
   referred back to. Dropping a sentence inside a paragraph can leave a pronoun with nothing before
   it ("This fermentation matters because..."). Both are left to the answer-presentation task.
5. **Once per answer.** One material card per material, keyed by CID, compound, material, term
   and name, after the card builder has already merged materials sharing a CID
   (`material_cards.merged_materials`, found in the prose by any merged row's name) and stopped
   offering claims its section's prose cites; one molecule per CID; one concept-graph node per
   term; one region story.
6. **Expert seats earn their place.** The panel is not asked when its section already cites every
   candidate, unseen claims are offered first, and a seat whose take adds no new claim is not
   shown, by the builder within its section and by the ledger across the answer.
7. **Pictures.** One per section, chosen for a claim the section shows, never one the answer has
   already shown (a zoom level whose picture was shown, or comes from a blocked site, is left
   out), never from a shop, marketplace or social site. The blocked sites are a maintained list
   (`services/picture_sites.BLOCKED_PICTURE_SITES`, the large Indian craft and fashion retailers
   included) plus shop path segments, a store's `/collections/<name>` listing and "Buy" or "Shop"
   titles; the section picture search applies it before choosing. A section's pictures, fresh or
   reused, are searched from the blocks the ledger let through, so the picture illustrates what
   that section actually says.
8. **Sources are works, not records.** `services/source_merge.SourceMerge` merges by DOI, address
   or title words (at least five, asides left out, never across two DOIs, and by title alone never
   across two stated years); the first cited keeps its id and the year is the earliest stated. The
   title key is the set of words, not their order, because the two GI Journal No. 188 records in
   production name the same words in a different order.
9. **The ledger sees blocks as a live section sends them.** A live section sends its ladder, its
   prose and its pictures alone and its built blocks together; reused sections and the rebuild
   use the same calls (`claim_ledger.admission_batches`), so the page and the stored answer agree.
   Blocks are translated after the ledger admits them, and together
   (`ExplainerStream.blocks(..., in_language=...)`), so a dropped block is never translated.
10. **Covered sections are not drawn.** A section emptied by the ledger ends `EMPTY` with
    "Already covered in this answer." and the client leaves it out (`lib/explainerView.shownSections`),
    rather than drawing an empty card.

## Consequences

- The recorded Indigo answer's 77 rendered sentences with 29 repeats become 34 with none, one
  Indigo card, one Indigo molecule, three concept nodes, two expert seats, one picture and no shop
  domain (`tests/ledger`). The research golden stream now carries one picture.
- Region story steps still repeat the prose of their own section by claim; making the story replace
  that prose needs the geography section to hold its prose until the story is built, which is
  presentation work for a later task.
- A caption saying what to look at in a picture needs a contract field and a renderer, also later.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
