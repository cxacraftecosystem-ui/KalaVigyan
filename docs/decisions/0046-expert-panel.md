# 0046. The expert panel

The expert panel seats experts from the stored understanding, each giving a cited take on a section
in one panel call that passes the prose checks or is not shown. "Experts differ" appears only for
two stored facts about one subject from two sources, and panel calls spend only from the answer's
headroom.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| What superseded part of it | [0093 No caps for now: every AI cap defaults to none, and every call asks for its model's documented maximum output](0093-no-caps-for-now.md): its cap values; the code paths stand |
| What built on it | [0099 The expert panel searches its own fields, calls each seat on its own, seats up to 12 at Expert, and hears the artisan from field transcripts](0099-wider-expert-panel.md): the expert panel, widened |
| The contract it was built to | [0042 Phase B contract: place, matter and the expert panel](0042-phase-b-contract.md) |
| What amended it | [0156 The expert panel takes a failing view again, differs across linked concepts and reuses only the seats it seats, and field voices reach the craft page, their pictures and every run](0156-expert-panel-and-field-voices-kept-true.md): point 5 (one retake of a failing take) and point 6 (one subject includes two concepts one glossary term links) |
| The review that fixed it | [0050 Phase B review fixes](0050-phase-b-review-fixes.md) |
| Every decision, by group | [README.md](README.md) |

## Context

Lane 0046 of phase B (`docs/plans/answer-experience.md` section 4 feature 6, decision 0042)
builds the `expert_view` block: seated experts each give a cited take on a section, and where two
sources disagree the reader sees "Experts differ" with both citations. Decision 0042 fixed the
block, the 18 seats (`research/expert_panel.py`) and the rule that a difference is stated by both
seats. Left to this lane: which seats speak where, how the panel shares research and spend, how a
take is written and checked, and when a disagreement is real enough to show. Every fact is cited,
a model only chooses and orders, and no connection is held across a model call (decision 0040).
The renderer is lane 0049's.

## Decision

1. **Seats come from the stored understanding.** `expert_panel.speaking_seats(discipline, seated,
   depth=)` takes `Understanding.seats` (on `Answer.understanding`, carried by the answer's
   `PlanRequest`) in the model's order, once each and only the 18 seats, keeps the depth's first
   `max_experts` (Basic 2, Detailed 4, Expert 10; plan 2.4), and of those the seats whose fields
   include the section's field (`seats_for`). The artisan's voice (`TESTIMONY_SEATS`) speaks only
   from field testimony, which phase E brings, so it is seated but never speaks: no panel call,
   reading share or plan line names it. Seats are never added to reach a depth's minimum.
2. **Planning shares the existing budget with the seats.** The plan call's `Experts` line names
   each seat speaking in the section with the source kinds it reads, most preferred first, and
   asks for queries that find them. The reading order (`planner/reading.reading_order`) takes the
   best found item of each facet as before and, for each speaking seat, the best item of its most
   preferred kind found, and alternates the two lists, so the seats take every other early read of
   the section's own fetch share. No query, fetch or model call is added.
3. **Deep keeps the same part of any share for references.** `DEEP_REFERENCE_RESERVE` (6 of 20)
   was subtracted whole from each section's fetch share, so an Expert section with 6 or fewer
   fetches read none of what it found and followed no reference. The reserve is now the same
   part of the section's share (`policy.reference_reserve`: 6 of 20, 1 of 4, none of 3), so the
   seats' reads exist at Expert depth.
4. **One panel call per section, from the section's verified evidence.**
   `services/expert_views.ExpertPanelBuilder` (registry entry `expert_view`, every field
   `PANEL_FIELDS`, 45 s) runs once a section's prose or ladder is checked. It offers the fact-level
   stored claims the section's checked sentences rest on (`BuildAsk.cited`), those its blocks cite
   first, each with its claim text and its citations' quotes inside an untrusted block; a section
   without a checked block hears no panel. One `COMPOSE` call (`composer/expert_takes`, Claude
   Sonnet first) gets the section line, each speaking seat's label and role brief, the
   statements and the question, and answers `{views[{seat, take[sentence]}], differences[{seat,
   statement, otherSeat, otherStatement}]}` with seats and statement refs as enums of what was
   offered.
5. **A take passes the prose checks or is not shown.** Each take sentence (at most 3) goes
   through the composer's sentence validator (`drafts.checked_sentence`: cited, quotes verbatim
   from the cited statement, numbers only from the quotes) and then `section_blocks.
   prose_problems` (a stored fact, figures held by the claims' texts or quotes); one failing
   sentence drops that seat's whole view. There is no regenerate: the call is optional work.
6. **Experts differ only on two stored facts about one subject from two sources.** A proposed
   pair is kept when the two seats are different and both gave a view, both statements are
   fact-level stored claims of the section, they are two claims, no source is cited by both, and
   both are stored on the same concept (`ClaimView.concept_id`; an edge claim has none and is
   refused). Each pair of seats differs once. The server writes both sides as the claims stand
   stored, with their own citations, into both views, mirrored (decision 0042); no model sentence
   says which is right.
7. **Agreement is a shared claim.** Two views agree when their takes cite one stored claim and
   they do not differ; the agreement is mutual by construction. The model is not asked for
   agreements, because an agreement it named would carry no citation.
8. **Panel calls spend only from the answer's headroom.** Builders get a `COMPOSE` model whose
   principal holds `AnswerSpend.headroom()` (`providers/budget.AnswerHeadroom`): the same
   answer's holds and spend, but a call is allowed only while the answer keeps half its depth's
   cap (`OPTIONAL_WORK_KEEPS`) after it. A refusal is a failed builder: the section shows no view
   and is never failed. Master Admins have no cap, so their panels always run. The route and the
   nightly rebuild pass this model as `build_answer_pipeline(builder_compose_model=)`.
9. **The kind is built.** Lane 0049's renderer (`components/answer/experts/`) and this builder
   are both present, so `expert_view` joins `BUILT_BLOCK_KINDS` on both sides in this change
   (decision 0042 point 11); `e2e/explainer-phase-b-unit.spec.ts` now expects a built phase B
   kind to parse and the others to be refused.

## Consequences

- An Expert answer reads found documents again in every section, and its reads lean towards the
  kinds its seated experts prefer.
- Readers see expert views and "Experts differ" cards after the next deploy. Each section with a
  speaking seat makes one more Sonnet call, bounded to the first half of the answer's cap for
  every role but Master Admin. A section waits for its panel (at most 45 s) before its pictures
  and `section_done`, holding its place among the four sections that run at once.
- Tests: seats per depth and field, the artisan seat silent, the reading share and the deep
  reserve (`tests/planner/test_seat_share.py`), the panel builder (an unquoted, unknown or
  unsupported take sentence drops its view, a pair on one source or two subjects is refused,
  agreement from a shared claim, a spend refusal adds nothing; `tests/experts/`), the stream seam
  (`tests/experts/test_expert_flow.py`), the headroom (`tests/test_budget.py`, and on GitHub
  Actions `tests/db/test_spend_rules_db.py`).
- Items left are in `docs/TECH_DEBT.md` under this decision.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
