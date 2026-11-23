# 0171. An import never undoes approved structure, a sources-differ flag lasts while a live pair holds it, and a retired dossier leaves no records

The dossier import takes a craft's or a category's file only when the file holds every fact and
conflict a reviewer approved into its page, and otherwise leaves the page as the database holds it.
A `sourcesDiffer` flag is worked out again whenever a fact it rests on is decided, released, refiled
or superseded, and the import keeps the flag a live differing fact holds. Retiring a dossier also
deletes its places, GI record, prices and workforce rows.

Date: 2026-11-23. Status: accepted (the lead's brief "fix knowledge integrity", from the adversarial
review of the whole codebase on 2026-11-23, which confirmed six findings). It amends
[decision 0053](0053-curated-dossier-import.md) (item 4, supersession), [decision
0108](0108-structure-proposals-become-curated-facts.md) (item 4, the export follows) and [decision
0142](0142-curated-crafts-read-only-curated-rows.md) (item 2, retiring a removed dossier). The
contracts are `docs/contracts/curation.md` (The import), `docs/contracts/dossier-export.md` and
`docs/contracts/knowledge-writes.md` (Sources differ).

| For | Read |
|---|---|
| The import it amends | [decision 0053](0053-curated-dossier-import.md) |
| The approvals it keeps safe and the export that follows them | [decision 0108](0108-structure-proposals-become-curated-facts.md) |
| The shared rows an approval writes at once | [decision 0162](0162-unused-craft-page-chapters-retired.md) |
| The retirement it extends | [decision 0142](0142-curated-crafts-read-only-curated-rows.md) |
| The import and its report | [curation.md](../contracts/curation.md), The import |
| The export a new version is built on | [dossier-export.md](../contracts/dossier-export.md) |
| The gates and the sources-differ rule | [knowledge-writes.md](../contracts/knowledge-writes.md) |
| A person clearing a fact's sources-differ mark, which settling keeps | [decision 0170](0170-review-over-mcp-staged-and-pages-refreshed-now.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Since decision 0108 an approved structure proposal (a stage's after or why, a native name, a
reaction, a botanical name, a glossary term, a conflict, an open question, a GI record, an
alternative) is written into the database: a curated fact with its `CuratedClaim` marker, an entry
in the page index, and for some kinds a `Reaction` or `CraftGiRecord` row. The dossiers in git are
the database's export, refreshed only when the lead runs `export_dossiers --out`. Every deploy runs
`import_curation` on the files in git, and nothing compared what the database held with the file:
the import superseded every curated fact the file did not list, wrote the file's page index over the
stored one, deleted reactions the file did not plan and replaced the GI record. Once the page index
was rewritten, a later export no longer found the fact either. So every deploy after an approval
undid it.

The same review found that the `sourcesDiffer` flag only ever went up. The import rebuilt it from
the file's conflicts and cleared the flag a contributed fact had set on a curated one; a held
write-back released to live never got it; retracting a differing fact left its rival flagged; and a
fact approved under another craft flagged the facts of the craft it was held for. Retiring a dossier
left its GI year and places on the catalogue and the map.

## Decision

1. **The import compares the file with the approvals, by content.** Before it writes anything,
   `services/curation_approvals.unheld_approvals` reads every `APPROVED` structure proposal of the
   craft (or category) whose fact is still shown, and the plan of the file must hold each one: a
   proposal's fact under its key with the wording the database holds, and an approved conflict with
   each of its shown facts marked as differing. A file that misses one is `BEHIND`: nothing is
   written, the outcome lists each missing approval by key, kind and day after one line saying to
   export the dossier and build any new version on that export, and the script does not stop the
   release for it (`behind` in the report, exit 0, as for `WAITING`), since approvals arrive at any
   time between exports and the database already serves them. An approved fact leaves its dossier
   only through review (a retraction), never through a new version of the file.
   Three other ways were refused. Comparing the stored version or digest with the file: a version
   bumped by hand on a stale file is indistinguishable from the export, a digest only tells that the
   file changed, and a category's export already requires the file at the stored version. Writing
   approvals back into the dossier when they are approved: the server cannot commit to git.
   Exporting on deploy before importing: it would overwrite a bulk import committed in git.
2. **A flag lasts while a live pair or a curated conflict holds it.** Two facts differ live when a
   passed DUPLICATE outcome of one names the other, both are held (shown or waiting), at least one is
   shown, and both rest on one craft's facts as the gate compares them: the same craft, a craft and its
   own family's facts, or two shared or family facts of one family (`services/sources_differ`).
   `settle_sources_differ` sets the flag on each fact it is given and on each fact it was paired with
   when such a pair or a conflict of a curated page holds it, and clears it (with `differsOn`) when
   neither does. It runs after every review decision on a fact (approve, raise, reject, retract and
   refile, so a fact filed under another craft keeps no flag against the craft it was held for), after
   a write-back files a stored claim again (a release from hold among them), and after an import or a
   retirement supersedes curated facts. The import keeps the flag and `differsOn` of a curated fact a
   live pair holds (`curation_claims.kept_differences`), so a second import still writes nothing. A
   mark a person cleared (decision 0170, audited `review.sources_differ_cleared`) is a review and
   stays cleared: it dismisses every pair judged at or before the clearance and every curated
   conflict naming the fact that was not approved after it, for settling and for the import alike
   (`services/differ_clearances`); only a pair judged later, or a conflict approved later, flags the
   fact again. The go-live mark (`mark_sources_differ`) stays as it was. Clearing a refiled fact's recorded outcome
   was refused, since it rewrites the gate's record; a column naming the subject an outcome was judged
   under was refused, since the fact's concept already says it.
3. **Retiring a dossier removes its records.** `retire_dossier` also deletes the curated
   `CraftLocation` rows its page index names and the `CraftGiRecord`, `CraftPrice` and
   `CraftWorkforce` rows that cite its curated facts, so the catalogue's GI year and the map's points
   leave with the facts (`records` in its summary).

## Consequences

- No migration and no new served field: the import report gains `behind` and the status `BEHIND`,
  and the retirement summary gains `records`; both are tools' output.
- A dossier the database has moved past stays as the database holds it until the lead exports it
  (`export_dossiers --out app/data/curation`) and commits the export; the deploy log names each
  approval the file lacks. A bulk import is built on that export.
- Approvals that deploys undid before this change are not restored by it: their facts are
  `SUPERSEDED` with a `curation import` review event after their approval. They can be found by that
  pair of events and proposed again.
- `review_queue_facts.decide_fact` calls `_settled_differences` where it called `_published`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-23; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md). Its rules are tested by
`backend/tests/curation/test_curation_approvals.py`, `backend/tests/curation/test_curation_claim_rules.py`,
`backend/tests/knowledge_writes/test_sources_differ.py`, `backend/tests/db/test_structure_export_db.py`,
`backend/tests/db/test_sources_differ_db.py`, `backend/tests/db/test_held_write_backs_db.py` and
`backend/tests/db/test_seed_retirement_db.py`.
