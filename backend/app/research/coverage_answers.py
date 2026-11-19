from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from pydantic import Field

from app.models.block_kinds import BLOCK_KINDS
from app.models.enums import DISCIPLINES

from .base import ContractModel
from .blocks_people import ExpertSeat, ExpertViewBlock
from .citations import AnswerSentence
from .explainer import Explainer, ExplainerSection
from .vocabulary import Discipline

__all__ = [
    "FIGURE_KINDS",
    "READY",
    "TEXT_KINDS",
    "ConsultedField",
    "FieldSentence",
    "consulted_fields",
    "field_sentences",
]

READY = "READY"
TEXT_KINDS = frozenset({"prose", "expert_view", "open_questions", "quiz", "artisan_voice", "in_practice"})
FIGURE_KINDS = frozenset(BLOCK_KINDS) - TEXT_KINDS


class ConsultedField(ContractModel):
    field: Discipline
    sections: int = Field(ge=1)
    sentences: int = Field(ge=0)
    sources: int = Field(ge=0)
    figures: int = Field(ge=0)
    seats: list[ExpertSeat]


@dataclass(frozen=True)
class FieldSentence:
    field: str
    sentence: AnswerSentence


def consulted_fields(explainer: Explainer) -> list[ConsultedField]:
    shown = [section for section in explainer.sections if section.state == READY]
    order = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}
    fields = sorted(dict.fromkeys(section.discipline for section in shown), key=order.__getitem__)
    return [_consulted(discipline, [s for s in shown if s.discipline == discipline]) for discipline in fields]


def field_sentences(explainer: Explainer) -> list[FieldSentence]:
    return [
        FieldSentence(section.discipline, sentence)
        for section in explainer.sections
        if section.state == READY
        for sentence in _sentences(section)
    ]


def _consulted(discipline: str, sections: Sequence[ExplainerSection]) -> ConsultedField:
    blocks = [block for section in sections for block in section.blocks]
    seats = [block.seat for block in blocks if isinstance(block, ExpertViewBlock)]
    return ConsultedField(
        field=discipline,
        sections=len(sections),
        sentences=sum(1 for section in sections for _ in _sentences(section)),
        sources=len({source for block in blocks for source in block.cited_source_ids()}),
        figures=sum(1 for block in blocks if block.kind in FIGURE_KINDS),
        seats=list(dict.fromkeys(seats)),
    )


def _sentences(section: ExplainerSection) -> Iterator[AnswerSentence]:
    for block in section.blocks:
        yield from block.cited_sentences()
