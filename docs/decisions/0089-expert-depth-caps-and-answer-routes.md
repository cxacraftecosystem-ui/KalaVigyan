# 0089. Expert answers research and write more, compose on Opus at high effort, and cost more; Hindi terms survive translation

Expert answers research more queries and documents, write more sentences per section and compose on
Opus at high effort, with routes tuned per depth and higher answer caps. A Hindi answer keeps its
term spans through translation, so its quiz has sentences to ask.

Date: 2026-11-18. Status: accepted. Item 3's output tokens and item 4's caps are superseded by
decision 0093 (no caps for now; every call asks for its model's documented maximum).

| For | Read |
|---|---|
| What superseded part of it | [0093 No caps for now: every AI cap defaults to none, and every call asks for its model's documented maximum output](0093-no-caps-for-now.md): item 3's output tokens and item 4's caps |
| A Hindi answer keeps its quiz on its terms' Hindi names | [decision 0167](0167-answer-leftovers-kept-true.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked an Expert question about Kutch Ajrakh and found the answer bland and short. Every
limit on an answer's breadth was set for the first phase A answers: an Expert answer had 8 web
queries and 20 documents for the whole answer, shared by every section (under one query per
section for a seven-section answer), 20 stored claims per section's evidence pack, at most 8
sentences per section whatever the depth, the compose route's output cap (the route's
`maxOutputTokens`, else 4096 tokens), the `COMPOSE` route's default effort `medium` (decision
0052), the same `COMPOSE` route (Opus 5.5 first in production) for every add-on builder, and caps
of $0.50 per Detailed and $1.00 per Expert answer. The owner set on 2026-11-18: $1.00 per Detailed
answer and $2.50 per Expert answer (Master Admins stay uncapped), the main compose on Opus 5.5 at
high effort for Expert, add-on builders on Sonnet 5.5, and a higher output cap for the
explainer draft.

## Decision

1. **Depth policy** (`research/depth.DEPTH_POLICIES`) gains `section_sentences` and
   `stored_claims`. Expert: 24 queries and 48 documents per answer (was 8 and 20), 16 sentences per
   section (was 8), 40 stored claims per section's pack (was 20). Basic and Detailed keep their
   budgets, 8 sentences and 20 stored claims. The `DEEP` mode, which bounds Expert, allows 24
   queries, 6 native-language queries and 48 fetches (was 8, 3 and 20);
   `DEEP_REFERENCE_RESERVE` is 15 of 48 (was 6 of 20), so references keep the same part of a share.
2. **Section composition** takes its limit from the depth: `ComposeFocus.sentencesMax` (default 8,
   at most 24) sets both the prompt's "at most" and the parse limit, through
   `composer.prompt.section_system_prompt(sentences_max)`. Above the default the prompt adds
   `EXPERT_SECTION_RULES`: a full explainer, each mechanism step by step with its conditions and
   products, every stage with its materials, every date, place and person the sources name, both
   readings where sources differ. Every sentence keeps every check.
3. **Routes per depth** (`providers/answer_routes.py`, `services/answer_models.AnswerModels`). The
   router takes a `RouteTuning {models by provider, effort, maxOutputTokens}` per call: a tuned
   route keeps its provider, key and order, swaps its model when the tuning names one for its
   provider, sets the reasoning effort, and raises (never lowers) the output cap.
   - Main compose (sections, lede, regeneration): Expert on `claude-opus-5-5` at `high`, 16000
     output tokens; Detailed 8192 tokens; Basic 4096; both keep the route's model and effort.
   - Add-on builders (material cards, expert panel, what-if, region story and the other model
     calls of `BuilderTools.compose_model` and `plan_model`): `claude-sonnet-5-5` on the Anthropic
     route, within the answer's optional headroom.
   - The generated explainer (`BuilderTools.explainer_model`): Expert on `claude-opus-5-5` at
     `high` with 18000 output tokens (three concurrent drafts then fit in the $1.25 optional headroom of an Expert cap), Detailed and Basic on `claude-sonnet-5-5` with 16000.
   `build_answer_pipeline(models=...)` replaces its six model arguments; the answer route and the
   nightly piece rebuild both call `answer_models(depth, principal=, optional=)`.
4. **Caps**: the defaults of `AI_ANSWER_CAP_USD` are Basic $0.25, Detailed $1.00, Expert $2.50.
5. **Hindi quiz** (E2E run 44301935063): translation kept a term span only where its English
   spelling survived, so a Hindi answer (saaj, kut, gach written साज, कुट, गच) kept no span and the
   quiz, which needs termed sentences, had nothing to ask, and its route answered 404. Each
   distinct span text is now translated with its sentences and the span follows the term's own
   rendering when the translation shows it. An explainer that still yields no question answers
   204 with no body, as `/compare` does for nothing to compare; 404 stays for an answer that is not
   the asker's or holds no explainer.

## Consequences

- A stored `AI_ANSWER_CAP_USD` row overrides the defaults. If production holds one, the owner (or
  a Master Admin) sets Detailed to 1.00 and Expert to 2.50 in Settings, AI budget, or with
  `PUT /settings/ai-budget`; no migration writes it.
- An Expert answer reserves more per call: an Opus section call holds about $0.32 of output
  (16000 tokens at $20 per million) plus its input while it runs, and four sections compose at
  once. An Admin's Expert answer on many fields can reach the $2.50 cap and then stops with "This
  answer reached the cost limit for its depth." Master Admins are never capped. The cost of real
  Expert answers is to be measured on the first production asks and the caps or `SECTION_CONCURRENCY`
  revisited.
- Opus at high effort thinks longer: Expert sections take longer to arrive. The 60-second
  heartbeat keeps the stream open.
- Builders no longer ride the Opus compose route, so their spend falls.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. The parts later records changed stay
here as they were decided; the later record is the one that holds. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
