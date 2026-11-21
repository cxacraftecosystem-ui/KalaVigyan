# 0116. KalaVigyan's knowledge is an open dataset with a DOI

KalaVigyan's published facts, their citations and curated structure are released as a versioned open
dataset under CC BY 4.0 with a Zenodo DOI, without the cited works' verbatim quotes or any
contributor's name. The same data gives the same bytes, each release is recorded with its row
digests, and `GET /api/open-data` lists how to cite it.

Date: 2026-11-21. Status: accepted (owner, 2026-11-21: "We should be able to publish the data with a
DOI."). The contract is `docs/contracts/open-data.md`.

| For | Read |
|---|---|
| The contract it fixes | [open-data.md](../contracts/open-data.md) |
| Every decision, by group | [README.md](README.md) |

## Context

KalaVigyan's facts, their citations and the structure curated around them live in its database and
reach readers through its pages, the knowledge API and the MCP server. Researchers who want to cite
or reuse the knowledge itself had no stable, versioned and citable copy of it: the per-craft export
(`GET /api/knowledge/crafts/{slug}/export`) is live and per craft, carries the verbatim quotes of
third-party sources, and has no identifier a paper can cite. A DOI needs a repository that mints
one per version and keeps every version; Zenodo (CERN) does both, for free, through a REST API, with
a sandbox for rehearsals and a concept DOI that always resolves to the newest version.

## Decision

1. **What a release holds.** Fourteen tables: `claims` (every published fact: a status that is
   shown, sensitivity OPEN, not held while its quotes fail, with a visible subject and at least one
   citation a signed-out reader may read), `citations` (fact, source, locator, relation, whether a
   quote stands there and its last check), `sources` (title, authors, publisher, year, DOI,
   address, Wayback copy, language, access, grade A to D, licence and attribution as recorded),
   `crafts`, `craft_places` (LGD state and district codes), `categories`, `families`, `stages`,
   `materials`, `reactions`, `native_names`, `gi_records`, `components` (the catalogue's metadata
   and the facts each rests on) and `datasets` (the map datasets' records). Structure rows keep only
   the facts that are released, and a row with none is left out.
2. **What it never holds.** The verbatim quotes of cited works: their words stay under their own
   terms, and a citation carries the locator and the source's address so anyone can read the quote
   at its source. No contributor's or reviewer's name, no `createdById` or e-mail. No held fact, no
   supplied text (decision 0110), no restricted source or researcher-only passage, and no
   `FIELD_TESTIMONY` source at all: the portals' recordings, photographs and artisans' own accounts
   were given for KalaVigyan's pages, and nothing records a right to redistribute them, so the
   release fails closed on all of them. No dataset values or geometry: only their records.
3. **Its licence.** KalaVigyan's own sentences and structure are CC BY 4.0, with the attribution
   "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur.
   KalaVigyan open knowledge, licensed under CC BY 4.0", and the release says plainly that cited
   works keep their own licences.
4. **Its files.** Each table as JSON Lines (every field present, compact, UTF-8) and as a CSV view
   (lists and objects as JSON, an empty cell for no value); a Frictionless Data Package descriptor
   with every field's type, meaning and requiredness, primary and foreign keys, and each file's size
   and SHA-256; `README.md` in plain English with the data dictionary; `CITATION.cff`; `CHANGES.md`
   against the previous release; `SHA256SUMS`. File names are flat because Zenodo has no folders.
5. **Same data, same bytes.** Rows are sorted by key, dates are UTC to the second, the release date
   comes from the version (`YYYY.MM.DD`, or `YYYY.MM.DD.N` for a second release that day), and no
   file names the time it was built. Volatile columns (a fact's `updatedAt`, a quote's `checkedAt`)
   are left out so a nightly re-check does not mark every row changed.
6. **Changes without keeping old files.** Each release stores a 16-hex-digit digest of every row by
   its key (`OpenDataRelease.rowDigests`); the next build compares against the latest published
   release of the same target and lists what was added, removed and changed. The files themselves
   live on Zenodo.
7. **The DOI.** The workflow `open-data.yml` (dispatch only) runs on GitHub's runner and on the box:
   it reads the latest published release from the database, opens a Zenodo draft (a new version of
   the concept record when there is one, its inherited files deleted), reserves the draft's DOI,
   builds the release on the box with that DOI and the concept DOI written into its files, copies the
   files to the runner through the deploy log prefix both roles may use, checks every checksum,
   uploads, describes and publishes the draft, and records the publication. Unticked it uses the
   Zenodo sandbox and `ZENODO_SANDBOX_TOKEN`; production needs `publish=true` and `ZENODO_TOKEN`,
   and never runs without both. A Zenodo token never reaches the box. Sandbox releases are recorded
   as `SANDBOX` so rehearsals can version too, and only `ZENODO` releases are listed publicly.
8. **Recording.** `OpenDataRelease` (migration `0057_open_data_releases`) keeps each release's
   target, version, release day, DOI and concept DOI, record ids and address, files with sizes and
   checksums, row counts, change counts, row digests and publication time. A published version is
   never rebuilt; a record step must name the DOI its build used.
9. **Citing it.** `GET /api/open-data` (public, counted like every public read) lists the published
   releases newest first with sizes, download links, the citation in text and BibTeX and the data
   dictionary. The `/data` page shows it, and both footers link "Cite this dataset". The creator is
   the institution, never a person.

## Consequences

- The release is built from the database, so what readers see and what the dataset holds cannot
  drift: a fact retracted before a release is absent from it, and `CHANGES.md` says so.
- The owner creates the Zenodo accounts and tokens (the PR body and the lead's runbook notes say
  how); the first production run creates the concept DOI, and every later run adds a version.
- A run that fails after opening a draft leaves it on Zenodo; the next run reuses an open draft of a
  new version, and an unpublished first draft can be deleted from Zenodo's uploads page.
- Facts whose only citations are field testimony stay out of the dataset until a recorded right to
  redistribute them exists; a later decision may add that right to the portals' consent.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-21; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
