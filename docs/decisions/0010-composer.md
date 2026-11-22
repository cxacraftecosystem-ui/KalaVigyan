# 0010. Composer

A new `app/composer/` layer writes answers from candidates in the evidence pack: the model quotes,
the server cites, and stricter post-checks retry or drop any sentence the evidence does not support.
When the evidence is not enough the answer says so, and the question and every passage reach the
model inside untrusted blocks.

Date: 2026-11-16. Status: accepted.

| For | Read |
|---|---|
| The contract it was built to | [0002 One contract package for research and answering](0002-research-and-answering-contracts.md) |
| A claim's sources in its candidate, the searchers asked, and a refused sentence rewritten once | [decision 0138](0138-answers-composed-from-the-asked-fields.md) |
| Stored passages offered as evidence in their own words | [decision 0144](0144-stored-passages-as-evidence.md) |
| Every decision, by group | [README.md](README.md) |

## Context

PLAN section 3.1 step 7 and section 0 ask for answers whose every sentence is cited, with the
quoted passage and a link out, and whose numbers and formulas all come from a cited source. The
contract (`research/composition.py`, decision 0002) had the request, the output and the
per-sentence checks, but no composer, no rule that a sentence must quote its source, nothing
that turns an `EvidencePack` into candidates, and no answer for "nothing survived".

## Decision

1. **A new layer, `app/composer/`** (`composer -> research, core, models`). It depends on the
   `StructuredModel` protocol only; `ModelComposer(model=router_structured_model(AiTask.COMPOSE,
   principal))` joins it to the AI router, so the `COMPOSE` routes of the Settings hub apply:
   Claude Sonnet first, Gemini next. A route whose key is missing fails `auth`, a kind that moves
   the router to the next route, so Gemini answers when there is no Anthropic key. Past the
   degrade threshold the router puts the cheapest route first, as for every degradable task.
2. **Candidates from the pack** (`composer/candidates.compose_request(pack, question)`):
   - every stored claim hit (`CLAIM`, its stored level, the claim text);
   - every read document (`EVIDENCE`, level `PROVISIONAL` = `LABEL_LEVELS["QUOTED"]`, the level
     a quoted write-back gets). A document of at most `WHOLE_TEXT_MAX_CHARS` (4,000) characters,
     which covers abstracts and record excerpts, is offered whole; a longer one offers its
     item's quotes, which the document already proved verbatim. A long document without quotes
     is left out until the reader (`WEB_READ`) takes quotes from it: picking passages is the
     reader's job, and a second passage picker here would be a duplicate.
   - Evidence that was found but not read is left out: there is no stored text to check a
     quote against. Stored passages (T2 chunks) are not candidates yet (debt register).
   `ComposeCandidate` now lets an `EVIDENCE` candidate carry several verbatim passages (`text`
   and `quotes`); the old rule "one quote, no quotes list" is dropped.
3. **The model quotes, the server cites.** The reply gives each sentence its text and quotes
   (`{source, quote}`); the cited ids are the quotes' sources, split into claim ids and
   evidence ids by the candidate's kind. So a citation always comes with a quote.
4. **Stricter post-checks** (`sentence_violations`):
   - `UNQUOTED`: a sentence with no quoted span fails. Every sentence must quote at least one
     passage that exists in a cited candidate's stored text.
   - A number or formula must appear in one of the sentence's own quoted spans that passed the
     source check, not merely somewhere in a cited source. A whole abstract would otherwise
     license any figure it contains.
5. **Retry and drop.** At most `COMPOSE_RETRIES` (1) extra call per answer. An unusable reply
   (not a JSON object, a missing list, a heading that is empty, too long, or carries a number,
   a link, markup or personal data) is asked again once, then raised as `ExternalFailure`. When
   the reply is usable, its failing sentences (including ones that do not construct) are sent
   back once with their problems, each inside an `untrusted_block` because it is model output;
   a replacement takes the failing sentence's place, an omitted or still-failing one is
   dropped, and a regenerate reply that is unusable drops them all. Follow-ups carrying a link,
   markup or personal data are dropped: they are suggestions, not answer text.
6. **Levels.** A sentence's level is computed by `sentence_level` from its cited candidates;
   hypothesis-level sentences go to `openQuestions`. Sections left empty are dropped.
7. **Not enough evidence.** `ComposeRequest.searched` carries a `ResearchSummary` built from
   the pack (stored claims and passages, the live queries by tier, the services that answered
   or failed, items found, documents read, failures). When no candidate exists the model is not
   called; when nothing survives the checks the answer is `ComposedAnswer(notEnoughEvidence=
   summary)`. `ComposedAnswer` now holds cited sentences or that summary, never both and never
   neither. `not_enough_evidence_message(summary)` is the one user-facing sentence that lists
   what was searched. `services` names only searchers that returned evidence or failed: the
   pack does not record a searcher that returned nothing.
8. **Untrusted text.** The system prompt holds only the rules. The learner's question, every
   candidate passage and every failed sentence go into the user message inside
   `untrusted_block`, one block per passage with the candidate id as `ref`. The mechanical
   checks are the guard: whatever a source makes the model write, it is shown only if it quotes
   an allowed source verbatim and every figure is in that quote. The checks prove support, not
   truth: a source that states a falsehood can still be quoted (the trust tier and level labels
   stay on the citation).
9. **One home for the JSON schema object helper.** `research/structured.schema_object` replaces
   the private `_object` copies in the planner and the composer.

## Consequences

- The answering service builds `compose_request(pack, question)`, calls the composer, and sends
  either the sections and open questions or `not_enough_evidence_message`.
- Quoted spans become `Quote`s for write-back; their 300-character limit matches.
- Number words and units without digits are still not checked (debt register).

## How this record is kept true

It is not edited after acceptance except to mark it superseded: a later choice is a new record that
names this one, and the table above links the two both ways. It records the choice as taken on
2026-11-16; what the code does today is in [ARCHITECTURE.md](../ARCHITECTURE.md) and the
[contracts](../contracts/README.md).
