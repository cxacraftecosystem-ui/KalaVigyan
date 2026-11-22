from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from pydantic import Field, ValidationError

from .base import ContractModel
from .blocks_play import (
    SIMULATION_GROUNDS_MAX,
    SIMULATION_REACTIONS_MAX,
    SIMULATION_VALUES_MAX,
    SimulationBlock,
    SimulationReaction,
    SimulationValue,
    simulation_data,
)
from .citations import Citation
from .datasets import DatasetRef
from .quotes import normalise_quote_text, numbers_in, quote_occurs
from .sandbox import SANDBOX_MAX_BYTES, SandboxProblem, sandbox_problems

__all__ = [
    "DATASET_REF_PREFIX",
    "DRAFT_RULES",
    "NO_GROUNDING",
    "OFFER_REF_PREFIX",
    "REACTION_REF_PREFIX",
    "SIMULATION_HTML_MAX_CHARS",
    "STATED_MAX_CHARS",
    "STATED_WORDS_AROUND",
    "STATEMENT_REF_PREFIX",
    "DraftCheck",
    "DraftValue",
    "Grounding",
    "OfferedReaction",
    "OfferedStatement",
    "OfferedValue",
    "RowValue",
    "SimulationDraft",
    "checked_draft",
    "data_object",
    "offered_rows",
    "offered_values",
    "stated_figures",
]

DRAFT_RULES = ("VALUE", "GROUND", "BLOCK")
OFFER_REF_PREFIX = "v"
DATASET_REF_PREFIX = "d"
STATEMENT_REF_PREFIX = "s"
REACTION_REF_PREFIX = "r"
STATED_WORDS_AROUND = 3
STATED_MAX_CHARS = 200
CLAUSE_ENDS = (".", ",", ";", ":", "!", "?")
CLOSING_MARKS = "\"')]}"
STATED_EDGES = "\"'()[]{},;:.!? "
DRAFT_TEXT_MAX_CHARS = 200
SIMULATION_HTML_MAX_CHARS = 40000


@dataclass(frozen=True)
class OfferedValue:
    ref: str
    figure: str
    value: float
    stated: str
    citation: Citation | None = None
    dataset: DatasetRef | None = None

    def __post_init__(self) -> None:
        if (self.citation is None) == (self.dataset is None):
            raise ValueError(
                f"offered value {self.ref} rests on a cited quote or on a dataset row, one of them"
            )

    @property
    def claim_id(self) -> uuid.UUID | None:
        return uuid.UUID(self.citation.claim_id) if self.citation is not None else None


@dataclass(frozen=True)
class RowValue:
    value: float
    unit: str | None
    stated: str
    dataset: DatasetRef


@dataclass(frozen=True)
class OfferedStatement:
    ref: str
    text: str
    citations: tuple[Citation, ...]


@dataclass(frozen=True)
class OfferedReaction:
    ref: str
    reaction: SimulationReaction


@dataclass(frozen=True)
class Grounding:
    statements: tuple[OfferedStatement, ...] = ()
    reactions: tuple[OfferedReaction, ...] = ()


NO_GROUNDING = Grounding()


class DraftValue(ContractModel):
    ref: str = Field(min_length=1, max_length=DRAFT_TEXT_MAX_CHARS)
    key: str = Field(min_length=1, max_length=DRAFT_TEXT_MAX_CHARS)
    label: str = Field(min_length=1, max_length=DRAFT_TEXT_MAX_CHARS)
    unit: str = Field(max_length=DRAFT_TEXT_MAX_CHARS)


class SimulationDraft(ContractModel):
    build: bool
    concept: str = Field(max_length=DRAFT_TEXT_MAX_CHARS)
    title: str = Field(max_length=DRAFT_TEXT_MAX_CHARS)
    values: list[DraftValue] = Field(max_length=SIMULATION_VALUES_MAX)
    html: str = Field(max_length=SANDBOX_MAX_BYTES)
    grounds: list[str] = Field(default_factory=list, max_length=SIMULATION_GROUNDS_MAX)
    reactions: list[str] = Field(default_factory=list, max_length=SIMULATION_REACTIONS_MAX)


@dataclass(frozen=True)
class DraftCheck:
    block: SimulationBlock | None
    problems: tuple[SandboxProblem, ...]

    @property
    def rules(self) -> tuple[str, ...]:
        return tuple(sorted({problem.rule for problem in self.problems}))


def offered_values(citations: Iterable[Citation]) -> list[OfferedValue]:
    offered: dict[tuple[str, float], OfferedValue] = {}
    for citation in citations:
        for figure, value, stated in stated_figures(citation.quote or ""):
            seen = (citation.claim_id, value)
            if seen in offered:
                continue
            if len(offered) == SIMULATION_VALUES_MAX:
                return list(offered.values())
            ref = f"{OFFER_REF_PREFIX}{len(offered) + 1}"
            offered[seen] = OfferedValue(ref, figure, value, stated, citation=citation)
    return list(offered.values())


def offered_rows(rows: Iterable[RowValue], *, limit: int = SIMULATION_VALUES_MAX) -> list[OfferedValue]:
    offered: list[OfferedValue] = []
    for row in rows:
        if len(offered) == limit:
            break
        figure = f"{row.value:g} {row.unit}" if row.unit else f"{row.value:g}"
        ref = f"{DATASET_REF_PREFIX}{len(offered) + 1}"
        offered.append(OfferedValue(ref, figure, row.value, row.stated, dataset=row.dataset))
    return offered


def stated_figures(quote: str) -> Iterator[tuple[str, float, str]]:
    words = normalise_quote_text(quote).split(" ")
    for index, word in enumerate(words):
        for figure in numbers_in(word):
            value = _plain_number(figure)
            stated = _words_around(words, index)
            if value is not None and len(stated) <= STATED_MAX_CHARS and quote_occurs(stated, quote):
                yield figure, value, stated


def data_object(values: Sequence[SimulationValue]) -> dict[str, float]:
    return {value.key: value.value for value in values}


def checked_draft(
    draft: SimulationDraft,
    offers: Sequence[OfferedValue],
    *,
    block_id: str,
    model: str,
    created_at: datetime,
    grounding: Grounding = NO_GROUNDING,
) -> DraftCheck:
    if len(draft.html) > SIMULATION_HTML_MAX_CHARS:
        detail = f"{len(draft.html)} characters, more than {SIMULATION_HTML_MAX_CHARS}"
        return DraftCheck(None, (SandboxProblem("SIZE", detail),))
    values, problems = _draft_values(draft, offers)
    grounds, reactions, missing = _draft_grounds(draft, grounding)
    problems += missing
    if not (values or grounds or reactions):
        problems.append(SandboxProblem("VALUE", "no offered value, statement or reaction is used"))
    elif not (grounds or reactions or any(value.citations for value in values)):
        problems.append(
            SandboxProblem("VALUE", "dataset rows alone are no explainer; it also rests on a cited claim")
        )
    if problems:
        return DraftCheck(None, tuple(problems))
    sandboxed = sandbox_problems(draft.html, simulation_data(values, reactions))
    if sandboxed:
        return DraftCheck(None, tuple(sandboxed))
    datasets = _datasets_used(values, offers)
    block = {"id": block_id, "model": model, "created_at": created_at, "values": values, "datasets": datasets}
    return _drafted_block(draft, block | {"grounds": grounds, "reactions": reactions})


def _datasets_used(values: Sequence[SimulationValue], offers: Sequence[OfferedValue]) -> list[DatasetRef]:
    refs = {offer.dataset.code: offer.dataset for offer in offers if offer.dataset is not None}
    return [
        refs[code] for code in dict.fromkeys(value.dataset_code for value in values if value.dataset_code)
    ]


def _drafted_block(draft: SimulationDraft, fields: Mapping[str, object]) -> DraftCheck:
    try:
        block = SimulationBlock.model_validate(
            {
                **fields,
                "kind": "simulation",
                "version": 1,
                "reuse": None,
                "concept": draft.concept,
                "title": draft.title,
                "html": draft.html,
                "html_sha256": hashlib.sha256(draft.html.encode("utf-8")).hexdigest(),
                "hidden": False,
            }
        )
    except ValidationError as refused:
        return DraftCheck(None, tuple(SandboxProblem("BLOCK", message) for message in _messages(refused)))
    return DraftCheck(block, ())


def _draft_values(
    draft: SimulationDraft, offers: Sequence[OfferedValue]
) -> tuple[list[SimulationValue], list[SandboxProblem]]:
    by_ref: Mapping[str, OfferedValue] = {offer.ref: offer for offer in offers}
    refs = [chosen.ref for chosen in draft.values]
    problems = [
        SandboxProblem("VALUE", f"{ref} is used twice") for ref in sorted(set(refs)) if refs.count(ref) > 1
    ]
    values: list[SimulationValue] = []
    for chosen in draft.values:
        offer = by_ref.get(chosen.ref)
        if offer is None:
            problems.append(SandboxProblem("VALUE", f"{chosen.ref} is not an offered value"))
            continue
        try:
            values.append(_value(chosen, offer))
        except ValueError as refused:
            problems += [SandboxProblem("VALUE", message) for message in _messages(refused)]
    return values, problems


def _draft_grounds(
    draft: SimulationDraft, grounding: Grounding
) -> tuple[list[Citation], list[SimulationReaction], list[SandboxProblem]]:
    statements = {statement.ref: statement for statement in grounding.statements}
    reactions = {offered.ref: offered.reaction for offered in grounding.reactions}
    problems = [
        SandboxProblem("GROUND", f"{ref} is used twice")
        for refs in (draft.grounds, draft.reactions)
        for ref in sorted(set(refs))
        if refs.count(ref) > 1
    ]
    problems += [
        SandboxProblem("GROUND", f"{ref} is not an offered statement")
        for ref in draft.grounds
        if ref not in statements
    ]
    problems += [
        SandboxProblem("GROUND", f"{ref} is not an offered reaction")
        for ref in draft.reactions
        if ref not in reactions
    ]
    cited = dict.fromkeys(
        c for ref in dict.fromkeys(draft.grounds) if ref in statements for c in statements[ref].citations
    )
    if len(cited) > SIMULATION_GROUNDS_MAX:
        problems.append(SandboxProblem("GROUND", f"more than {SIMULATION_GROUNDS_MAX} cited passages"))
    played = [reactions[ref] for ref in dict.fromkeys(draft.reactions) if ref in reactions]
    return list(cited), played, problems


def _value(chosen: DraftValue, offer: OfferedValue) -> SimulationValue:
    unit = chosen.unit or None
    said = offer.figure if offer.dataset is not None else offer.stated
    if unit is not None and not quote_occurs(unit, said):
        raise ValueError(f"value {chosen.key} gives the unit {unit!r}, which {said!r} does not")
    from_row = offer.dataset is not None
    return SimulationValue(
        key=chosen.key,
        label=chosen.label,
        value=offer.value,
        unit=unit,
        stated=None if from_row else offer.stated,
        citations=[offer.citation] if offer.citation is not None else [],
        dataset_code=offer.dataset.code if offer.dataset is not None else None,
    )


def _messages(refused: ValueError) -> list[str]:
    if isinstance(refused, ValidationError):
        return [str(error["msg"]) for error in refused.errors()]
    return [str(refused)]


def _words_around(words: Sequence[str], index: int) -> str:
    start = index
    while start > 0 and index - start < STATED_WORDS_AROUND and not _ends_clause(words[start - 1]):
        start -= 1
    end = index
    while end < len(words) - 1 and end - index < STATED_WORDS_AROUND and not _ends_clause(words[end]):
        end += 1
    return " ".join(words[start : end + 1]).strip(STATED_EDGES)


def _plain_number(figure: str) -> float | None:
    try:
        return float(figure)
    except ValueError:
        return None


def _ends_clause(word: str) -> bool:
    return word.rstrip(CLOSING_MARKS).endswith(CLAUSE_ENDS)
