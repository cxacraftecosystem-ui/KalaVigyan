# 0158. A curated craft's monograph lists the facts contributors add under their own fields, and a fact a figure shows is not listed again

A curated craft's monograph document lists each fact its dossier does not hold, and that no
curated sentence or figure cites, under the fact's own field in the chapter that field belongs to,
as decision 0149 lists a generated page's unwritten facts; a fact a curated figure already shows is
never listed; and the web draws every list of a document as one cited list in the design system.

Date: 2026-11-23. Status: accepted (the lead's round 7 brief, curated-contributed-facts lane, on the
owner's report of 2026-11-23: the sixteen Sanganeri Hand Block Printing facts contributed through
Claude were served in `page.claims` and drawn in no chapter). It amends
[decision 0149](0149-a-fact-readers-can-see.md), item 5. The contracts are
`docs/contracts/monograph-document.md` (Facts no section cites; A curated craft's structure),
`docs/contracts/monograph-renderer.md` (The page) and `docs/contracts/craft-page.md` (Chapters).

| For | Read |
|---|---|
| The rule for a field's unwritten facts it extends to curated crafts | [decision 0149](0149-a-fact-readers-can-see.md), item 5 |
| Why a curated craft is drawn from its document | [decision 0106](0106-one-monograph-template-for-every-page.md) |
| Why the old web refuses a new part kind while the backend ships first | [decision 0151](0151-a-release-the-live-side-can-read.md), items 1 and 3 |
| The list as it stands | [monograph-document.md](../contracts/monograph-document.md), Facts no section cites |
| How the web draws it | [monograph-renderer.md](../contracts/monograph-renderer.md), The page |
| Every decision, by group | [README.md](README.md) |

## Context

The owner added sixteen facts to Sanganeri Hand Block Printing over the MCP server in Health,
Climate, Physics, Botany and Geology. After decision 0149 the craft page route served them to a
signed-out reader in `page.claims`, and no chapter of that payload cited them, because a curated
page's chapters draw the dossier's own sentences and structure. The served HTML held none of them.

The page readers see is not that payload but the craft's monograph document, which takes the
craft page as its structure (`document_components_store.subject_structure`). Read publicly on
2026-11-23 (release 92482abf), Sanganeri's document did carry the sixteen, in the wrong places:

- `with_page_claims` wrote every page claim that no section or structure showed into the prose of
  the discipline its concept gives (`craft_page._claim`), not its field. A fact about the craft's
  tradition reads OVERVIEW, so the 2007 Ames test, a Health fact, ran as a paragraph of "What it is"
  in At a glance between curated sentences and leftover seed claims; the rest ran in the prose of
  The chemistry, the materials and Geography and water.
- Two Climate facts were listed under Climate and also drawn by the seasons figure: the list left
  out what the structure's text items cite (`structure_claim_ids`) but not what its figures cite.
- The served HTML holds only the opening chapter; the rest is read after first paint
  (`DeferredShellSlot`), so a search of the HTML found none of them.
- The web drew a run of `li` units as a bare `ul.kv-list`, which the approved kit leaves
  unstyled (`.bx-pt ul` has no margin or padding, `li` no marker, and no rule names `kv-list`), so
  listed facts ran together with no space or rule between them.

## Decision

1. **The document lists them; the craft page payload is unchanged.** A curated craft's document
   lists each fact the dossier does not hold that no published section, curated text item or
   curated figure cites, under its own field (`Claim.field`, the field coverage counts) in the
   chapter `coverage_chapters.FIELD_CHAPTERS` gives it: after the field's curated sentences and
   fact grid, or under the field's heading when the field has no section. It is decision 0149's
   rule for generated pages, through the same `craft_page_unwritten.unwritten_facts`, order and cap
   of twelve. `with_page_claims` no longer writes a listed fact into prose; it adds to its
   discipline's prose only a page claim that no section, structure or list shows (one filed under
   no field, or one past its field's twelve), so the document still shows every claim of the page,
   once. A fact a curated sentence comes to cite leaves the list. Refused: a new `field_facts` part
   in the craft page's chapters. The web draws no craft page chapter for a curated craft, so the
   part's only reader would be the document, which lists facts its own way; it is a new tagged
   variant, which the release before refuses while the backend ships first (decision 0151 ignores
   unknown fields, not unknown variants); and its fields would need a golden to carry them, which
   no curated golden with a contributed fact exists to do.
2. **A fact a curated figure shows is not listed.** The facts the list leaves out are those a
   section, a curated text item or a curated figure cites (`monograph_generated_structure.shown_claim_ids`),
   for generated and curated pages alike, so a figure's fact is drawn once.
3. **One cited list.** `components/monograph/CitedList.tsx` draws every run of `li` units of a
   document, registered where a passage draws its pieces (`MonographPassage`): a `ul.kv-list` under
   a hairline, each item a hairline row (`border-rule`) in reading text at body-sm in ink-1 with its
   sentence's citation cluster, set 16 px below the prose before it and 24 px above what follows.
   The space sits on a wrapping block because the kit's reset outranks utilities on lists. Refused:
   a `.kv-list` rule in the kit stylesheet, which the approved Kutch Ajrakh page and its parity run
   share; the authored page draws no passage, so it is unchanged.

A closed source keeps decision 0149's rule: a listed fact is cited with its source and locator and
no quote.

## Consequences

- No migration and no data written. The stored copy of every generated document is rebuilt after
  the release, since the page code's fingerprint is part of its stamp. Sanganeri's sixteen facts
  then sit in the lists of their fields: Health and safety in How it is made, Physics and Botany
  in The chemistry, Geology and Climate in Why Rajasthan; the two the seasons figure shows are no
  longer listed.
- Any filed fact a curated craft's prose held only through `with_page_claims` moves to its field's
  list the same way; on the test seed two Chemistry facts move from the materials prose.
- The craft page payload is unchanged: a fact no item cites stays in its `claims` only. A check of
  that payload's chapters still finds no list; the document is where readers see it, and the
  release's round trip (`frontend/e2e/release/mcp-contribution.spec.ts`) reads the document.
- The Hypotheses list of a generated document is drawn by the same component.
- A field holding more than twelve unwritten facts still lists twelve; the rest read as prose of
  their discipline.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in the contracts named above. Its rules are tested by
`backend/tests/db/test_curated_listed_facts_db.py`, `backend/tests/layouts/test_generated_structure.py`,
`backend/tests/db/test_unwritten_facts_db.py`, `frontend/e2e/cited-list-unit.spec.ts` and
`frontend/e2e/monograph-slot-unit.spec.ts`, and run live by `frontend/e2e/release/mcp-contribution.spec.ts`.
