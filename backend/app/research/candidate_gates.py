from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal

from pydantic import Field

from app.models.candidate_checks import CANDIDATE_GATES

from .base import ContractModel
from .licences import open_licence
from .quotes import QUOTE_MIN_CHARS, quote_key, quote_occurs, trivial_quote, unsupported_figures
from .stated_prices import stated_prices
from .vocabulary import Discipline, TrustTier

__all__ = [
    "COMPARISON_RELATIONS",
    "DUPLICATE_GATE",
    "GATES",
    "NEIGHBOURS_MAX",
    "NEIGHBOUR_MIN_SIMILARITY",
    "NOVELTY_GATE",
    "NO_QUOTE_REASON",
    "QUOTES_GATE",
    "SOURCE_GATE",
    "WEAKEST_GRADE",
    "Candidate",
    "CitedSource",
    "FactComparison",
    "Gate",
    "GateOutcome",
    "HeldFact",
    "NoveltyVerdict",
    "close_facts",
    "closed_outcome",
    "duplicate_outcome",
    "held_twin",
    "novelty_outcome",
    "quote_gate",
    "source_gate",
    "statement_key",
]

GATES = CANDIDATE_GATES
QUOTES_GATE, SOURCE_GATE, DUPLICATE_GATE, NOVELTY_GATE = GATES
COMPARISON_RELATIONS = ("SAME", "DIFFERS", "DISTINCT")
SAME, DIFFERS, DISTINCT = COMPARISON_RELATIONS
WEAKEST_GRADE = "D"
PRICE_FIELD = "ECONOMICS"
NEIGHBOURS_MAX = 8
NEIGHBOUR_MIN_SIMILARITY = 0.8
REASONS_MAX = 20
REASON_MAX_CHARS = 600
MODEL_NAME_MAX_CHARS = 120
NO_QUOTE_REASON = "no quote was offered, so the fact is kept as a hypothesis, never as a quoted fact"
UNVECTORED_REASON = (
    "only identical texts were looked for: the statement could not be embedded, so held facts were not "
    "compared by meaning"
)
D_ONLY_REASON = (
    "every source is graded D; a D source supports a fact only beside an A to C source, except a dated price"
)

Gate = Literal[*GATES]
Relation = Literal[*COMPARISON_RELATIONS]


class GateOutcome(ContractModel):
    gate: Gate
    passed: bool
    reasons: list[str] = Field(min_length=1, max_length=REASONS_MAX)
    model: str | None = Field(default=None, max_length=MODEL_NAME_MAX_CHARS)
    related: list[uuid.UUID] = Field(default_factory=list)


class Candidate(ContractModel):
    ref: str = Field(min_length=1, max_length=80)
    statement: str = Field(min_length=1, max_length=1000)
    field: Discipline | None


class CitedSource(ContractModel):
    url: str = Field(min_length=1)
    quotes: list[str] = Field(default_factory=list)
    text: str | None = None
    unread: str | None = None
    grade: TrustTier | None = None
    declared_licence: str | None = None
    stated_licence: str | None = None
    restricted: bool = False
    supplied: str | None = None


class HeldFact(ContractModel):
    id: uuid.UUID
    text: str
    similarity: float = Field(ge=-1.0, le=1.0)
    status: str | None = None


class FactComparison(ContractModel):
    held: uuid.UUID
    relation: Relation
    reason: str = Field(min_length=1, max_length=REASON_MAX_CHARS)


class NoveltyVerdict(ContractModel):
    adds: bool
    covered_by: list[uuid.UUID] = Field(default_factory=list)
    reason: str = Field(min_length=1, max_length=REASON_MAX_CHARS)


def statement_key(text: str) -> str:
    return quote_key(text).casefold().rstrip(" .")


def quote_gate(statement: str, sources: Sequence[CitedSource]) -> GateOutcome:
    problems = [problem for source in sources for problem in _quote_problems(source)]
    quoted = [quote for source in sources for quote in source.quotes]
    missing = unsupported_figures(statement, quoted)
    if missing:
        problems.append(f"{', '.join(missing)} in the statement appears in none of its quotes")
    if problems:
        return _outcome(QUOTES_GATE, passed=False, reasons=problems)
    if not quoted:
        return _outcome(QUOTES_GATE, passed=True, reasons=[NO_QUOTE_REASON])
    return _outcome(
        QUOTES_GATE,
        passed=True,
        reasons=[
            f"all {len(quoted)} quotes were found verbatim in their fetched sources",
            *(f"{source.url}: {source.supplied}" for source in sources if source.supplied),
        ],
    )


def source_gate(statement: str, field: str | None, sources: Sequence[CitedSource]) -> GateOutcome:
    problems = [problem for source in sources for problem in _source_problems(source)]
    grades = {source.grade for source in sources}
    if grades == {WEAKEST_GRADE} and not _dated_price(statement, field):
        problems.append(D_ONLY_REASON)
    if problems:
        return _outcome(SOURCE_GATE, passed=False, reasons=problems)
    return _outcome(SOURCE_GATE, passed=True, reasons=[_graded(source) for source in sources])


def held_twin(statement: str, held: Sequence[HeldFact]) -> HeldFact | None:
    key = statement_key(statement)
    return next((fact for fact in held if statement_key(fact.text) == key), None)


def close_facts(held: Sequence[HeldFact]) -> list[HeldFact]:
    ranked = sorted(held, key=lambda fact: (-fact.similarity, str(fact.id)))
    return [fact for fact in ranked if fact.similarity >= NEIGHBOUR_MIN_SIMILARITY][:NEIGHBOURS_MAX]


def duplicate_outcome(
    candidate: Candidate,
    *,
    twin: HeldFact | None,
    close: Sequence[HeldFact],
    comparisons: Sequence[FactComparison] | None,
    model: str | None = None,
    vectored: bool = True,
) -> GateOutcome:
    if twin is not None:
        reason = f"the same statement is already held as fact {twin.id}"
        return _outcome(DUPLICATE_GATE, passed=False, reasons=[reason], related=[twin.id])
    if not vectored:
        return _outcome(DUPLICATE_GATE, passed=True, reasons=[UNVECTORED_REASON])
    if not close:
        reason = f"no held fact of this subject {_in_field(candidate.field)} is close to it"
        return _outcome(DUPLICATE_GATE, passed=True, reasons=[reason])
    if comparisons is None:
        reason = f"{len(close)} held facts are close, and no judge compared them, so only identical texts were refused"
        return _outcome(DUPLICATE_GATE, passed=True, reasons=[reason])
    return _compared(comparisons, model)


def closed_outcome(fact: HeldFact) -> GateOutcome:
    status = (fact.status or "closed").lower()
    reason = (
        f"fact {fact.id} says the same and review closed it as {status}; research never writes a closed fact "
        "back"
    )
    return _outcome(DUPLICATE_GATE, passed=False, reasons=[reason], related=[fact.id])


def novelty_outcome(
    candidate: Candidate,
    *,
    differs: Sequence[uuid.UUID],
    held_count: int,
    verdict: NoveltyVerdict | None,
    model: str | None = None,
) -> GateOutcome | None:
    if differs:
        reason = f"it changes what the section says: it differs from {_facts(differs)}"
        return _outcome(NOVELTY_GATE, passed=True, reasons=[reason], related=list(differs))
    if held_count == 0:
        reason = f"the subject holds no fact {_in_field(candidate.field)} yet, so it adds to the section"
        return _outcome(NOVELTY_GATE, passed=True, reasons=[reason])
    if verdict is None:
        return None
    related = [] if verdict.adds else list(verdict.covered_by)
    return _outcome(NOVELTY_GATE, passed=verdict.adds, reasons=[verdict.reason], model=model, related=related)


def _compared(comparisons: Sequence[FactComparison], model: str | None) -> GateOutcome:
    same = [item for item in comparisons if item.relation == SAME]
    if same:
        reasons = [f"fact {item.held} already says the same: {item.reason}" for item in same]
        return _outcome(
            DUPLICATE_GATE, passed=False, reasons=reasons, model=model, related=[i.held for i in same]
        )
    differ = [item for item in comparisons if item.relation == DIFFERS]
    reasons = [
        f"it differs from fact {item.held}, kept as sources differ: {item.reason}"
        if item.relation == DIFFERS
        else f"distinct from fact {item.held}: {item.reason}"
        for item in comparisons
    ]
    return _outcome(
        DUPLICATE_GATE, passed=True, reasons=reasons, model=model, related=[i.held for i in differ]
    )


def _quote_problems(source: CitedSource) -> list[str]:
    if not source.quotes:
        return []
    if source.text is None:
        return [f"{source.url} could not be read: {source.unread or 'no text came back'}"]
    problems = []
    for index, quote in enumerate(source.quotes, start=1):
        if trivial_quote(quote):
            problems.append(f"quote {index} from {source.url} is shorter than {QUOTE_MIN_CHARS} characters")
        elif not quote_occurs(quote, source.text):
            where = "the text supplied for it" if source.supplied else "the page as fetched"
            problems.append(f"quote {index} from {source.url} is not in {where}")
    return problems


def _source_problems(source: CitedSource) -> list[str]:
    problems = []
    if source.grade is None:
        problems.append(f"{source.url} has no grade")
    if source.restricted:
        problems.append(f"{source.url} is a restricted source, whose words are never published")
    if _contradicted(source):
        problems.append(
            f"{source.url} is declared {source.declared_licence!r} but the page itself states "
            f"{source.stated_licence!r}"
        )
    return problems


def _contradicted(source: CitedSource) -> bool:
    stated = source.stated_licence
    return bool(stated) and open_licence(source.declared_licence) and not open_licence(stated)


def _dated_price(statement: str, field: str | None) -> bool:
    return field == PRICE_FIELD and bool(stated_prices(statement))


def _graded(source: CitedSource) -> str:
    licence = source.stated_licence or source.declared_licence or "no licence stated"
    return f"{source.url} is graded {source.grade}; licence: {licence}"


def _in_field(field: str | None) -> str:
    return f"in {field}" if field else "in any field"


def _facts(ids: Sequence[uuid.UUID]) -> str:
    return ", ".join(f"fact {fact_id}" for fact_id in ids)


def _outcome(
    gate: str,
    *,
    passed: bool,
    reasons: Sequence[str],
    model: str | None = None,
    related: Sequence[uuid.UUID] = (),
) -> GateOutcome:
    trimmed = [reason[:REASON_MAX_CHARS] for reason in reasons[:REASONS_MAX]]
    return GateOutcome(gate=gate, passed=passed, reasons=trimmed, model=model, related=list(related))
