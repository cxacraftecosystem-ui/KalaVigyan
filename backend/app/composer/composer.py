from __future__ import annotations

import logging
import uuid
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from functools import partial
from typing import Any

from app.core.errors import ExternalFailure
from app.research.composition import (
    COMPOSE_RETRIES,
    LEDE_SENTENCES_MAX,
    ComposeCandidate,
    ComposedAnswer,
    ComposedLede,
    ComposedSection,
    ComposedSentence,
    ComposeRequest,
    LedeRequest,
    RefusedSentence,
    sentence_level,
)
from app.research.planning import OPEN_QUESTION_LEVEL
from app.research.reading_style import ReadingStyle
from app.research.structured import StructuredModel, reply_object

from .drafts import (
    DraftAnswer,
    DraftSection,
    DraftSentence,
    parsed_answer,
    parsed_lede,
    parsed_replacements,
    parsed_section,
)
from .prompt import (
    COMPOSE_SYSTEM_PROMPT,
    LEDE_SYSTEM_PROMPT,
    REGENERATE_SYSTEM_PROMPT,
    SECTION_FOLLOW_UPS_MAX,
    compose_message,
    compose_schema,
    lede_message,
    lede_schema,
    regenerate_message,
    regenerate_schema,
    section_schema,
    section_system_prompt,
    styled,
)

__all__ = [
    "ModelComposer",
    "ReplyForm",
    "assembled_answer",
    "assembled_lede",
    "lede_form",
    "refused_drafts",
    "reply_form",
]

logger = logging.getLogger(__name__)

Parse = Callable[[Mapping[str, Any], Mapping[str, ComposeCandidate]], DraftAnswer]


@dataclass(frozen=True)
class ReplyForm:
    system: str
    schema: dict[str, Any]
    parse: Parse
    style: ReadingStyle | None = None


def reply_form(request: ComposeRequest) -> ReplyForm:
    focus = request.focus
    if focus is None:
        system = styled(COMPOSE_SYSTEM_PROMPT, request.style)
        return ReplyForm(system, compose_schema(), parsed_answer, request.style)
    parse = partial(parsed_section, focus=focus, follow_ups_max=SECTION_FOLLOW_UPS_MAX)
    system = styled(section_system_prompt(focus.sentences_max), request.style)
    schema = section_schema(focus.stage_ids, labels=focus.component_labels)
    return ReplyForm(system, schema, parse, request.style)


def lede_form(request: LedeRequest) -> ReplyForm:
    section_ids = [section.section_id for section in request.sections]
    parse = partial(parsed_lede, section_ids=section_ids, limit=LEDE_SENTENCES_MAX)
    system = styled(LEDE_SYSTEM_PROMPT, request.style)
    return ReplyForm(system, lede_schema(section_ids), parse, request.style)


class ModelComposer:
    def __init__(self, *, model: StructuredModel) -> None:
        self._model = model

    async def compose(self, request: ComposeRequest) -> ComposedAnswer:
        if not request.candidates:
            return ComposedAnswer(not_enough_evidence=request.searched)
        if request.refused:
            return assembled_answer(await self._rewritten(request), request)
        draft = await self._checked(reply_form(request), compose_message(request), request.allowed)
        return assembled_answer(draft, request)

    async def lede(self, request: LedeRequest) -> ComposedLede:
        if not request.candidates:
            return ComposedLede()
        draft = await self._checked(lede_form(request), lede_message(request), request.allowed)
        return assembled_lede(draft, request.allowed)

    async def _checked(
        self, form: ReplyForm, message: str, allowed: Mapping[str, ComposeCandidate]
    ) -> DraftAnswer:
        draft, retries_left = await self._first_draft(form, message, allowed)
        if draft.failed and retries_left:
            draft = await self._regenerated(message, draft, allowed, form.style)
        _log_dropped(draft)
        return draft

    async def _first_draft(
        self, form: ReplyForm, user: str, allowed: Mapping[str, ComposeCandidate]
    ) -> tuple[DraftAnswer, int]:
        for attempt in range(COMPOSE_RETRIES):
            reply = await self._model(system=form.system, user=user, schema=form.schema)
            try:
                return form.parse(reply_object(reply), allowed), COMPOSE_RETRIES - attempt
            except ExternalFailure as error:
                logger.warning("compose reply %d unusable: %s", attempt + 1, error)
        reply = await self._model(system=form.system, user=user, schema=form.schema)
        return form.parse(reply_object(reply), allowed), 0

    async def _rewritten(self, request: ComposeRequest) -> DraftAnswer:
        heading = request.focus.title if request.focus else ""
        refused = refused_drafts(request.refused, heading)
        empty = DraftAnswer(sections=(DraftSection(heading, refused),), follow_ups=())
        rewritten = await self._regenerated(compose_message(request), empty, request.allowed, request.style)
        kept = tuple(sentence for sentence in rewritten.sections[0].sentences if sentence.passes)
        logger.info("rewrote %d of %d refused sentence(s) from stored claims", len(kept), len(refused))
        return replace(rewritten, sections=(DraftSection(heading, kept),))

    async def _regenerated(
        self,
        message: str,
        draft: DraftAnswer,
        allowed: Mapping[str, ComposeCandidate],
        style: ReadingStyle | None,
    ) -> DraftAnswer:
        failed = draft.failed
        reply = await self._model(
            system=styled(REGENERATE_SYSTEM_PROMPT, style),
            user=regenerate_message(message, failed),
            schema=regenerate_schema(len(failed)),
        )
        try:
            replacements = parsed_replacements(reply_object(reply), len(failed), allowed)
        except ExternalFailure as error:
            logger.warning("regenerate reply unusable, failing sentences dropped: %s", error)
            return draft
        return _with_replacements(draft, replacements)


def assembled_answer(draft: DraftAnswer, request: ComposeRequest) -> ComposedAnswer:
    allowed = request.allowed
    sections: list[ComposedSection] = []
    open_questions: list[ComposedSentence] = []
    for section in draft.sections:
        kept = [s.sentence for s in section.sentences if s.passes and s.sentence is not None]
        stated = [s for s in kept if not _is_open_question(s, allowed)]
        open_questions += [s for s in kept if _is_open_question(s, allowed)]
        if stated:
            sections.append(ComposedSection(heading=section.heading, sentences=stated))
    stage_ids = [uuid.UUID(stage) for stage in draft.stage_ids]
    if not sections and not open_questions and not stage_ids:
        return ComposedAnswer(not_enough_evidence=request.searched)
    return ComposedAnswer(
        sections=sections,
        open_questions=open_questions,
        stage_ids=stage_ids,
        follow_ups=list(draft.follow_ups),
        heading=draft.heading if sections else None,
        component_labels=list(draft.component_labels),
    )


def assembled_lede(draft: DraftAnswer, allowed: Mapping[str, ComposeCandidate]) -> ComposedLede:
    answer = _stated_answer(draft, allowed)
    if answer is None:
        logger.warning("the lede's answer sentence did not pass its checks, so no lede is written")
    kept = [s.sentence for section in draft.sections for s in section.sentences if s.passes and s.sentence]
    facts = [s for s in kept if s is not answer and not _is_open_question(s, allowed)]
    return ComposedLede(
        sentences=[answer, *facts][:LEDE_SENTENCES_MAX] if answer is not None else [],
        headings=dict(draft.headings),
        follow_ups=list(draft.follow_ups),
    )


def _stated_answer(draft: DraftAnswer, allowed: Mapping[str, ComposeCandidate]) -> ComposedSentence | None:
    answer = draft.answer
    if answer is None or not answer.passes or answer.sentence is None:
        return None
    return None if _is_open_question(answer.sentence, allowed) else answer.sentence


def _with_replacements(draft: DraftAnswer, replacements: Mapping[int, DraftSentence]) -> DraftAnswer:
    slot = 0
    sections: list[DraftSection] = []
    for section in draft.sections:
        sentences: list[DraftSentence] = []
        for sentence in section.sentences:
            if sentence.passes:
                sentences.append(sentence)
                continue
            if slot in replacements:
                sentences.append(replace(replacements[slot], heading=section.heading, answer=sentence.answer))
            slot += 1
        sections.append(DraftSection(section.heading, tuple(sentences)))
    return replace(draft, sections=tuple(sections))


def refused_drafts(refused: Sequence[RefusedSentence], heading: str) -> tuple[DraftSentence, ...]:
    return tuple(DraftSentence(heading, one.text, None, tuple(one.problems)) for one in refused)


def _is_open_question(sentence: ComposedSentence, allowed: Mapping[str, ComposeCandidate]) -> bool:
    return sentence_level(sentence, allowed) == OPEN_QUESTION_LEVEL


def _log_dropped(draft: DraftAnswer) -> None:
    failed = draft.failed
    if failed:
        kinds = Counter(kind for sentence in failed for kind in sentence.problem_kinds)
        logger.warning("compose dropped %d sentence(s): %s", len(failed), dict(sorted(kinds.items())))
    if draft.unoffered_labels:
        logger.warning("compose dropped %d component label(s) that were not offered", draft.unoffered_labels)
