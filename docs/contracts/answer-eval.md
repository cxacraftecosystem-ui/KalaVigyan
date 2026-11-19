# Answer quality: seats by field and the evaluation

How the ask agent covers every field a question touches, and how that is measured (round 5, lane
fields-and-ask; `kalavigyan-craft-pages` checklist rule 23: an answer page draws on every field its
question touches, through one expert seat per field, and its provenance names the fields it
consulted).

## Seats by field

- The understanding step (`planner/understanding.ModelUnderstander`) reads the fields the question
  touches (`disciplines`) and the seats the model chose. With a craft chosen it also reads the fields
  the craft holds cited claims in (`held`, `services/coverage.held_field_lookup`, the coverage count
  of `coverage.md`). The **relevant fields** are the asked fields the craft holds claims in, or every
  asked field when no craft is chosen or the lookup fails (`coverage_seats.relevant_fields`).
- The seats keep the model's choice, in its order, and add for each relevant field no chosen seat
  speaks for the seat that leads it (`FIELD_LEADS`: the seat that lists the field first, the panel's
  order breaking ties; the artisan's voice speaks for no field), up to the depth's seat limit
  (`depth_policy(depth).max_experts`: 2 Basic, 4 Detailed) (`coverage_seats.covering_seats`,
  `understanding.understood_seats`). Expert depth keeps the model's seats: its panel already widens
  to every seat of each section's field (`expert_panel.panel_seats`).
- Each seat searches stored knowledge with its own fields as the retrieval field filter
  (`services/seat_search.seat_query`, `KnowledgeQuery.fields`).
- An answer that leaves a relevant field with stored claims without a speaking seat is a defect;
  `tests/planner/test_field_seats.py` catches it.
- **Provenance**: the MCP `ask` result names the fields it consulted (`AskedAnswer.fields`,
  `ConsultedField {field, sections, sentences, sources, figures, seats[]}`, from the ready sections
  of the stored explainer, `research/coverage_answers.consulted_fields`).

## The evaluation

`python -m app.scripts.eval_answers [--only <id> ...] [--limit N] [--cap USD]` asks each question of
`backend/app/data/eval/answer_questions.json` (`EvalQuestions {schemaVersion 1, questions[{id,
question, craftSlug, depth (DETAILED), fields[]}]}`: 24 questions across all 16 fields and ten
curated crafts; the plans list no minister showcase questions yet, so none are marked) through the
same answer pipeline as the site, as the system (no person's account), each under its own request
id (`answer-eval-<run>-q<NNN>`), then scores the stored explainer.

**The rubric** (`research/coverage_eval.py`), each part 0 to 1, the score their mean:

| Part | Measured |
|---|---|
| fields | the share of the question's fields the answer consulted (a ready section in the field) |
| cited | per question field, cited sentences over 3 (at most 1), averaged over the question's fields |
| everyCited | 1 when every sentence's citations name sources the answer lists |
| figures | 1 when the answer shows a figure (any block that is not text) |
| noGaps | 1 when no sentence admits a gap (`GAP_ADMISSION`: no source or evidence, not enough evidence, could not find, not known or documented, little is known, sources do not say, we do not know) |

**The judge** (the existing `EVAL_JUDGE` route, `router_structured_model(AiTask.EVAL_JUDGE)`) scores
the same five parts 0 to 5 with a note, reading the question and the answer's sentences by field as
untrusted data (`JUDGE_SYSTEM_PROMPT`, `judge_message`, `judge_schema`); its share is the sum over 25.
A judge that fails leaves the measures and says so.

**Spend.** The run stops before a question when the spend so far (`router.tagged_spend` on the run's
request id prefix) leaves less than `EVAL_QUESTION_RESERVE_USD` (2.50) of the cap. The cap is
`services/coverage_eval.EVAL_SPEND_CAP_USD` (30.00 US dollars); `--cap` may lower it, never raise
it. Each answer has the MCP ask's limit, `ASK_TIMEOUT_SECONDS` (600).

**The report** is printed as one JSON line: `EvalReport {schemaVersion 1, startedAt, capUsd,
spentUsd, stopped, asked, answered, rubricMean, judgeMean, questions[{id, craftSlug, depth,
answerId, problem, measures {expected, consulted, missed, sentences, unresolved, figures, gaps,
fields[]}, rubric, judge, judgeShare, spentUsd}]}`. A question whose answer fails is kept with its
problem and the run goes on. The exit status is 0 when at least one question was scored.

**The workflow** `.github/workflows/answer-quality.yml` (dispatched by hand, inputs `limit`, `only`,
`cap`, each checked) runs the script on the box over SSM as the other upkeep workflows do, keeps
`report.json` (the report) and `stdout.txt` as the `answer-quality-<run id>` artifact for 90 days,
and writes the asked, answered, means and spend into the run summary.
