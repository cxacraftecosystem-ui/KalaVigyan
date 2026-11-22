# 0130. One craft can be released as its own dataset with its own DOI

An open-data release has a scope: the whole knowledge base, as decision 0116 set, or one craft. A
craft release holds that craft's slice of KalaVigyan's knowledge under the same tables, fields,
licence and rules of what is left out, and is deposited on Zenodo as its own record with its own
concept DOI, so Kutch Ajrakh can be cited as a dataset of its own.

Date: 2026-11-22. Status: accepted (owner, 2026-11-22, on the first production DOI: "for the doi
publishing, publish the ajrakh one"; and then: "do not publish anything yet, just sandbox it"). It
amends [decision 0116](0116-open-data-with-a-doi.md). The contract is
`docs/contracts/open-data.md`, A craft release.

| For | Read |
|---|---|
| The contract it changes | [open-data.md](../contracts/open-data.md) |
| The release it scopes | [decision 0116](0116-open-data-with-a-doi.md) |
| The craft scope it reads through | [decision 0122](0122-evidence-reach.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Decision 0116 releases the whole knowledge base as one dataset, versioned under one concept DOI.
The owner asked for the first production DOI to be Kutch Ajrakh's: the craft whose page is the
owner-approved exemplar, with the most curated structure and the most reviewed facts. Publishing the
whole knowledge base to give Ajrakh a DOI would make the citable object far larger than the work a
paper about Ajrakh cites, and a new version of it would move every time any other craft changed.
A paper about one craft needs a record that holds that craft and changes only when it does.

## Decision

1. **A release has a scope.** `OpenDataRelease.scope` (migration `0062_open_data_scope`) is null for
   the whole knowledge base and a craft's slug for a craft release. A version is unique per target
   and scope (`NULLS NOT DISTINCT`), the latest release and `CHANGES.md` are per target and scope,
   and existing rows keep a null scope.
2. **The slice is what an answer about the craft reads.** The facts are those the craft scope of
   stored search reaches (`retrieval/hybrid.craft_scope` and `statements.scope_claims`, decision
   0122): the craft's own concepts and those of crafts merged into it, its sub-category's shared
   concepts and its category's science, under every rule 0116 sets for a released fact. With them
   come their exportable citations and sources, the craft's row and places, its category and
   sub-category, its own stages, materials, reactions, native names and GI record, the components
   of the craft or of no craft that rest on a fact of the slice, and the records of the datasets
   those components cite. Every table keeps its columns; a table may be empty. Same data gives the
   same bytes per scope.
3. **Its words name the craft, from the database.** The title is "<craft name>: KalaVigyan open
   knowledge", with the craft's display name, never typed. The README, `datapackage.json`,
   `CITATION.cff` and the Zenodo description say it is the slice of KalaVigyan's knowledge about
   that craft, with its row counts and what is left out; the keywords add the craft's name; the
   related identifiers add the craft's monograph page (`isDocumentedBy`) beside the dataset page
   and the code. The creator, licence (`cc-by-4.0`), access and language are the whole release's.
4. **Its own record.** Every step of `app.scripts.build_open_data` takes `--craft`, and the
   workflow `open-data.yml` takes a `craft` input (empty: the whole knowledge base) and passes it
   to every step. The draft of a scope with no published release is a new Zenodo record, so a new
   concept DOI; the draft refuses a new version whose inherited title is not the one it sets, so a
   craft release is never a version of the whole-knowledge record. The deposit refuses files whose
   descriptor names another scope than the run. `publish` stays false by default.
5. **It is listed and shown apart.** `GET /api/open-data` keeps schema 1 for the whole release and
   lists published craft releases under `craftReleases` with the craft's slug and name, both DOIs,
   the record, the files, the counts and their own citation. The `/data` page shows them after
   every release, and a craft page's Cite this monograph adds the newest craft release's DOI when
   one is published; a craft with none shows nothing new.

## Consequences

- Kutch Ajrakh can be cited by a DOI of its own; a paper about it is not tied to every other
  craft's changes.
- A fact shared by a craft family appears in each of its crafts' releases and in the whole
  release; each record states its own scope, so the overlap is visible and expected.
- The first production run for a craft creates that craft's concept DOI; later runs add versions
  to it. A sandbox run rehearses the same steps under `10.5072`.
- Kutch Ajrakh's page draws its Cite this monograph from its authored citation tool, which does not
  render `CiteThis`; the DOI line reaches it once that tool mounts the same line, a change outside
  this decision's files.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-22; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/db/test_open_data_scope_db.py`, `backend/tests/open_data/test_open_data_scope.py`,
`test_open_data_craft_files.py`, `test_open_data_craft_deposit.py`, `test_open_data_workflow.py`
and `frontend/e2e/open-data-crafts-unit.spec.ts`.
