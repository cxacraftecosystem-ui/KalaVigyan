from __future__ import annotations

import logging
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.composition import ComposeCandidate, ComposeRequest
from app.research.coverage_answers import shown_field_sentences
from app.research.explainer import Explainer

from .craft_resolver import CraftIndexStore
from .write_back_names import CraftNames, filing_names

__all__ = [
    "COMPARISON_LABEL",
    "explainer_off_question",
    "off_question_sentences",
    "off_question_topics",
    "screened_request",
]

logger = logging.getLogger(__name__)

COMPARISON_LABEL = "about {topics}, not the craft asked about: cite only to compare; {label}"
LABEL_MAX_CHARS = 300


def off_question_topics(texts: Sequence[str], names: CraftNames) -> tuple[str, ...]:
    if names.lead is None or names.researched(texts):
        return ()
    others = tuple(craft.name for craft in names.catalogued(texts))
    return tuple(dict.fromkeys((*names.abroad_in(texts), *others)))


def screened_request(
    request: ComposeRequest, names: CraftNames | None, *, comparison: bool
) -> ComposeRequest:
    if names is None:
        return request
    kept: list[ComposeCandidate] = []
    for candidate in request.candidates:
        topics = off_question_topics(candidate.cited_texts, names) if candidate.kind == "EVIDENCE" else ()
        if not topics:
            kept.append(candidate)
        elif comparison:
            kept.append(_labelled(candidate, topics))
        else:
            logger.info("passage %s is about %s, so it is not offered", candidate.id, ", ".join(topics))
    return request.model_copy(update={"candidates": kept})


def off_question_sentences(explainer: Explainer, names: CraftNames) -> int:
    return sum(
        1
        for one in shown_field_sentences(explainer)
        if any(off_question_topics([c.quote], names) for c in one.sentence.citations if c.quote)
    )


async def explainer_off_question(
    session: AsyncSession, store: CraftIndexStore, explainer: Explainer, craft_slug: str
) -> int:
    index = await store.get(session)
    target = index.slugs.get(craft_slug)
    lead = index.refs.get(target.craft_id) if target is not None else None
    if lead is None:
        return 0
    return off_question_sentences(explainer, await filing_names(session, store, lead, ()))


def _labelled(candidate: ComposeCandidate, topics: Sequence[str]) -> ComposeCandidate:
    label = COMPARISON_LABEL.format(topics=", ".join(topics), label=candidate.source_label)
    return candidate.model_copy(update={"source_label": label[:LABEL_MAX_CHARS]})
