from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from app.core.errors import AppError
from app.planner.reading import ReadCache
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.explainer import Block
from app.research.planning import PlanRequest, RetrievalPlan
from app.research.reading_style import ReadingStyle
from app.research.sections import AnswerPlans, SectionPlan, SectionSpec
from app.research.stream import ResearchProgress
from app.science.records import ProcessRecords

from .answer_catalogue import CatalogueLookup, no_catalogue
from .answer_events import CitedClaims
from .answer_translation import AnswerTranslation
from .block_builders import BlockBuilders
from .explainer_events import ExplainerStream
from .research_ledger import ResearchLedger
from .reuse_enrichment import Floor, shown_builds
from .section_deepening import NEW_SECTION, Deepening
from .section_enrichment import Enrichment
from .section_fields import SectionFields
from .write_back_names import CraftNames

__all__ = [
    "ClaimsOf",
    "Research",
    "SectionContext",
    "SectionOutcome",
    "SectionStore",
    "SectionTools",
    "answer_plans",
]

ClaimsOf = tuple[tuple[uuid.UUID, ...], ...]


class Research(Protocol):
    async def __call__(
        self,
        request: PlanRequest,
        progress: ResearchProgress,
        trail: ResearchTrail,
        *,
        reads: ReadCache | None = None,
    ) -> EvidencePack: ...


class SectionStore(Protocol):
    async def keep(self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf: ...

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims: ...


@dataclass(frozen=True)
class SectionTools:
    research: Research
    compose: Callable[[ComposeRequest], Awaitable[ComposedAnswer]]
    store: SectionStore
    translation: AnswerTranslation
    catalogue: CatalogueLookup = no_catalogue


@dataclass(frozen=True)
class SectionContext:
    tools: SectionTools
    stream: ExplainerStream
    answer_id: uuid.UUID
    base: PlanRequest
    ledger: ResearchLedger
    enrichment: Enrichment
    process: ProcessRecords | None = None
    builders: BlockBuilders = field(default_factory=BlockBuilders)
    deepening: Mapping[str, Deepening] = field(default_factory=dict)
    floors: Mapping[str, Floor] = field(default_factory=dict)
    reading_style: ReadingStyle | None = None
    fields: SectionFields = field(default_factory=SectionFields)
    names: CraftNames | None = None
    reads: ReadCache = field(default_factory=ReadCache)

    def deepening_of(self, section_id: str) -> Deepening:
        return self.deepening.get(section_id, NEW_SECTION)


@dataclass(frozen=True)
class SectionOutcome:
    spec: SectionSpec
    blocks: tuple[Block, ...] = ()
    built: tuple[Block, ...] = ()
    searched: str | None = None
    plans: tuple[RetrievalPlan, ...] = ()
    packs: tuple[EvidencePack, ...] = ()
    follow_ups: tuple[str, ...] = ()
    claim_ids: tuple[uuid.UUID, ...] = ()
    sources: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    failure: AppError | None = None
    shown_title: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "built", shown_builds(self.built, {block.id for block in self.blocks}))


def answer_plans(outcomes: Sequence[SectionOutcome]) -> AnswerPlans:
    return AnswerPlans(
        sections=[
            SectionPlan(section_id=outcome.spec.id, discipline=outcome.spec.discipline, plan=plan)
            for outcome in outcomes
            for plan in outcome.plans
        ]
    )
