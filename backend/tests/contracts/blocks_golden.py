from typing import Literal

from pydantic import Field

from app.research.base import ContractModel
from app.research.citations import SourceRef

from .phase_b_golden import FixtureSection

__all__ = ["QUANTITIES", "TIMELINE_UNDATED", "BlocksFixture"]

QUANTITIES = "explainer.quantities.golden.json"
TIMELINE_UNDATED = "explainer.timeline-undated.golden.json"


class BlocksFixture(ContractModel):
    schema_version: Literal[1]
    sections: list[FixtureSection] = Field(min_length=1)
    sources: list[SourceRef]
