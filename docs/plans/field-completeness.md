# Every field on every page: completeness research (decision 0101, step 6)

Status: proposed, waiting for the owner's approval of the spend and a Researcher session token
(2026-11-20). The owner's direction the same day: "information density encompassing all the fields
is spectacular on all the pages".

| For | Read |
|---|---|
| What each page holds per field, as data | [contracts/coverage.md](../contracts/coverage.md) |
| The method each agent follows | [kalavigyan-craft-pages](../../.claude/skills/kalavigyan-craft-pages/SKILL.md) |
| The architecture this is step 6 of | [decision 0101](../decisions/0101-knowledge-architecture-for-every-craft.md) |

## Where we stand

Counted by `.claude/skills/kalavigyan-craft-pages/scripts/gaps.py` over the 41 curated dossiers (32
crafts and families, 9 categories), with communities and the GI record counted for society and
policy:

| Measure | Value |
|---|---|
| Fields covered per dossier (of 16) | minimum 8, median 13, maximum 16 |
| Dossiers at the bar of 12 or more | 31 of 41 |
| Dossiers with any claim in the field | overview, process, materials, geography, history, economics, design and society 41; chemistry 30; physics 28; ecology 25; policy 24; geology 22; climate 21; health 21; botany 16 |
| Kutch Ajrakh, the exemplar | 13 of 16: physics, geology and health missing; climate and ecology under 3 claims |

The other 420 crafts of the 461 have no dossier: they show the "craft without a monograph"
template and its research questions until researched.

## What is already built or being built

- The bar is in the skills: craft-pages "Every field, densely" and checklist rules 23 to 26; design
  system principle 10. `gaps.py` reports fields covered, fields with no claim and thin fields.
- Round 5 (lane fields-and-ask): coverage per page as data (in the document, at an API route and
  over MCP), every field with sections placed in its chapter, missing and thin fields as open work,
  the expert panel choosing seats by field, and an answer-quality evaluation across all 16 fields
  (`answer-quality` workflow, dispatched by hand).

## Proposed phases

| Phase | Work | Estimate (Claude Code use) | Agents |
|---|---|---|---|
| A | Deepen the 41 curated dossiers to the field bar: search every missing field, add 3 or more cited claims to each thin one (botany, climate, health, geology, policy and ecology first) | 250 to 400 thousand tokens per dossier, 10 to 16 million in all (wave 0 measured 0.9 to 1.1 million for a whole dossier) | Sonnet, one dossier per agent, 5 per round, about 9 rounds |
| B | First dossiers for the GI-registered crafts that have none, minister-facing order of the craft-pages skill | about 1 million tokens per craft | Sonnet, 5 per round |
| C | The remaining crafts, by prominence | about 1 million tokens per craft | as B |

Each agent follows the craft-pages skill: verifier and checker as judges, no critic panels, stop at
about 60 turns, report gaps before and after.

## What the owner decides

1. Approve phase A (and later B and C) with its estimate.
2. Give a Researcher session token for `tools/curation/propose.py` (facts go through the gates), or
   allow phase A to travel as dossier versions through the bulk import, as structure does.

## How this document is kept true

| Part | Kept true by |
|---|---|
| The counts in Where we stand | `.claude/skills/kalavigyan-craft-pages/scripts/gaps.py`, run on 2026-11-20; run it again to refresh them |
| The status line | changed when the owner decides |

Re-read it when a phase is approved or finished.
