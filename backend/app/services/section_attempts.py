from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.composer.candidates import ClaimSupport, compose_request
from app.research.composition import ComposedAnswer, ComposeFocus, ComposeRequest
from app.research.depth import section_sentence_limit
from app.research.evidence_pack import EvidencePack
from app.research.explainer import Block
from app.research.planning import PlanRequest, ResearchShare
from app.research.sections import DISCIPLINE_TITLES, LADDER_DISCIPLINE, SectionSpec, block_id, named_stage_ids
from app.science.ladder import ladder_problems, ladder_stage_options, process_ladder

from .answer_catalogue import SectionCatalogue
from .answer_events import CitedClaims, joined_claims
from .off_question import screened_request
from .section_blocks import BlockRefused, SectionSentences, cited_sentence, kept_sentences, prose_block
from .section_context import ClaimsOf, SectionContext
from .section_deepening import LADDER_KIND
from .section_rewrite import Written, rewritten
from .section_trail import stored_sources

__all__ = ["Attempt", "attempt"]

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Attempt:
    pack: EvidencePack
    composed: ComposedAnswer
    blocks: tuple[Block, ...]
    open_questions: tuple[dict[str, Any], ...]
    cited: CitedClaims
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[uuid.UUID, ...] = field(default=())
    floored: tuple[Block, ...] = ()


@dataclass(frozen=True)
class _Researched:
    pack: EvidencePack
    stored: CitedClaims


@dataclass(frozen=True)
class _Drafted:
    pack: EvidencePack
    composed: ComposedAnswer
    written: Written
    offered: SectionCatalogue


async def attempt(
    spec: SectionSpec, context: SectionContext, share: ResearchShare, *, fresh: bool
) -> Attempt:
    found = await _researched(spec, context, share, fresh=fresh)
    await context.stream.section_state(spec.id, "WRITING")
    offered = await context.tools.catalogue(context.base, spec.discipline)
    request = _request(spec, context, found, offered)
    if request.candidates:
        await context.stream.status("COMPOSING", len(request.candidates))
    composed = await context.tools.compose(request)
    await context.stream.section_state(spec.id, "CHECKING")
    claims_of = await _kept(context, found.pack, composed)
    cited = await context.tools.store.cited(claim for claims in claims_of for claim in claims)
    sentences = context.deepening_of(spec.id).unshown(kept_sentences(composed, claims_of))
    written = await rewritten(spec, context, request, sentences, cited)
    return _built(spec, context, _Drafted(found.pack, composed, written, offered))


async def _researched(
    spec: SectionSpec, context: SectionContext, share: ResearchShare, *, fresh: bool
) -> _Researched:
    request = PlanRequest.model_validate(
        context.base.model_dump() | {"focus": spec.discipline, "share": share.model_dump(), "fresh": fresh}
    )

    async def progress(step: Any, count: int) -> None:
        await context.stream.status(step, count)

    pack = await context.tools.research(request, progress, context.stream.trail, reads=context.reads)
    context.ledger.settle(share, pack)
    stored = await context.tools.store.cited(hit.claim_id for hit in pack.stored.claims)
    await context.stream.trail.found_stored(stored_sources(pack, stored))
    return _Researched(pack, stored)


def _request(
    spec: SectionSpec, context: SectionContext, found: _Researched, offered: SectionCatalogue
) -> ComposeRequest:
    request = compose_request(
        found.pack,
        context.base.question,
        focus=_focus(spec, context, offered),
        style=context.reading_style,
        support=claim_support(found.stored),
    )
    return screened_request(request, context.names, comparison=bool(context.base.compared))


def claim_support(cited: CitedClaims) -> dict[uuid.UUID, ClaimSupport]:
    return {
        claim_id: ClaimSupport(
            quotes=tuple(citation["quote"] for citation in view.citations if citation["quote"]),
            sources=tuple(
                name
                for name in dict.fromkeys(
                    _source_name(cited.sources.get(c["sourceId"])) for c in view.citations
                )
                if name
            ),
        )
        for claim_id, view in cited.views.items()
    }


def _source_name(ref: Mapping[str, Any] | None) -> str:
    if not ref or not ref.get("title"):
        return ""
    return f"{ref['title']} ({ref['year']})" if ref.get("year") else str(ref["title"])


async def _kept(context: SectionContext, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf:
    if composed.not_enough_evidence is not None and not pack.documents:
        return ()
    if pack.documents:
        await context.stream.status("WRITING_BACK", len(pack.documents))
    return await context.tools.store.keep(context.answer_id, pack, composed)


def _built(spec: SectionSpec, context: SectionContext, drafted: _Drafted) -> Attempt:
    composed, split, cited = drafted.composed, drafted.written.split, drafted.written.cited
    deepening = context.deepening_of(spec.id)
    blocks: list[Block] = []
    ladder = None if deepening.shows(LADDER_KIND) else _ladder(spec, context, composed, deepening.number(1))
    if ladder is not None:
        blocks.append(ladder)
    prose = _prose(block_id(spec.id, deepening.number(len(blocks) + 1)), split.facts, cited)
    if prose is not None:
        blocks.append(prose)
        placed = drafted.offered.placed(
            composed.component_labels, section_id=spec.id, first=deepening.number(len(blocks) + 1)
        )
        blocks += placed.blocks
        cited = joined_claims(cited, placed.cited)
    return _attempted(spec, context, drafted, blocks, _Shown(split, cited, prose is not None))


@dataclass(frozen=True)
class _Shown:
    split: SectionSentences
    cited: CitedClaims
    has_prose: bool


def _attempted(
    spec: SectionSpec, context: SectionContext, drafted: _Drafted, blocks: Sequence[Block], shown: _Shown
) -> Attempt:
    split, cited = shown.split, shown.cited
    open_questions = tuple(
        cited_sentence(f"{spec.id}.open.{n}", sentence, cited)
        for n, sentence in enumerate(split.open_questions, 1)
    )
    kept = (*(split.facts if shown.has_prose else ()), *split.open_questions)
    return Attempt(
        pack=drafted.pack,
        composed=drafted.composed,
        blocks=tuple(context.enrichment.marked(block) for block in blocks),
        open_questions=open_questions,
        cited=cited,
        evidence_ids=tuple(evidence for sentence in kept for evidence in sentence.evidence_ids),
        claim_ids=claim_ids_of(blocks, open_questions),
    )


def _ladder(
    spec: SectionSpec, context: SectionContext, composed: ComposedAnswer, ordinal: int
) -> Block | None:
    records = context.process
    if records is None or spec.discipline != LADDER_DISCIPLINE:
        return None
    stage_ids = named_stage_ids(context.base, ladder_stage_options(records), composed.stage_ids)
    ladder = process_ladder(records, block_id=block_id(spec.id, ordinal), stage_ids=stage_ids)
    if ladder is None:
        return None
    problems = ladder_problems(ladder, records)
    if problems:
        logger.warning("ladder %s refused: %s", ladder.id, "; ".join(problems))
        return None
    return ladder


def _prose(prose_id: str, facts: Sequence[Any], cited: CitedClaims) -> Block | None:
    if not facts:
        return None
    try:
        return prose_block(prose_id, facts, cited)
    except BlockRefused as refused:
        logger.warning("%s", refused)
        return None


def _focus(spec: SectionSpec, context: SectionContext, offered: SectionCatalogue) -> ComposeFocus:
    records = context.process
    stages = ladder_stage_options(records) if records and spec.discipline == LADDER_DISCIPLINE else []
    limit = section_sentence_limit(context.base.depth)
    return ComposeFocus(
        discipline=spec.discipline,
        title=DISCIPLINE_TITLES[spec.discipline],
        stages=stages,
        sentences_max=context.fields.sentences_max(spec.discipline, limit),
        components=offered.options(),
    )


def claim_ids_of(
    blocks: Sequence[Block], open_questions: Sequence[Mapping[str, Any]]
) -> tuple[uuid.UUID, ...]:
    from_blocks = [citation.claim_id for block in blocks for citation in block.citations()]
    from_open = [citation["claimId"] for sentence in open_questions for citation in sentence["citations"]]
    return tuple(uuid.UUID(claim) for claim in dict.fromkeys([*from_blocks, *from_open]))
