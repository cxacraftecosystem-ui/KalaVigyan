from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import Field

from .base import ContractModel
from .crafts import CraftRef
from .image_contributions import ImageContributionView
from .layout_proposals import LayoutReview
from .review_queue_components import ComponentReview
from .review_queue_layers import LayerReview
from .review_queue_parts import FactSource, GateCheck
from .review_queue_readings import ReadingReview
from .review_queue_stages import StagePlacing
from .review_queue_structure import StructureReview
from .review_switch import PROPOSAL_ORIGINS
from .vocabulary import Discipline, EvidenceLevel

__all__ = [
    "REVIEW_ORIGINS",
    "TESTIMONY_ORIGIN",
    "ComponentItem",
    "FactConcept",
    "FactItem",
    "FactReview",
    "HeldWriteBack",
    "LayerQueueItem",
    "LayoutItem",
    "PictureItem",
    "Proposer",
    "QueueItem",
    "ReadingQueueItem",
    "ReviewOrigin",
    "StageQueueItem",
    "StructureQueueItem",
    "TestimonyItem",
]

TESTIMONY_ORIGIN = "TESTIMONY"
REVIEW_ORIGINS: tuple[str, ...] = (*PROPOSAL_ORIGINS, TESTIMONY_ORIGIN)

ReviewOrigin = Literal[*REVIEW_ORIGINS]


class Proposer(ContractModel):
    name: str
    role: str


class FactConcept(ContractModel):
    name: str
    type: str


class HeldWriteBack(ContractModel):
    reason: str
    suggested_craft: str


class FactReview(ContractModel):
    statement: str
    field: Discipline | None
    fields: list[Discipline]
    status: str
    level: EvidenceLevel
    sources_differ: bool
    concept: FactConcept | None
    sources: list[FactSource]
    gates: list[GateCheck]
    held: HeldWriteBack | None = None


class _QueueItem(ContractModel):
    id: uuid.UUID
    origin: ReviewOrigin
    submitted_at: datetime
    craft: CraftRef | None
    proposer: Proposer | None = None


class FactItem(_QueueItem):
    kind: Literal["FACTS"] = "FACTS"
    fact: FactReview


class TestimonyItem(_QueueItem):
    kind: Literal["TESTIMONY"] = "TESTIMONY"
    testimony: dict[str, Any]


class PictureItem(_QueueItem):
    kind: Literal["IMAGES"] = "IMAGES"
    picture: ImageContributionView


class ComponentItem(_QueueItem):
    kind: Literal["COMPONENTS"] = "COMPONENTS"
    component: ComponentReview


class LayoutItem(_QueueItem):
    kind: Literal["LAYOUTS"] = "LAYOUTS"
    layout: LayoutReview


class StructureQueueItem(_QueueItem):
    kind: Literal["STRUCTURE"] = "STRUCTURE"
    structure: StructureReview


class ReadingQueueItem(_QueueItem):
    kind: Literal["READINGS"] = "READINGS"
    reading: ReadingReview


class LayerQueueItem(_QueueItem):
    kind: Literal["LAYERS"] = "LAYERS"
    layer: LayerReview


class StageQueueItem(_QueueItem):
    kind: Literal["STAGES"] = "STAGES"
    stage: StagePlacing


QueueItem = Annotated[
    FactItem
    | TestimonyItem
    | PictureItem
    | ComponentItem
    | LayoutItem
    | StructureQueueItem
    | ReadingQueueItem
    | LayerQueueItem
    | StageQueueItem,
    Field(discriminator="kind"),
]
