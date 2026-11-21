# 0052. Opus 5.5 composes answers, at medium effort

Opus 5.5 composes answers first on the `COMPOSE` route at medium reasoning effort, which the router
passes on every chat call and only always-thinking Anthropic models act on. Each route keeps its
parameters across a reorder, and the effort can be lowered without a deploy.

Date: 2026-11-18. Status: accepted.

| For | Read |
|---|---|
| Every decision, by group | [README.md](README.md) |

## Context

The owner asked on 2026-11-17 for the serving model to move from Sonnet 5.5 to Opus 5.5 if it
answers better. Opus 5.5 was put first on the `COMPOSE` route in production (Sonnet second, then
Gemini 3.8 Flash and GPT-6.1 Terra) and a test call passed. Opus 5.5 always thinks. The router
never set an effort, so `AnthropicAdapter` asked it for `low`, the least reasoning it can do,
which spends the stronger model on the cheapest setting. `RoutePolicy.params` existed but nothing
read it, and saving a new order in Settings recreated every route without it.

## Decision

1. The router passes a reasoning effort on every chat call: the route's own
   `RoutePolicy.params.reasoningEffort` when it is one of `low`, `medium`, `high`, `xhigh` or
   `max`, else the task's default. `COMPOSE` defaults to `medium`; every other task keeps the
   provider's default.
2. Only always-thinking Anthropic models act on it. Sonnet 5.5 keeps thinking off for composing,
   and OpenAI-compatible routes use it only when a caller asks for reasoning, which none does.
3. `route_policy.save_order` keeps each route's `params` by provider and model across a reorder.
4. The effort can be lowered without a deploy: set `{"reasoningEffort": "low"}` on the Opus
   `COMPOSE` row.

## Consequences

- Opus answers think more, so each section takes longer and spends more output tokens. The
  per-answer caps still hold, and an answer that runs out of headroom degrades to the next route.
  The production E2E's known-answer questions are the check that sections still finish within
  the stream's limits.
- The paid nightly enrichment stays off (commit fdf478c); the dataset is curated by Claude Code
  (`docs/plans/dataset-curation.md`, decision 0051). Live answers are serving and keep using the
  routes above.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
