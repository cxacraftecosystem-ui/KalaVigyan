from __future__ import annotations

import logging
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal, Protocol

from app.core.errors import AppError, ExternalFailure
from app.research.candidate_gates import (
    DUPLICATE_GATE,
    NOVELTY_GATE,
    Candidate,
    CitedSource,
    FactComparison,
    GateOutcome,
    HeldFact,
    NoveltyVerdict,
    close_facts,
    duplicate_outcome,
    held_twin,
    novelty_outcome,
    quote_gate,
    source_gate,
)
from app.research.candidate_judge import (
    JudgeAsk,
    JudgeRequest,
    comparison_request,
    novelty_request,
    parsed_comparisons,
    parsed_novelty,
)
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.gate_thrift import (
    GateThrift,
    distant_novelty,
    novel_by_distance,
    vector_twin,
    vector_twin_outcome,
)
from app.research.structured import StructuredModel, reply_object
from app.retrieval.text import document_text

__all__ = [
    "NOVELTY_FACTS_MAX",
    "NOVELTY_FAILURE_RAISED",
    "NOVELTY_LEFT_UNJUDGED",
    "GateRun",
    "HeldFacts",
    "LaterGates",
    "NoveltyFailure",
    "candidate_text",
    "candidate_vectors",
    "first_gates",
    "gate_run",
    "later_gates",
]

logger = logging.getLogger(__name__)

NOVELTY_FACTS_MAX = 12

type NoveltyFailure = Literal["RAISED", "UNJUDGED"]
NOVELTY_FAILURE_RAISED: NoveltyFailure = "RAISED"
NOVELTY_LEFT_UNJUDGED: NoveltyFailure = "UNJUDGED"


class HeldFacts(Protocol):
    async def nearest(self, field: str | None, vector: Sequence[float], limit: int) -> list[HeldFact]: ...

    async def twins(self, field: str | None, statement: str) -> list[HeldFact]: ...


@dataclass(frozen=True)
class LaterGates:
    outcomes: tuple[GateOutcome, ...]
    vector: list[float] | None


@dataclass(frozen=True)
class GateRun:
    candidate: Candidate
    outcomes: tuple[GateOutcome, ...]
    vector: list[float] | None = None

    @property
    def passed(self) -> bool:
        return all(outcome.passed for outcome in self.outcomes)

    @property
    def refused_at(self) -> GateOutcome | None:
        return next((outcome for outcome in self.outcomes if not outcome.passed), None)

    @property
    def differs_from(self) -> list[uuid.UUID]:
        found = self._outcome(DUPLICATE_GATE)
        return list(found.related) if found is not None and found.passed else []

    @property
    def held_instead(self) -> list[uuid.UUID]:
        refused = self.refused_at
        if refused is None or refused.gate not in (DUPLICATE_GATE, NOVELTY_GATE):
            return []
        return list(refused.related)

    def _outcome(self, gate: str) -> GateOutcome | None:
        return next((outcome for outcome in self.outcomes if outcome.gate == gate), None)


@dataclass(frozen=True)
class _Held:
    twin: HeldFact | None
    nearest: tuple[HeldFact, ...]
    close: tuple[HeldFact, ...]
    near_twin: HeldFact | None = None
    distant: bool = False

    @property
    def compared(self) -> bool:
        return self.twin is None and self.near_twin is None and bool(self.close)


@dataclass(frozen=True)
class _Judging:
    ladder: tuple[StructuredModel, ...]
    thrift: GateThrift | None
    novelty_failure: NoveltyFailure = NOVELTY_FAILURE_RAISED


def first_gates(candidate: Candidate, sources: Sequence[CitedSource]) -> tuple[GateOutcome, ...]:
    quoted = quote_gate(candidate.statement, sources)
    if not quoted.passed:
        return (quoted,)
    return quoted, source_gate(candidate.statement, candidate.field, sources)


def gate_run(candidate: Candidate, first: Sequence[GateOutcome], later: LaterGates | None) -> GateRun:
    if later is None:
        return GateRun(candidate, tuple(first))
    return GateRun(candidate, (*first, *later.outcomes), later.vector)


async def later_gates(
    store: HeldFacts,
    candidates: Sequence[Candidate],
    *,
    embed: TextEmbedder | None,
    judge: StructuredModel | None,
    thrift: GateThrift | None = None,
    escalate: Sequence[StructuredModel] = (),
    novelty_failure: NoveltyFailure = NOVELTY_FAILURE_RAISED,
) -> dict[str, LaterGates]:
    if not candidates:
        return {}
    ladder = () if judge is None else (judge, *escalate)
    judging = _Judging(ladder=ladder, thrift=thrift, novelty_failure=novelty_failure)
    vectors = await candidate_vectors(embed, candidates)
    held = {c.ref: await _held(store, c, vectors.get(c.ref), thrift) for c in candidates}
    duplicates = await _duplicates(judging, candidates, held, vectored=embed is not None)
    passing = [candidate for candidate in candidates if duplicates[candidate.ref].passed]
    novelty = await _novelty(judging, passing, held, duplicates) if embed is not None else {}
    return {
        candidate.ref: LaterGates(
            outcomes=tuple(
                o for o in (duplicates[candidate.ref], novelty.get(candidate.ref)) if o is not None
            ),
            vector=vectors.get(candidate.ref),
        )
        for candidate in candidates
    }


async def candidate_vectors(
    embed: TextEmbedder | None, candidates: Sequence[Candidate]
) -> dict[str, list[float]]:
    if embed is None or not candidates:
        return {}
    texts = [candidate_text(candidate) for candidate in candidates]
    found = checked_vectors(await embed(texts), expected=len(texts))
    return {candidate.ref: vector for candidate, vector in zip(candidates, found, strict=True)}


def candidate_text(candidate: Candidate) -> str:
    return document_text(candidate.statement, title=candidate.title)


async def _held(
    store: HeldFacts, candidate: Candidate, vector: list[float] | None, thrift: GateThrift | None
) -> _Held:
    nearest = tuple(await store.nearest(candidate.field, vector, NOVELTY_FACTS_MAX)) if vector else ()
    twins = await store.twins(candidate.field, candidate.statement)
    twin = held_twin(candidate.statement, [*twins, *nearest])
    close = tuple(close_facts(nearest))
    if thrift is None or twin is not None:
        return _Held(twin=twin, nearest=nearest, close=close)
    return _Held(
        twin=None,
        nearest=nearest,
        close=close,
        near_twin=vector_twin(candidate.statement, close, at_least=thrift.twin_similarity),
        distant=novel_by_distance(nearest, below=thrift.novelty_similarity),
    )


async def _duplicates(
    judging: _Judging,
    candidates: Sequence[Candidate],
    held: Mapping[str, _Held],
    *,
    vectored: bool,
) -> dict[str, GateOutcome]:
    asks = [JudgeAsk(c, held[c.ref].close) for c in candidates if held[c.ref].compared]
    compared: dict[str, list[FactComparison]] = {}
    model = None
    if asks and judging.ladder:
        compared, model = await _asked(
            judging.ladder, comparison_request(asks), lambda reply: parsed_comparisons(reply, asks)
        )
    found: dict[str, GateOutcome] = {}
    for candidate in candidates:
        mine = held[candidate.ref]
        if mine.near_twin is not None:
            found[candidate.ref] = vector_twin_outcome(mine.near_twin)
            continue
        found[candidate.ref] = duplicate_outcome(
            candidate,
            twin=mine.twin,
            close=mine.close,
            comparisons=compared.get(candidate.ref),
            model=model,
            vectored=vectored,
        )
    return found


async def _novelty(
    judging: _Judging,
    candidates: Sequence[Candidate],
    held: Mapping[str, _Held],
    duplicates: Mapping[str, GateOutcome],
) -> dict[str, GateOutcome]:
    settled = {c.ref for c in candidates if held[c.ref].distant and not duplicates[c.ref].related}
    asks = [
        JudgeAsk(c, held[c.ref].nearest)
        for c in candidates
        if held[c.ref].nearest and not duplicates[c.ref].related and c.ref not in settled
    ]
    verdicts: dict[str, NoveltyVerdict] = {}
    model = None
    if asks and judging.ladder:
        verdicts, model = await _novelty_verdicts(judging, asks)
    found: dict[str, GateOutcome] = {}
    for candidate in candidates:
        if candidate.ref in settled:
            found[candidate.ref] = distant_novelty(candidate, held[candidate.ref].nearest)
            continue
        outcome = novelty_outcome(
            candidate,
            differs=duplicates[candidate.ref].related,
            held_count=len(held[candidate.ref].nearest),
            verdict=verdicts.get(candidate.ref),
            model=model,
        )
        if outcome is not None:
            found[candidate.ref] = outcome
    return found


async def _novelty_verdicts(
    judging: _Judging, asks: Sequence[JudgeAsk]
) -> tuple[dict[str, NoveltyVerdict], str | None]:
    try:
        return await _asked(judging.ladder, novelty_request(asks), lambda reply: parsed_novelty(reply, asks))
    except AppError as error:
        if judging.novelty_failure != NOVELTY_LEFT_UNJUDGED:
            raise
        logger.warning(
            "the novelty judge failed, so novelty is left unjudged and duplicates stand: %s", error
        )
        return {}, None


async def _asked[T](
    ladder: Sequence[StructuredModel], request: JudgeRequest, parse: Callable[[dict[str, Any]], T]
) -> tuple[T, str | None]:
    failure: ExternalFailure | None = None
    for judge in ladder:
        reply = await judge(system=request.system, user=request.user, schema=request.schema)
        try:
            return parse(reply_object(reply)), reply.model
        except ExternalFailure as refused:
            failure = refused
    if failure is None:
        raise ExternalFailure("no judge was given to ask", service="model")
    raise failure
