# 0181. A craft's community and person names stay out of AI pictures, Expert research follows OpenAlex reference lists, and the Wood Handbook's cited chapters are its passages

Each craft keeps a list of the communities and people its cited quotes name, used only to keep those
names out of AI picture prompts and never shown to readers; Expert research follows a read work's own
reference list through OpenAlex in the room its cited DOIs leave; the five chapters of the 2010 Wood
Handbook the wood claims cite are vendored as they were read and stored as that source's passages; and
Dabu's indigo dyeing carries the reaction its GI journal quote states.

Date: 2026-11-23. Status: accepted (the lead's evening brief of 2026-11-23, lane E, sources and
names; the owner's decision of 2026-11-22 on community and practitioner names). It amends
[decision 0022](0022-batch-3-review-fixes.md) (the group words that keep a claim out of a prompt) and
[decision 0009](0009-planner-and-tiered-research.md) (which references research follows). The
contracts are `docs/contracts/media.md` (The claim set, Prompt), `docs/contracts/knowledge-writes.md`
(Structure proposals), `docs/contracts/curation.md` (The import), `docs/contracts/research.md` (Follow
references, Reference lister) and `docs/contracts/retrieval.md` (the seed import's passages).

| For | Read |
|---|---|
| The group words it adds a craft's own names to | [decision 0022](0022-batch-3-review-fixes.md) |
| The named-cluster flag it leaves on places | [decision 0018](0018-media-backend.md) |
| The reference following it widens | [decision 0009](0009-planner-and-tiered-research.md) |
| The rule that no change adds model calls or input tokens to a measured answer | [decision 0165](0165-answers-counted-as-settled-asked-as-asked.md) |
| An import that never undoes approved structure | [decision 0171](0171-imports-keep-approvals-and-differences-settle.md) |
| Every decision, by group | [README.md](README.md) |

## Context

- **Names.** A claim, stage name or style hint was kept out of an AI picture prompt only when it used a
  group word (`NAMED_GROUP_WORDS`): "Khatri printers lay the pa" reached the model. The owner decided
  on 2026-11-22: build a per-craft community and practitioner name list from cited sources only, used
  only to keep names out of AI picture prompts, every addition reviewed. The dossiers already hold
  each craft's `communities` (`COMMUNITY`, `PERSON`, `ORGANISATION`) with the facts that name them;
  Kutch Ajrakh's own quotes state four of its names (Khatri, Maldhari, Ismail Mohammad Khatri,
  Abduljabbar M. Khatri).
- **References.** Research followed only DOIs written in a read text. An OpenAlex abstract carries no
  DOIs, so a work found there gave no lead, though OpenAlex holds its reference list
  (`referenced_works`). A recorded call on 2026-11-23 showed the `cited_by:<work>` filter returns
  exactly those works; with `search` on top it returned none of 21, and with `has_abstract:true` and
  `sort=cited_by_count:desc` it returned 9 of the 21, most cited first, each with its abstract.
- **The Wood Handbook.** The 26 wood claims of the inferential-system seed cite FPL-GTR-190 (2010)
  by chapter title with no quote, and the repository held no text of it. A copy of the 2021 edition
  (FPL-GTR-282) exists outside the repository. The five cited chapters of the 2010 edition read
  through `tools/curation/fetch.py` (Wayback copies of the FPL's chapter PDFs).
- **Reactions.** A bounded search (about an hour) found the indigo air oxidation already quoted by
  Dabu's GI journal source (Bagru application 183), Akola's mud stage order in GI application 845's
  statement of case (readable only by POST, so not by the reader), and block carving placed first in
  Machilipatnam's GI method of production and before printing for Sanganer; both of those dossiers hold
  the 150 claims a dossier may.

## Decision

1. **A craft's names are a stored list, seeded from its dossier.** `CraftGroupName` (migration
   `0099_craft_group_names`, row level security on, no public grants) holds each name with its kind
   (`COMMUNITY` or `PERSON`), origin, the quote that states it with its source's title and address,
   and its case-folded `nameKey`, once per craft. The dossier import writes, for every `COMMUNITY` and
   `PERSON` group, each name and local name one of the group's own quotes states by the structure
   proposal's `STATED` check (`curation/group_names.stated_group_names`), origin `DOSSIER`. A name is
   never removed by a later version: a list that only keeps names out fails closed. Organisations are
   not listed. Chosen over a hand-kept seed file because the dossiers already hold these names with
   their citations, so a second copy could only drift.
2. **Additions pass review as a structure kind.** `GROUP_NAME {name, groupKind}` is a structure
   proposal with sources and no field, statement or task, checked `STATED`, `QUOTES` and `SOURCE` (the
   name gated as its own statement), on any craft, curated or not, and never on a category. Approved,
   it writes one `PROPOSAL` row and nothing else: no fact, no page entry, no export, no page refresh.
   The review card says what approving does. Chosen over a new queue kind because structure is the
   reviewed path the code already has for a craft's structured data.
3. **No prompt carries a listed name.** A claim naming one is left out of the claim set, a stage name
   naming one is left out of the prompt, a style hint naming one is refused, a prompt whose facts
   still name one is refused, and the worker ends a queued job whose prompt names a name listed since
   as `BLOCKED` (refunded) before it calls a model. Names match case-folded, as whole words with
   their spaces collapsed, singular or plural (`research/named_groups.names_a_listed_group`). Since
   no generated asset can name a listed name, `depictsNamedCluster` keeps comparing places only.
4. **Expert research follows reference lists in one call each.** `ReferenceLister` is a research
   contract (`lists(item)`, `references(item, k)`); `OpenAlexAdapter` lists a work by its OpenAlex id
   with `cited_by:<work>,has_abstract:true`, most cited first. After the cited DOIs, each read
   document the lister lists fills the rest of its five references from its list, in reading order,
   inside what the DOIs leave of the reserve. Chosen over fetching `referenced_works` one by one (up
   to five calls a document, most without abstracts) and over a search-ranked list (no hits). Only
   `DEEP` follows references, so the measured Basic and Detailed answers make the same calls and
   read the same documents as before (decision 0165); no model call is added anywhere.
5. **The cited edition is vendored.** `backend/app/data/source_texts/fpl-gtr-190/` holds the five
   cited chapters as the reader read them, with the SHA-256 of each text in `source.json`; the loader
   refuses a text that differs. A seed source with a vendored text takes its pages as its passages
   instead of its quotes, each page cut at its printed label and located by chapter, title and page.
   Chosen over re-citing the claims to FPL-GTR-282: that would cite another edition than the one the
   claims were drafted from, change the generated seed file of another lane's pipeline, and need a
   verbatim quote stating each of 26 paraphrases.
6. **Dabu's reaction, and what the search left.** Dabu's stage P07 carries reaction `R01` (reduced
   indigo and atmospheric oxygen to oxidized indigo) on claim C112, whose GI journal quote names all
   three (dossier version 2, verified 16 of 16 sources and 217 of 217 quotes). The searches for Dabu,
   Machilipatnam and Sanganeri are in their dossiers' `searched`; what is left stays in the register.

## Consequences

- The first deploy's import lists every stated name of every curated craft; a second import lists
  none. A craft with no dossier gets names only by proposal.
- Over-blocking is possible where a listed name is also an ordinary word of a craft's facts (Kumar,
  Naga, Muslim); it costs a stage a fact for its picture, never a name in one.
- Expert answers may read more of their reference reserve than before; their fetch limit is unchanged.
- The new item kind would have taken `tools/list` past its 60 KiB input budget (decision 0159), so
  `mcp_schemas.compact` drops a default that only repeats its node's `const` (every item's `kind`
  tag), and `propose_structure`'s description and argument text were shortened; the list's inputs
  measure 61,369 bytes of 61,440.
- The Wood Handbook's 137 printed pages become public passages, embedded by `embed_knowledge` after
  the seeds, and wood questions can now cite its pages.
- `index.json` is stale for Dabu until the lead regenerates it (`check.py --write-index`).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by `backend/tests/research/test_named_groups.py`,
`backend/tests/media/test_claim_set.py`, `backend/tests/media/test_prompt.py`,
`backend/tests/media/test_runner.py`, `backend/tests/structure/test_group_name_proposals.py`,
`backend/tests/curation/test_group_names.py`, `backend/tests/db/test_group_names_db.py`,
`backend/tests/planner/test_reference_lists.py`, `backend/tests/sources/test_openalex_references.py`,
`backend/tests/retrieval/test_vendored_texts.py`, `backend/tests/db/test_retrieval_passages_db.py`,
`backend/tests/mcp/test_tool_budget.py` and `frontend/e2e/review-structure-unit.spec.ts`.
