from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.research.expert_panel import SeatBrief
from app.research.explainer import Block
from app.research.planning import PlanRequest
from app.research.retrieval import KnowledgeRetriever
from app.research.sections import SectionSpec
from app.research.structured import StructuredModel

from .answer_events import CitedClaims
from .live_sources import LiveSourcesStore

__all__ = ["BlockBuilder", "BuildAsk", "BuilderTools", "Built", "SeatResearch", "SourceRefs"]

SourceRefs = Mapping[str, Mapping[str, Any]]


@dataclass(frozen=True)
class BuilderTools:
    sessions: async_sessionmaker[AsyncSession]
    live: LiveSourcesStore
    plan_model: StructuredModel
    compose_model: StructuredModel
    explainer_model: StructuredModel | None = None
    retriever: KnowledgeRetriever | None = None


class SeatResearch(Protocol):
    async def __call__(self, brief: SeatBrief, discipline: str) -> CitedClaims: ...


@dataclass(frozen=True)
class BuildAsk:
    answer_id: uuid.UUID
    section: SectionSpec
    request: PlanRequest
    blocks: tuple[Block, ...]
    cited: CitedClaims
    research: SeatResearch | None = None
    answer_fields: frozenset[str] = frozenset()


@dataclass(frozen=True)
class Built:
    blocks: tuple[Block, ...] = ()
    sources: SourceRefs = field(default_factory=dict)


class BlockBuilder(Protocol):
    async def build(self, ask: BuildAsk) -> Built: ...
