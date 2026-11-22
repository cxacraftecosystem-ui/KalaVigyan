from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.geo.rainfall import DistrictRainfall
from app.research.blocks import ExplainerSentence
from app.research.blocks_place import SeasonRow, SeasonsBlock
from app.research.calendar import only_season, season_months, year_months
from app.research.citations import Citation
from app.research.vocabulary import FACT_LEVELS, weakest_level
from app.science.records import KnownClaim, ProcessRecords

__all__ = [
    "SEASON_ROWS_MAX",
    "SeasonFact",
    "SeasonMapping",
    "SeasonOffer",
    "StageClaims",
    "rain_only_block",
    "season_facts",
    "season_mappings",
    "seasons_block",
    "stage_claims",
]

logger = logging.getLogger(__name__)

SEASON_ROWS_MAX = 12


@dataclass(frozen=True)
class StageClaims:
    stage_id: uuid.UUID
    name: str
    claims: tuple[KnownClaim, ...]


@dataclass(frozen=True)
class SeasonFact:
    claim: KnownClaim
    subject: str | None


@dataclass(frozen=True)
class SeasonOffer:
    stages: tuple[StageClaims, ...]
    facts: tuple[SeasonFact, ...]
    rainfall: DistrictRainfall | None


@dataclass(frozen=True)
class SeasonMapping:
    months: frozenset[int]
    citation: Citation
    level: str


@dataclass(frozen=True)
class _Planned:
    stage_id: uuid.UUID | None
    label: str
    claim: KnownClaim
    months: frozenset[int] = frozenset()
    season: str | None = None

    @property
    def timed(self) -> bool:
        return bool(self.months) or self.season is not None


def seasons_block(offer: SeasonOffer, *, block_id: str) -> SeasonsBlock | None:
    planned = _within_max(_planned_rows(offer))
    if not any(plan.timed for plan in planned):
        return None
    rows = _rows(planned, season_mappings(_offered_claims(offer)), block_id)
    if not any(row.months or row.season for row in rows):
        return None
    return _seasons(block_id, rows, offer.rainfall)


def rain_only_block(rainfall: DistrictRainfall | None, *, block_id: str) -> SeasonsBlock | None:
    return None if rainfall is None else _seasons(block_id, [], rainfall)


def stage_claims(records: ProcessRecords) -> tuple[StageClaims, ...]:
    order = {process.id: n for n, process in enumerate(records.processes)}
    stages = sorted(records.stages, key=lambda s: (order.get(s.process_id, len(order)), s.ordinal, s.name))
    return tuple(
        StageClaims(stage.id, stage.name, tuple(_stored_facts(records, stage.claim_ids))) for stage in stages
    )


def season_facts(facts: Iterable[KnownClaim], subjects: Mapping[uuid.UUID, str]) -> tuple[SeasonFact, ...]:
    return tuple(SeasonFact(fact, subjects.get(fact.id)) for fact in facts)


def season_mappings(claims: Iterable[KnownClaim]) -> dict[str, SeasonMapping]:
    stated: dict[str, list[SeasonMapping]] = {}
    for claim in claims:
        for citation in claim.citations:
            for season, months in season_months(citation.quote or "").items():
                stated.setdefault(season, []).append(SeasonMapping(months, citation, claim.level))
    return {
        season: found[0]
        for season, found in stated.items()
        if len({mapping.months for mapping in found}) == 1
    }


def _planned_rows(offer: SeasonOffer) -> list[_Planned]:
    cited = {fact.claim.id for fact in offer.facts}
    staged = {claim.id for stage in offer.stages for claim in stage.claims}
    stage_rows = (_stage_row(stage, cited) for stage in offer.stages)
    planned = [*(plan for plan in stage_rows if plan is not None), *_fact_rows(offer.facts, staged)]
    seen: set[uuid.UUID] = set()
    kept: list[_Planned] = []
    for plan in planned:
        if plan.claim.id not in seen:
            seen.add(plan.claim.id)
            kept.append(plan)
    return kept


def _stage_row(stage: StageClaims, cited: set[uuid.UUID]) -> _Planned | None:
    for claim in stage.claims:
        months, season = _timing(claim)
        if months or season is not None:
            return _Planned(stage.stage_id, stage.name, claim, months, season)
    listed = next((claim for claim in stage.claims if claim.id in cited), None)
    return None if listed is None else _Planned(stage.stage_id, stage.name, listed)


def _fact_rows(facts: Sequence[SeasonFact], staged: set[uuid.UUID]) -> Iterator[_Planned]:
    for fact in facts:
        if fact.claim.id in staged or not fact.subject:
            continue
        months, season = _timing(fact.claim)
        if months or season is not None:
            yield _Planned(None, fact.subject, fact.claim, months, season)


def _stored_facts(records: ProcessRecords, claim_ids: Iterable[uuid.UUID]) -> Iterator[KnownClaim]:
    for claim_id in claim_ids:
        claim = records.claims.get(claim_id)
        if claim is not None and claim.level in FACT_LEVELS and claim.citations:
            yield claim


def _timing(claim: KnownClaim) -> tuple[frozenset[int], str | None]:
    return year_months([claim.text]), only_season(claim.text)


def _within_max(planned: list[_Planned]) -> list[_Planned]:
    if len(planned) <= SEASON_ROWS_MAX:
        return planned
    timed = [plan.claim.id for plan in planned if plan.timed][:SEASON_ROWS_MAX]
    listed = [plan.claim.id for plan in planned if not plan.timed][: SEASON_ROWS_MAX - len(timed)]
    kept = {*timed, *listed}
    return [plan for plan in planned if plan.claim.id in kept]


def _offered_claims(offer: SeasonOffer) -> list[KnownClaim]:
    claims = [fact.claim for fact in offer.facts] + [c for stage in offer.stages for c in stage.claims]
    return list({claim.id: claim for claim in claims}.values())


def _rows(
    planned: Sequence[_Planned], mappings: Mapping[str, SeasonMapping], block_id: str
) -> list[SeasonRow]:
    rows: list[SeasonRow] = []
    for plan in planned:
        row = _season_row(plan, mappings, f"{block_id}.{len(rows) + 1}")
        if row is not None:
            rows.append(row)
    return rows


def _season_row(plan: _Planned, mappings: Mapping[str, SeasonMapping], sentence_id: str) -> SeasonRow | None:
    citations, levels, months = list(plan.claim.citations), [plan.claim.level], plan.months
    mapping = mappings.get(plan.season) if plan.season is not None and not months else None
    if mapping is not None:
        months = mapping.months
        if all(citation.id != mapping.citation.id for citation in citations):
            citations.append(mapping.citation)
            levels.append(mapping.level)
    try:
        sentence = ExplainerSentence(
            id=sentence_id, text=plan.claim.text, level=weakest_level(levels), citations=citations, terms=[]
        )
        return SeasonRow(
            stage_id=plan.stage_id,
            label=plan.label,
            months=sorted(months),
            season=plan.season,
            sentence=sentence,
        )
    except ValidationError as refused:
        logger.info("the season row %r is left out: %s", plan.label, refused)
        return None


def _seasons(block_id: str, rows: list[SeasonRow], rain: DistrictRainfall | None) -> SeasonsBlock | None:
    try:
        return SeasonsBlock(
            id=block_id,
            kind="seasons",
            version=1,
            reuse=None,
            rows=rows,
            rainfall=rain.rain if rain is not None else None,
            datasets=[rain.dataset] if rain is not None else [],
        )
    except ValidationError as refused:
        logger.warning("the seasons block %s is refused: %s", block_id, refused)
        return None
