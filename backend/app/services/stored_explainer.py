from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.research.composition import HEADING_MAX_CHARS
from app.research.planning import OPEN_QUESTION_LEVEL
from app.research.sections import (
    FALLBACK_DISCIPLINE,
    FALLBACK_HEADINGS,
    SectionSpec,
    block_id,
    fallback_heading,
    is_facet_label,
)
from app.research.vocabulary import CANONICAL_LANGUAGE, LEVEL_ORDER

from .answer_events import STORED_ANSWER_LIMIT, STORED_OPEN_QUESTION_LIMIT, CitedClaims, stored_follow_ups
from .answer_translation import AnswerTranslation, translated_block, translated_sentences
from .claim_ledger import COVERED_NOTE
from .explainer_events import ExplainerStream
from .interface_words import InterfaceWords
from .knowledge_view import ClaimView, order_claims, section_heading
from .section_blocks import KeptSentence, cited_sentence, prose_block
from .section_enrichment import Enrichment, PictureSearches

__all__ = [
    "HEADING_DISCIPLINES",
    "HEADING_WORDS_KEY",
    "shown_stored_heading",
    "stored_heading",
    "stream_stored_answer",
]

HEADING_DISCIPLINES: Mapping[str, str] = MappingProxyType(
    {
        "The tradition": "OVERVIEW",
        "History": "HISTORY",
        "Design": "DESIGN",
        "Materials and tools": "MATERIALS",
        "Process": "PROCESS",
        "The artisan's judgement": "PROCESS",
        "Place and climate": "GEOGRAPHY",
    }
)
HEADING_WORDS_KEY = "stream.heading"
STORED_SECTION_STATE = "CHECKING"


@dataclass(frozen=True)
class _StoredShowing:
    stream: ExplainerStream
    cited: CitedClaims
    translation: AnswerTranslation
    enrichment: Enrichment
    pictures: PictureSearches


async def stream_stored_answer(
    stream: ExplainerStream,
    craft_name: str,
    cited: CitedClaims,
    *,
    translation: AnswerTranslation,
    enrichment: Enrichment,
) -> bool:
    ranked = sorted(cited.views.values(), key=lambda c: (-c.rank, LEVEL_ORDER.get(c.level, 9)))
    findings = [c for c in ranked if c.level != OPEN_QUESTION_LEVEL][:STORED_ANSWER_LIMIT]
    open_questions = [c for c in ranked if c.level == OPEN_QUESTION_LEVEL][:STORED_OPEN_QUESTION_LIMIT]
    if not findings and not open_questions:
        return False
    if stream.language != CANONICAL_LANGUAGE:
        await stream.status("TRANSLATING")
    groups: dict[str, list[ClaimView]] = {}
    for view in order_claims(findings):
        groups.setdefault(section_heading(view.concept_type), []).append(view)
    async with enrichment.searching() as pictures:
        showing = _StoredShowing(stream, cited, translation, enrichment, pictures)
        for order, (group, views) in enumerate(groups.items(), start=1):
            discipline = HEADING_DISCIPLINES.get(group, FALLBACK_DISCIPLINE)
            spec = SectionSpec(
                id=f"s{order}", discipline=discipline, title=stored_heading(group, craft_name), order=order
            )
            titles = {spec.id: shown_stored_heading(group, craft_name, stream.words)}
            await stream.section_started(spec, titles=titles, state=STORED_SECTION_STATE)
            await _stored_section(showing, spec, views)
    sentences = [cited_sentence(f"open.{n}", _kept(view), cited) for n, view in enumerate(open_questions, 1)]
    if stream.language != CANONICAL_LANGUAGE and sentences:
        sentences = await translated_sentences(
            sentences, language=stream.language, translation=translation, claim_texts=_texts(cited)
        )
    await stream.open_questions(sentences, cited.sources)
    await stream.emit("follow_ups", {"items": stored_follow_ups(craft_name, list(groups), stream.words)})
    return True


def stored_heading(group: str, craft_name: str) -> str:
    if not is_facet_label(group):
        return group
    return fallback_heading(HEADING_DISCIPLINES.get(group, FALLBACK_DISCIPLINE), craft_name)


def shown_stored_heading(group: str, craft_name: str, words: InterfaceWords) -> str:
    english = stored_heading(group, craft_name)
    if not is_facet_label(group):
        return words.shown(HEADING_WORDS_KEY, group) or english
    template = FALLBACK_HEADINGS[HEADING_DISCIPLINES.get(group, FALLBACK_DISCIPLINE)]
    shown = words.shown(HEADING_WORDS_KEY, template)
    heading = english if shown is None else shown.format(craft=craft_name)
    return heading if len(heading) <= HEADING_MAX_CHARS else english


async def _stored_section(showing: _StoredShowing, spec: SectionSpec, views: Sequence[ClaimView]) -> None:
    stream, cited = showing.stream, showing.cited
    block = showing.enrichment.marked(
        prose_block(block_id(spec.id, 1), [_kept(view) for view in views], cited)
    )
    showing.pictures.start(spec.id, [block])
    if stream.language != CANONICAL_LANGUAGE:
        payload = block.model_dump(mode="json", by_alias=True)
        shown = await translated_block(
            payload,
            language=stream.language,
            translation=showing.translation,
            claim_texts=_texts(cited),
            term_names=showing.enrichment.term_names,
        )
        block = type(block).model_validate(shown)
    sent = await stream.blocks(spec.id, [block], cited.sources)
    if sent:
        await showing.pictures.sent(spec.id, stream)
    await stream.section_done(spec.id, searched=None if sent else COVERED_NOTE)


def _kept(view: ClaimView) -> KeptSentence:
    return KeptSentence(view.text, (view.id,), (), view.level == OPEN_QUESTION_LEVEL)


def _texts(cited: CitedClaims) -> dict[uuid.UUID, str]:
    return {claim_id: view.text for claim_id, view in cited.views.items()}
