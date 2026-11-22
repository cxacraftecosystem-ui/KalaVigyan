from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Final, Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel

from .fusion import EQUAL_WEIGHT, RRF_K

__all__ = [
    "CLAIM_RANKINGS",
    "FUSION_FILE",
    "FUSION_VERSION",
    "ClaimWeights",
    "FusionSettings",
    "fusion_settings",
    "parse_fusion_settings",
    "settings_text",
]

FUSION_FILE = Path(__file__).resolve().parents[1] / "data" / "eval" / "fusion.json"
FUSION_VERSION: Final = 1
CLAIM_RANKINGS = ("lexical", "vector", "entity")

Weight = Annotated[float, Field(ge=0.0, le=100.0, allow_inf_nan=False)]


class ClaimWeights(ContractModel):
    lexical: Weight = EQUAL_WEIGHT
    vector: Weight = EQUAL_WEIGHT
    entity: Weight = EQUAL_WEIGHT

    @model_validator(mode="after")
    def _one_counts(self) -> Self:
        if not any(self.ordered()):
            raise ValueError("at least one claim ranking must have a weight above zero")
        return self

    def ordered(self) -> tuple[float, ...]:
        return tuple(getattr(self, name) for name in CLAIM_RANKINGS)


class FusionSettings(ContractModel):
    version: Literal[1] = FUSION_VERSION
    about: str = ""
    k: int = Field(default=RRF_K, ge=1, le=1000)
    claims: ClaimWeights = Field(default_factory=ClaimWeights)

    def label(self) -> str:
        weights = ", ".join(
            f"{name} {weight:g}" for name, weight in zip(CLAIM_RANKINGS, self.claims.ordered(), strict=True)
        )
        return f"k {self.k}; {weights}"


def parse_fusion_settings(data: Any) -> FusionSettings:
    try:
        return FusionSettings.model_validate(data)
    except ValidationError as error:
        raise InvalidInput(f"The fusion settings are malformed: {error}") from None


def settings_text(settings: FusionSettings) -> str:
    return json.dumps(settings.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False) + "\n"


@cache
def fusion_settings(path: Path = FUSION_FILE) -> FusionSettings:
    return parse_fusion_settings(json.loads(path.read_text(encoding="utf-8")))
