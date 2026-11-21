# 0038. Phase A review fixes

Phase A's review fixed what broke an owner rule or a plan decision: Master Admins are never
throttled, a failed craft lookup never blocks, modes stay internal and answers write no process
rows. No adapter drops a schema, the trail's limits have one home, and the documents say what the
code does.

Date: 2026-11-17. Status: accepted.

| For | Read |
|---|---|
| The lanes it reviewed | [0030](0030-explainer-contract.md), [0031](0031-understanding-and-depth.md), [0032](0032-sectioned-composition.md), [0033](0033-knowledge-pieces-and-reuse.md), [0034](0034-images-and-terms.md), [0035](0035-listen-and-voice-switched-off.md), [0036](0036-asking-screen.md) and [0037](0037-explainer-ui.md) |
| The contracts it names | [research.md](../contracts/research.md), [backend.md](../contracts/backend.md), [voice.md](../contracts/voice.md) |
| Every decision, by group | [README.md](README.md) |

## Context

The review of phase A of `docs/plans/answer-experience.md` (lanes 0030 to 0037) found places where
the code or the documents broke an owner rule or a plan decision: Master Admins were still
throttled when asking; a failed craft lookup stopped the answer and told the reader to name a
craft; reader-facing notes named internal modes; the OpenAI-compatible adapter still fell back to
free text when a format was refused (finding 8a.1); an answer could write a craft's process with
step numbers ordered by the model; two lengths and two prefixes of the trail had two homes; the
site-wide CSP let pictures load from any https site with no feature using it; the production audit
flagged KaTeX's hidden MathML copy (finding 8a.4); the phone Process tab hang (8a.3) had no record;
and several documents described behaviour that had changed.

## Decision

1. **Master Admins are never throttled.** `POST /answers/stream` skips `ask_attempt` when
   `core/roles.is_uncapped(user)`, as the term and Listen routes do; the term route now calls
   `is_uncapped` instead of reading `UNCAPPED_ROLES` itself. The limit stays 30 asks in 10 minutes
   for every other role.
2. **A failed craft lookup never blocks.** `ModelUnderstander` catches an `AppError` from the
   resolver. A spend refusal is raised again (its words are the answer's `error`), and so is a
   failure while looking up a slug the reader chose. Any other failure is logged and the question
   proceeds with no resolver candidates: the model's reply and the crafts it names decide, through
   the same resolver, and nothing found is any craft. `RESOLVER_FAILED_DETAIL` now reads "Finding
   the craft failed just now. Try again." and is shown only for a chosen craft.
   The review also asked to skip the resolver when the reader chose Any craft. That is not done:
   decision 0031 (point 2) and `docs/contracts/research.md` keep the detected crafts as offers for
   an any-craft ask, so the reader can switch back with one tap, and with failures caught the
   resolver can no longer block that ask.
3. **Modes stay internal.** A section's searched note says "No live research ran." without the
   mode, and `RESEARCH_FAILED_DETAIL` reads "Research failed just now. Try again." (the ask screen
   has had no mode choice since decision 0036).
4. **No adapter drops a schema.** `providers/base.format_refused(service, model)` is the one home
   of the refused-format failure (kind `error`, logged, so the router moves to the next route),
   with `names_the_format(message, needles)`; the Anthropic and Gemini adapters use it, and the
   OpenAI-compatible adapter now does too. Its `response_format` is always sent when a schema is
   asked for (`json_schema` for OpenAI itself, `json_object` for DeepSeek and the other
   compatible services), a refusal naming `json_schema`, `response_format` or `json_object` is
   that failure, and those words are no longer parameters to unlearn; a reject learned before is
   ignored.
5. **Answers write no process rows.** `SqlPieceStore.keep` no longer turns a `PROCESS` section's
   cited `PROCESS_STAGE` concepts into a "Live research process"; `services/piece_stages` is
   deleted. The order and the step numbers came from the order of the model's sentences, and the
   concept names from the planner's facet targets, so once stored they would have looked sourced
   to every later ladder and to the Process tab. The reason decision 0033 gave for not placing a
   new stage in an existing process applies to the whole order of a new one. Item 9 of decision
   0033 is withdrawn; the cited-order route is debt.
6. **One home for the trail's limits.** `research/explainer.py` defines `STORED_SOURCE_PREFIX`,
   `PIECE_PREFIX`, `STORED_TRAIL_PREFIXES`, `TRAIL_TITLE_MAX_CHARS` and
   `TRAIL_PUBLISHER_MAX_CHARS`; `TrailEvent` and `services/answer_trail` both read them.
7. **No site-wide https pictures.** `img-src` is again the app, `data:` and the media bucket on
   every page. The stream sends no `images` block yet, so the widening served nothing and handed
   any future injection an image-beacon channel to any host. Decision 0039, which wires step 7,
   puts `https:` back on every page, because a client-side move to `/ask` keeps the first page's
   policy; until then `ImageStrip` hides a picture that does not load.
8. **The audit skips KaTeX's MathML copy, and only it.** `e2e/production/pageAudit.auditPage`
   ignores text inside `.katex-mathml`, for overflow and for collected copy. It runs in a browser,
   so its spec (`e2e/page-audit-unit.spec.ts`, a real KaTeX fragment at phone width) is the first
   unit spec that needs one, and the Frontend checks job installs Chromium before the unit specs.
   The spec's oracle is the same page with the MathML copy removed, plus a narrow paragraph whose
   class only resembles KaTeX's that must still be flagged.
9. **The phone Process tab hang is recorded, not guessed at.** Finding 8a.3 could not be
   reproduced without the deployed site, so no code was changed for it; the debt entry says how to
   find it.
10. **The documents say what the code does.** The `/answers/stream` row of
    `docs/contracts/backend.md` lists the explainer events and the Master Admin exception; decision
    0032 says only step 7 is uncalled; decision 0035 and `docs/contracts/voice.md` say that turning
    the call on brings back the craft page's Talk dock only, since the mic on `/ask` is dictation
    (decision 0036). The ask screen's call entry is not put back.

## Consequences

- A resolver outage now costs answer quality (no candidates offered, the model's names resolved
  only if the resolver recovers) instead of the answer.
- An OpenAI or DeepSeek route that cannot do structured output now fails over to the next route on
  every structured call, as Anthropic and Gemini do.
- The craft page's Process tab shows only curated or seeded processes until a source-stated order
  exists.
- Frontend checks take the time of a Chromium install more.
- Items left are in `docs/TECH_DEBT.md`: "Answers never grow the Process tab", the `/ask` picture
  policy (cleared by decision 0039), "Retired stream vocabulary still listed" and "Craft Process
  tab on phones hangs (finding 8a.3)".

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-17; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
