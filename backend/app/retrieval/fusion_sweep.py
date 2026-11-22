from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import product
from typing import Any

from app.research.vocabulary import CANONICAL_LANGUAGE

from .eval_floors import HAND_WRITTEN, RELEASE_SAMPLE
from .eval_runs import EvalTools, QuestionSets, prefetched_embedder, visible_claims
from .evaluation import (
    EVAL_DEPTH,
    FactClaims,
    GoldenQuestion,
    Measures,
    QuestionResult,
    eval_query,
    expected_facts,
    measures,
)
from .fusion import reciprocal_rank_fusion
from .fusion_settings import ClaimWeights, FusionSettings
from .hybrid import ClaimRankings, SessionScopedSearch
from .release_check import release_sample

__all__ = [
    "FUSION_GRID",
    "GENERATED_ENGLISH",
    "GENERATED_OTHER",
    "FusionSweep",
    "SweepRow",
    "fused_results",
    "fusion_sweep",
    "picked_row",
    "picked_settings",
    "sweep_rows",
    "swept_sets",
]

GENERATED_ENGLISH = "generatedEnglish"
GENERATED_OTHER = "generatedOther"
GRID_K = (60, 20)
GRID_LEXICAL = (1.0, 0.5)
GRID_VECTOR = (1.0, 1.5, 2.0, 3.0, 5.0)
GRID_ENTITY = (1.0, 0.5, 0.25)
FUSION_GRID = tuple(
    FusionSettings(k=k, claims=ClaimWeights(lexical=lexical, vector=vector, entity=entity))
    for k, lexical, vector, entity in product(GRID_K, GRID_LEXICAL, GRID_VECTOR, GRID_ENTITY)
)

Asked = tuple[GoldenQuestion, tuple[FactClaims, ...]]


@dataclass(frozen=True)
class SweepRow:
    settings: FusionSettings
    sets: Mapping[str, Measures]

    def as_dict(self) -> dict[str, Any]:
        return {
            "fusion": self.settings.label(),
            "sets": {name: found.as_dict() for name, found in self.sets.items()},
        }


@dataclass(frozen=True)
class FusionSweep:
    rows: tuple[SweepRow, ...]
    picked: SweepRow
    absent: tuple[str, ...]

    @property
    def current(self) -> SweepRow:
        return self.rows[0]

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "current": self.current.as_dict(),
            "picked": self.picked.as_dict(),
            "changed": self.picked is not self.current,
            "absent": list(self.absent),
            "rows": [row.as_dict() for row in self.rows],
        }


def swept_sets(sets: QuestionSets) -> dict[str, tuple[GoldenQuestion, ...]]:
    generated = sets.generated.questions if sets.generated is not None else ()
    return {
        HAND_WRITTEN: sets.hand_written,
        GENERATED_ENGLISH: tuple(q for q in generated if q.language == CANONICAL_LANGUAGE),
        GENERATED_OTHER: tuple(q for q in generated if q.language != CANONICAL_LANGUAGE),
        RELEASE_SAMPLE: release_sample(generated, hand_written=len(sets.hand_written)),
    }


def fused_results(
    settings: FusionSettings, asked: Sequence[Asked], rankings: Mapping[str, ClaimRankings]
) -> list[QuestionResult]:
    results: list[QuestionResult] = []
    for question, facts in asked:
        order = reciprocal_rank_fusion(
            rankings[question.key], k=settings.k, weights=settings.claims.ordered()
        )
        results.append(
            QuestionResult(
                key=question.key,
                ranked=tuple((item.key,) for item in order[:EVAL_DEPTH]),
                facts=facts,
                field=question.field,
                craft_slug=question.craft_slug,
            )
        )
    return results


def sweep_rows(
    named: Mapping[str, Sequence[Asked]],
    rankings: Mapping[str, ClaimRankings],
    candidates: Sequence[FusionSettings],
) -> tuple[SweepRow, ...]:
    return tuple(
        SweepRow(
            settings,
            {name: measures(fused_results(settings, asked, rankings)) for name, asked in named.items()},
        )
        for settings in candidates
    )


def picked_row(rows: Sequence[SweepRow]) -> SweepRow:
    current = rows[0]
    held = [(at, row) for at, row in enumerate(rows) if _holds(row, current)]
    return max(held, key=lambda pair: (_score(pair[1], GENERATED_ENGLISH), -pair[0]))[1]


def picked_settings(swept: FusionSweep, *, at: datetime) -> FusionSettings:
    picked, current = swept.picked, swept.current
    about = (
        f"Picked on {at:%Y-%m-%d} by python -m app.scripts.eval_retrieval --fusion (decision 0151) from "
        f"{len(swept.rows)} weightings, as the one that scores the generated English questions best in the "
        f"fused order without lowering the hand-written ones: {_measured(picked)}. The weighting before it, "
        f"{current.settings.label()}, scored {_measured(current)}."
    )
    return picked.settings.model_copy(update={"about": about})


async def fusion_sweep(
    tools: EvalTools,
    sets: QuestionSets,
    *,
    current: FusionSettings,
    grid: Sequence[FusionSettings] = FUSION_GRID,
) -> FusionSweep:
    named = swept_sets(sets)
    questions = list({question.key: question for found in named.values() for question in found}.values())
    ids = {key: tools.claim_id(key) for question in questions for fact in question.facts for key in fact}
    async with tools.sessions() as session:
        present = await visible_claims(session, ids.values())
    asked, absent = expected_facts(questions, ids.__getitem__, present)
    by_key = {question.key: (question, facts) for question, facts in asked}
    by_set = {name: [by_key[q.key] for q in found if q.key in by_key] for name, found in named.items()}
    rankings = await _rankings(tools, list(by_key.values()))
    others = [settings for settings in grid if _weighting(settings) != _weighting(current)]
    rows = sweep_rows(by_set, rankings, [current, *others])
    return FusionSweep(rows=rows, picked=picked_row(rows), absent=tuple(absent))


async def _rankings(tools: EvalTools, asked: Sequence[Asked]) -> dict[str, ClaimRankings]:
    embed = await prefetched_embedder(tools.embed, [question.question for question, _ in asked])
    search = SessionScopedSearch(tools.sessions, embed=embed)
    gate = asyncio.Semaphore(tools.concurrency)

    async def one(question: GoldenQuestion) -> tuple[str, ClaimRankings]:
        async with gate:
            return question.key, await search.rankings(eval_query(question))

    return dict(await asyncio.gather(*(one(question) for question, _ in asked)))


def _measured(row: SweepRow) -> str:
    return "; ".join(
        f"{name} recall at 5 {found.recall_at5} and mean reciprocal rank {found.mean_reciprocal_rank}"
        for name, found in row.sets.items()
    )


def _weighting(settings: FusionSettings) -> tuple[int, tuple[float, ...]]:
    return settings.k, settings.claims.ordered()


def _score(row: SweepRow, name: str) -> tuple[float, float]:
    found = row.sets.get(name)
    if found is None or found.recall_at5 is None or found.mean_reciprocal_rank is None:
        return (0.0, 0.0)
    return (found.recall_at5, found.mean_reciprocal_rank)


def _holds(row: SweepRow, current: SweepRow) -> bool:
    return all(
        mine >= theirs
        for mine, theirs in zip(_score(row, HAND_WRITTEN), _score(current, HAND_WRITTEN), strict=True)
    )
