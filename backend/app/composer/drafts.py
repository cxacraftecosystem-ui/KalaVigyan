from __future__ import annotations

import logging
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any

from pydantic import ValidationError

from app.core.errors import ExternalFailure
from app.research.composition import (
    FOLLOW_UPS_MAX,
    HEADING_MAX_CHARS,
    ComposeCandidate,
    ComposedSentence,
    ComposeFocus,
    QuotedSpan,
    sentence_violations,
)
from app.research.evidence import personal_data_in
from app.research.gap_admissions import without_source_gap
from app.research.quotes import figures_in
from app.research.sections import is_facet_label
from app.research.sentence_support import NEGATION_CHANGED, negation_gap
from app.research.structured import MODEL_SERVICE

__all__ = [
    "LEDE_DRAFT_HEADING",
    "MAX_SECTIONS",
    "SECTION_SENTENCES_MAX",
    "WHOLE_ANSWER_FORM",
    "AnswerForm",
    "DraftAnswer",
    "DraftSection",
    "DraftSentence",
    "checked_block_sentence",
    "checked_heading",
    "checked_sentence",
    "free_text_problem",
    "parsed_answer",
    "parsed_lede",
    "parsed_replacements",
    "parsed_section",
]

logger = logging.getLogger(__name__)

LINK_OR_MARKUP = re.compile(r"https?:|www\.|<|>|\]\(", re.IGNORECASE)
LEDE_DRAFT_HEADING = "The direct answer"
HEADING_QUOTES = "\"'‘’“”"
MAX_SECTIONS = 6
SECTION_SENTENCES_MAX = 8


@dataclass(frozen=True)
class AnswerForm:
    sections: int
    sentences: int
    follow_ups: int


WHOLE_ANSWER_FORM = AnswerForm(
    sections=MAX_SECTIONS, sentences=SECTION_SENTENCES_MAX, follow_ups=FOLLOW_UPS_MAX
)


@dataclass(frozen=True)
class DraftSentence:
    heading: str
    raw_text: str
    sentence: ComposedSentence | None
    problems: tuple[str, ...]
    answer: bool = False

    @property
    def passes(self) -> bool:
        return self.sentence is not None and not self.problems

    @property
    def problem_kinds(self) -> tuple[str, ...]:
        return tuple(problem.split(":", 1)[0] for problem in self.problems)


@dataclass(frozen=True)
class DraftSection:
    heading: str
    sentences: tuple[DraftSentence, ...]


@dataclass(frozen=True)
class DraftAnswer:
    sections: tuple[DraftSection, ...]
    follow_ups: tuple[str, ...]
    stage_ids: tuple[str, ...] = ()
    heading: str | None = None
    headings: tuple[tuple[str, str], ...] = ()
    component_labels: tuple[str, ...] = ()
    unoffered_labels: int = 0

    @property
    def failed(self) -> list[DraftSentence]:
        return [s for section in self.sections for s in section.sentences if not s.passes]

    @property
    def answer(self) -> DraftSentence | None:
        return next((s for section in self.sections for s in section.sentences if s.answer), None)


@dataclass(frozen=True)
class _Chosen:
    kept: tuple[str, ...] = ()
    dropped: int = 0


def parsed_answer(
    reply: Mapping[str, Any],
    allowed: Mapping[str, ComposeCandidate],
    *,
    form: AnswerForm = WHOLE_ANSWER_FORM,
) -> DraftAnswer:
    sections = _list(reply, "sections")[: form.sections]
    follow_ups = _list(reply, "followUps")
    return DraftAnswer(
        sections=tuple(_section(raw, allowed, sentences_max=form.sentences) for raw in sections),
        follow_ups=tuple(_usable_follow_ups(follow_ups)[: form.follow_ups]),
    )


def parsed_section(
    reply: Mapping[str, Any],
    allowed: Mapping[str, ComposeCandidate],
    *,
    focus: ComposeFocus,
    follow_ups_max: int,
) -> DraftAnswer:
    title = focus.title
    sentences = _list(reply, "sentences")[: focus.sentences_max]
    labels = _offered_only(reply, "components", focus.component_labels)
    return DraftAnswer(
        sections=(DraftSection(title, tuple(checked_block_sentence(s, title, allowed) for s in sentences)),),
        follow_ups=tuple(_usable_follow_ups(_list(reply, "followUps"))[:follow_ups_max]),
        stage_ids=_chosen_stages(reply, focus.stage_ids),
        heading=checked_heading(reply.get("heading")),
        component_labels=labels.kept,
        unoffered_labels=labels.dropped,
    )


def parsed_lede(
    reply: Mapping[str, Any],
    allowed: Mapping[str, ComposeCandidate],
    *,
    section_ids: Sequence[str],
    limit: int,
) -> DraftAnswer:
    sentences = _list(reply, "sentences")[:limit]
    marked = next(
        (n for n, raw in enumerate(sentences) if isinstance(raw, Mapping) and raw.get("answer") is True), None
    )
    checked = tuple(
        replace(checked_sentence(raw, LEDE_DRAFT_HEADING, allowed), answer=n == marked)
        for n, raw in enumerate(sentences)
    )
    return DraftAnswer(
        sections=(DraftSection(LEDE_DRAFT_HEADING, checked),),
        follow_ups=tuple(_usable_follow_ups(_list(reply, "followUps"))),
        headings=_chosen_headings(reply.get("headings"), section_ids),
    )


def checked_heading(raw: Any) -> str | None:
    if not isinstance(raw, str):
        return None
    heading = raw.strip().strip(HEADING_QUOTES).strip()
    problem = _heading_problem(heading) or ("names a field" if is_facet_label(heading) else None)
    if problem:
        logger.warning("a composed heading %s; the section keeps its own", problem)
        return None
    return heading


def parsed_replacements(
    reply: Mapping[str, Any], failed: int, allowed: Mapping[str, ComposeCandidate]
) -> dict[int, DraftSentence]:
    replacements: dict[int, DraftSentence] = {}
    for raw in _list(reply, "sentences"):
        index = raw.get("index") if isinstance(raw, Mapping) else None
        if isinstance(index, int) and 0 <= index < failed and index not in replacements:
            replacements[index] = checked_sentence(raw, "", allowed)
    return replacements


def checked_sentence(raw: Any, heading: str, allowed: Mapping[str, ComposeCandidate]) -> DraftSentence:
    raw_text = str(raw.get("text", "")) if isinstance(raw, Mapping) else str(raw)
    try:
        sentence = _sentence(raw, allowed)
    except (ValidationError, TypeError, AttributeError, KeyError, ValueError) as error:
        return DraftSentence(heading, raw_text, None, (f"MALFORMED: {_reason(error)}",))
    problems = tuple(f"{v.kind}: {v.detail}" for v in sentence_violations(sentence, allowed))
    return DraftSentence(heading, raw_text, sentence, problems)


def checked_block_sentence(raw: Any, heading: str, allowed: Mapping[str, ComposeCandidate]) -> DraftSentence:
    checked = checked_sentence(raw, heading, allowed)
    sentence = checked.sentence
    if sentence is None or NEGATION_CHANGED not in checked.problem_kinds:
        return checked
    stated = without_source_gap(sentence.text)
    if stated is None or negation_gap(stated, [span.text for span in sentence.spans]) is not None:
        return checked
    kept = tuple(problem for problem in checked.problems if not problem.startswith(f"{NEGATION_CHANGED}:"))
    return replace(checked, problems=kept)


def free_text_problem(text: str) -> str | None:
    if LINK_OR_MARKUP.search(text):
        return "carries a link or markup"
    found = personal_data_in(text)
    if found:
        return f"carries personal data ({', '.join(found)})"
    return None


def _section(raw: Any, allowed: Mapping[str, ComposeCandidate], *, sentences_max: int) -> DraftSection:
    if not isinstance(raw, Mapping):
        raise _unusable("a section is not an object")
    heading = str(raw.get("heading", "")).strip()
    problem = _heading_problem(heading)
    if problem:
        raise _unusable(f"a section heading {problem}")
    sentences = _list(raw, "sentences")[:sentences_max]
    return DraftSection(heading, tuple(checked_sentence(s, heading, allowed) for s in sentences))


def _sentence(raw: Mapping[str, Any], allowed: Mapping[str, ComposeCandidate]) -> ComposedSentence:
    spans = [QuotedSpan(ref=str(q["source"]), text=str(q["quote"])) for q in raw["quotes"]]
    refs = list(dict.fromkeys(span.ref for span in spans))
    claims = [ref for ref in refs if ref in allowed and allowed[ref].kind == "CLAIM"]
    return ComposedSentence(
        text=str(raw["text"]),
        claim_ids=[uuid.UUID(ref) for ref in claims],
        evidence_ids=[ref for ref in refs if ref not in claims],
        spans=spans,
    )


def _heading_problem(heading: str) -> str | None:
    if not heading or len(heading) > HEADING_MAX_CHARS:
        return f"is empty or longer than {HEADING_MAX_CHARS} characters"
    if figures_in(heading):
        return "carries a number or formula"
    return free_text_problem(heading)


def _usable_follow_ups(raw: list[Any]) -> list[str]:
    texts = [str(item).strip() for item in raw]
    return [text for text in texts if text and free_text_problem(text) is None][:FOLLOW_UPS_MAX]


def _chosen_headings(raw: Any, section_ids: Sequence[str]) -> tuple[tuple[str, str], ...]:
    chosen: dict[str, str] = {}
    for item in raw if isinstance(raw, list) else []:
        section = item.get("section") if isinstance(item, Mapping) else None
        heading = checked_heading(item.get("heading")) if isinstance(item, Mapping) else None
        if section in section_ids and section not in chosen and heading is not None:
            chosen[section] = heading
    return tuple(chosen.items())


def _chosen_stages(reply: Mapping[str, Any], offered: Sequence[str]) -> tuple[str, ...]:
    chosen = _offered_only(reply, "stages", offered)
    if chosen.dropped:
        logger.warning("compose chose %d process stage(s) that were not offered", chosen.dropped)
    return chosen.kept


def _offered_only(reply: Mapping[str, Any], key: str, offered: Sequence[str]) -> _Chosen:
    if not offered:
        return _Chosen()
    chosen = [str(item) for item in _list(reply, key)]
    unknown = [item for item in chosen if item not in offered]
    return _Chosen(tuple(item for item in dict.fromkeys(chosen) if item in offered), len(unknown))


def _list(raw: Mapping[str, Any], key: str) -> list[Any]:
    value = raw.get(key)
    if not isinstance(value, list):
        raise _unusable(f"{key} is missing or not a list")
    return value


def _unusable(reason: str) -> ExternalFailure:
    return ExternalFailure(f"the compose reply is unusable: {reason}", service=MODEL_SERVICE)


def _reason(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return ", ".join(sorted({".".join(str(p) for p in e["loc"]) or "sentence" for e in error.errors()}))
    return type(error).__name__
