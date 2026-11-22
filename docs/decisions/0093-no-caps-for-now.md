# 0093. No caps for now: every AI cap defaults to none, and every call asks for its model's documented maximum output

Every AI cap defaults to none and every model call asks for its model's documented maximum output,
on the owner's word of 2026-11-18. Unlimited is a default value, not deleted code, so a cap can come
back as a stored setting.

Date: 2026-11-18. Status: accepted. Supersedes the cap values of decisions 0031, 0046 and 0089
(item 3's output tokens and item 4's caps) and the daily allowances of PLAN section 12; their
code paths stand.

| For | Read |
|---|---|
| What it supersedes in part | [0031 Understanding the question, and depth by role](0031-understanding-and-depth.md): its cap values; the code paths stand |
| What it supersedes in part | [0046 The expert panel](0046-expert-panel.md): its cap values; the code paths stand |
| What it supersedes in part | [0089 Expert answers research and write more, compose on Opus at high effort, and cost more; Hindi terms survive translation](0089-expert-depth-caps-and-answer-routes.md): item 3's output tokens and item 4's caps |
| What it supersedes in part | the daily allowances of [PLAN.md](../PLAN.md), section 12; their code paths stand |
| Daily allowances become a setting with a screen | [decision 0146](0146-answers-recorded-and-bounded-on-the-box.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The owner wrote on 2026-11-18: "no caps for now on anyone, not in terms of money or tokens".

Until then a request could be refused, degraded or cut short for money, quota or tokens in these
places:

| Where | What it did | Value before |
|---|---|---|
| `AI_ANSWER_CAP_USD` (`providers/budget.AnswerSpend`, `AnswerHeadroom`) | refused an answer's next call past its depth's cap; optional builders only within the first half | Basic $0.25, Detailed $1.00, Expert $2.50; Master Admin none |
| `AI_ROLE_DAILY_USD` | refused a user's call past the role's daily spend | Student $0.50, Researcher $3, Professor $5, Admin $10; Artisan and Master Admin none |
| `AI_MONTHLY_CEILING_USD` | refused every paid call past the month's spend | $800 |
| `AI_MEDIA_CAP_USD` | refused image, video, music and sound calls past the month's media spend | $150 |
| `AI_DEGRADE_AT_FRACTION` | past this share of the ceiling: cheapest route first, Deep research became Hybrid, Expert became Detailed | 0.8 |
| `core/roles.DAILY_ALLOWANCES` (and the unread `QuotaPolicy` rows) | refused voice calls and turns, Listen holds and media jobs past the day's units | Student 600 s, 5 images, 0 videos; Researcher 1800 s, 30, 5; Professor 1800 s, 50, 10; Admin 3600 s, 100, 20 |
| `providers/answer_routes` tunings | output tokens of compose and the generated explainer | compose Basic 4096, Detailed 8192, Expert 16000; explainer 16000, Expert 18000 |
| `RoutePolicy.maxOutputTokens`, else `router.DEFAULT_MAX_OUTPUT_TOKENS` | output tokens of every other call (plan, builders, translation, term summaries, voice turns, interview, testimony) | 4096; `TRANSLATE` rows 8192, `SUMMARISE` rows 2048 |

## Decision

1. **Unlimited is the default value, not deleted code.** Every money cap in
   `services/app_settings.DEFAULTS` is `None`: no monthly ceiling, no media cap, no daily cap for
   any role, no answer cap at any depth, no degrade mark. `providers/budget` reads `None` as "no
   cap" (`cap_usd`, `over`, `Ceilings.role_cap`), `month_fraction` is `None` without a ceiling,
   and nothing degrades without both a ceiling and a mark (`past_degrade_mark`). A cap set again
   in the AI budget is enforced by the same code; a depth missing from a stored answer-cap row
   still has nothing to spend (fail closed). Master Admins stay uncapped whatever is set.
2. **The AI budget can say "no cap".** `PUT /settings/ai-budget` keeps the fields the body sent
   (`app_settings.sent_budget_fields`): an explicit `null` lifts the monthly ceiling, the media
   cap or the degrade mark, and `answerCapUsd` takes `null` per depth. `roleDailyUsd` and
   `answerCapUsd` merge into the stored map, so a body that names only `STUDENT` caps Students and
   leaves every other role as it was (`Ceilings.role_cap` would otherwise give a role missing from
   the map the Student cap). A media cap is checked against the ceiling only when both are set.
3. **No daily allowances.** `core/roles.DAILY_ALLOWANCES` maps every role to `None` for
   `VOICE_SECONDS`, `IMAGE` and `VIDEO` (`ALLOWANCE_RESOURCES`). Voice availability, calls,
   relay turns, Listen holds and media jobs already read `None` as unlimited (Artisans had it), so
   none of them refuses for time or units, `remainingSeconds` and `remainingToday` are `null`, and
   the seconds and units are still written to `QuotaLedger`. The voice notice no longer speaks of
   daily voice minutes ("We record how long each call lasts."), so it moves to version
   `2026-11-18` (`voice/notice.VOICE_NOTICE_VERSION`) and each user accepts it again before the
   next call.
4. **Every call asks for its model's documented maximum.** `AiModel.max_output_tokens` records
   the documented maximum, and `router.output_tokens_for(choice, requested)` asks for the caller's
   `max_tokens`, else the route's `maxOutputTokens`, else the model's maximum, else
   `DEFAULT_MAX_OUTPUT_TOKENS` (4096) for a model without one, and never more than the maximum.
   Every chat model in the catalogue has a maximum, and the router never sends a call to a model
   outside it (`route_allowed` needs `supports`), so no routed text call falls to 4096.
   The answer tunings set no output cap. So compose, the lede and regeneration, the explainer
   draft and the generated explainer, the add-on builders, translation, term summaries, voice
   turns, interview and testimony all ask for the maximum of the model that serves them. The
   maxima, checked on 2026-11-18:

   | Models | Maximum output | Source |
   |---|---|---|
   | `claude-opus-5-5`, `claude-opus-5`, `claude-sonnet-5-5`, `claude-sonnet-5`, `claude-haiku-5-5` | 128,000 (128K, the synchronous Messages API limit) | https://platform.claude.com/docs/en/about-claude/models/overview, https://platform.claude.com/docs/en/models/sonnet-5-5/overview, https://platform.claude.com/docs/en/build-with-claude/context-windows |
   | `gemini-3.8-flash` | 65,536 | https://aistudio.google.com/docs/models/gemini-3.8-flash |
   | `gemini-3.7-flash` (deprecated, routed to 3.8 Flash) | 65,536 | https://aistudio.google.com/docs/models/gemini-3.7-flash |
   | `gemini-3.5-flash-lite` | 65,536 | https://aistudio.google.com/docs/models/gemini-3.5-flash-lite |
   | `gemini-3.1-pro-preview` | 65,536 | https://aistudio.google.com/docs/models/gemini-3.1-pro-preview |
   | `gemini-4-argon` | 65,536 synchronous (1,048,576 only with long decode, which the adapter does not use) | https://aistudio.google.com/docs/models/gemini-4-argon |
   | `gemini-3.8-flash-tts` | 16,384 (Gemini API serving limit) | https://aistudio.google.com/docs/models/gemini-3.8-flash-tts |
   | `gpt-6-luna` | 128,000 | https://developers.openai.com/api/docs/models/gpt-6-luna |
   | `gpt-6.1-terra` | 128,000 | https://developers.openai.com/api/docs/models/gpt-6.1-terra |
   | `gpt-5.6-terra` | 128,000 | https://developers.openai.com/api/docs/models/gpt-5.6-terra |
   | `gpt-5.6-sol` | 128,000 | https://developers.openai.com/api/docs/models/gpt-5.6-sol |
   | `deepseek-flash`, `deepseek-v4-pro` | 384,000 (the page writes "384K"; the decimal reading is the lower of the two, so a request never passes the limit) | https://api-docs.deepseek.com/quick_start/pricing |

   Anthropic calls stream (`messages.stream`), so 128,000 needs no non-streaming timeout. No
   route asks for fewer tokens than before: the OpenAI fallback that served translation at 8192
   and compose and the explainer at up to 18000 now asks for 128,000, and every model a route can
   use has a maximum of at least 16,384, above every earlier limit of its task.
5. **Production rows** change once, in migration `0029_unlimited_ai_use`: the five cap rows of
   `AppSetting` are deleted (the defaults then govern), `QuotaPolicy.perDay` and `perMonth` become
   NULL, and `RoutePolicy.maxOutputTokens` becomes NULL (a routable row then asks for its model's
   maximum, which is above the 8192 or 2048 it held, so no row loses tokens). A migration and not a deploy step because
   a step run on every deploy would wipe caps the owner sets again later. Deleting the rows rather
   than writing JSON nulls keeps the old colour working while the deploy migrates: an earlier
   release reads a missing row as its own capped defaults, but would fail on a null. Every
   statement converges, so a second run changes nothing. `docs/RUNBOOK.md` lists the rows and the
   way back.
6. **Settings and Usage read without caps.** `/settings/ai-budget` answers `null` for each cap;
   `/usage/summary` answers `monthlyCeilingUsd`, `mediaCapUsd` and `fraction` `null` and
   `degraded` false; `/usage/report` answers `ceilingUsd` `null`; `/usage/me` answers
   `dailyCapUsd` and each allowance `null`. The Usage page then shows the month's spend as "This
   month" with "No monthly ceiling", no share and no bar; with a ceiling set it shows the share as
   before. Spend is still shown everywhere.

## What is not a cap and stays

- Press limits against abuse, which count presses and not money or tokens: 30 asks, 60 term
  lookups, 30 Listen presses and 10 film-score asks per user in 10 minutes, the voice session and
  turn limits (Master Admins skip the first four, decision 0038).
- The shape of one call or job: a voice call's longest length (`MAX_SESSION_SECONDS`) and turns,
  the upload size, three open media jobs per user, the live voice sessions at once, and research
  breadth by depth (queries, documents, sentences, stored claims; decision 0089).
- The coverage enrichment's own daily budget (`ENRICHMENT_DAILY_BUDGET_USD`, $2.50, and
  `ENRICHMENT_JOB_MAX_USD`): it paces a scheduled job that no person asks for, and production no
  longer runs it (`docs/RUNBOOK.md`, Coverage enrichment). It needs the owner's word to lift.

## Consequences

- Nothing stops spend. The owner watches `/admin/usage`; a cap returns through the AI budget, AI
  routing or `DAILY_ALLOWANCES`, and the deploy never resets them.
- A reservation now estimates a call at its model's maximum output (an Opus call at 128,000
  tokens holds about $2.56 of output while it runs, and a DeepSeek call at 384,000 tokens at the
  unknown-price rate about $11.52); with no caps the estimate refuses nothing and the settled cost
  replaces it.
- Calls that ran out of output tokens (Expert sections at high effort, translations of long
  answers) can now finish; replies are as long as the model writes, so latency and cost follow
  the answer, not a limit.
- The answer-cap and allowance tests run against "caps an owner might set" fixtures
  (`tests/test_budget.py`, `tests/conftest.allowances_an_owner_might_set`), and new tests show
  that no role or depth is refused, degraded or cut short by default, that spend is still
  recorded, that each route asks for the documented maximum, and that the data step converges.

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-18; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
