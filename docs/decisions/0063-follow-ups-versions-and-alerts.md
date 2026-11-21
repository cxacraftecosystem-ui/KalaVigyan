# 0063. Follow-ups that build, version history, saved explainers and alerts

A follow-up is an ordinary sectioned answer stored as the explainer's next version without touching
an earlier one, and a deepened section only adds. Saved explainers reuse `SavedItem`, the nightly
job checks them again with no model call, and the weekly digest is built and switched off.

Date: 2026-11-18. Status: accepted. Amended by 0070 (the digest links each item to
its explainer).

| For | Read |
|---|---|
| What amended it | [0070 Phase D review fixes](0070-phase-d-review-fixes.md): the digest links each item to its explainer |
| The contract it was built to | [0062 Phase D contract: learning blocks, versions, alerts, lessons, exports and the map](0062-phase-d-contract.md) |
| The contracts it names | [learning.md](../contracts/learning.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Plan features 15 and 16 (`docs/plans/answer-experience.md`, section 4) and the contract of
decision 0062 (`docs/contracts/learning.md`): a follow-up adds or deepens sections of the same
explainer and is stored as the next version without touching an earlier one; a saved explainer
is re-checked when new claims arrive for its craft and fields, the reader gets an in-app note and,
once the owner has an SES sender, a weekly email. The answer flow (decisions 0032 and 0033) runs
one sectioned answer per ask and numbers sections and blocks from 1; a `SavedItem` table from the
first schema existed with no code using it.

## Decision

1. **A follow-up is an ordinary sectioned answer with a layout.** `services/follow_ups.py` turns
   the base version and the fields to research into an `AnswerLayout`: a field the explainer
   already has deepens that section (its id, order and shown title), any other field becomes a new
   section after the explainer's own (next id, next order). The answer flow runs these sections
   through the same research, compose, builders and pictures as any answer; only the layout
   differs. `buildsOn.facets`, when given, are exactly the fields researched (the alert's Update
   sends the fields with news); empty, the question's fields are, as for a first answer, capped
   by the depth's section count.
2. **A deepened section only adds.** Its blocks are numbered after every block it showed
   (`section_deepening.Deepening`), a sentence whose claims the explainer already cites is dropped
   before blocks are built (so a section that finds nothing new may run its fresh research), and
   kinds the section already shows are not built again: no second ladder, no second picture strip,
   builders of a shown kind are left out (`BlockBuilders.without`). Deepened sections are never
   answered from stored pieces and are not stored as pieces, so a partial section never supersedes
   a whole one; new sections reuse and store pieces as usual.
3. **The stored version is merged on the server and checked by the contract's rule.**
   `services/version_merge.merged_version` keeps every base section and block, puts the added
   blocks after the section's own and before its pictures, places added sections that found
   something after the base (an empty one is left out and later ones close up), lists sources by
   first citation and writes the `VersionMark`; `version_problems` must be empty or the version is
   refused loudly. The follow-up's answer row keeps the merged document and the mark
   (`payload.version`), and its `claimIds` are every claim the merged document cites, so a
   retraction marks every version that shows the claim. A follow-up that adds nothing stores no
   version and emits no `version` event.
4. **Versions are indexed columns.** `Answer.explainerId` and `Answer.explainerVersion` (migration
   `0020_explainer_versions_alerts`; version 1 is the explainer's own answer, backfilled for
   every stored explainer) carry a unique pair, so two follow-ups racing on one version cannot both
   be stored: the second ends with "A newer version of this explainer was saved meanwhile". The
   asker is the answer rows' `userId`; every explainer, saved and note route answers 404 to anyone
   else, Master Admins included.
5. **Saving reuses `SavedItem`.** A saved explainer is a `SavedItem` with `answerId` (version 1),
   gaining `seenVersion` and `checkedAt` and a unique (reader, answer) index. Lists read the
   question and understanding of version 1 and the fields of the latest version with JSON paths, so
   no document is loaded to list them.
6. **The re-check is the nightly job's last module, with no model call.** `app.scripts.recheck_saved`
   runs after `link_compounds` in **Coverage enrichment**: for each saved explainer of a known
   craft it counts fact-level claims the reader's depth can see (`retrieval/statements` scope),
   created or raised in level since `checkedAt` (else since the latest version), that the latest
   version does not cite, per saved field (a curated claim's discipline, else its concept's
   heading through `HEADING_DISCIPLINES`; an edge claim maps to no field). Raises are read from
   `ReviewEvent` level moves. A count of at least one writes one `ANSWER_IMPROVED` note; an unread
   note for the same explainer and version is replaced by one that adds its counts, so nothing
   unread is lost (a partial unique index keeps one unread note per explainer). Curated imports
   at a deploy are caught the next night.
7. **The weekly digest is built and switched off.** `app.scripts.send_alert_digest` runs from the
   new **Alert digest** workflow on Mondays at 09:00 India time and sends, through the existing SES
   mailer, each opted-in, active reader's unread notes of the last seven days (at most 20), once
   per week (`AlertDigestSend`, claimed before sending and released when SES refuses). It does
   nothing while `ALERT_DIGEST_ENABLED` is false (default) and refuses to run enabled without
   `MAIL_FROM_ADDRESS`. The opt-in is `PreferencesUpdate.alertDigest`; preferences also answer
   `alertDigestOffered` so the client draws the toggle only when the digest can be sent. Tests
   never send mail: the sender is passed in.

## Consequences

- `stored_explainer` and the payload keys have one home (`services/explainer_payload.py`);
  `answer_store` and the Listen store import them. Block and open-question translation moved to
  `services/section_language.py`, so `answer_sections.py` stays within its budget.
- `explainer_document` numbers a document's sections by position, so a follow-up's own document
  is valid before it is merged; first answers are unchanged.
- Owner steps (`docs/PROGRESS.md`, Waiting on the owner): verify an SES sender, then set
  `ALERT_DIGEST_ENABLED=true` in Parameter Store. The screens (explainer history, Save, notes,
  Update, the digest toggle) are lane 0069's; items left are in `docs/TECH_DEBT.md`.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
