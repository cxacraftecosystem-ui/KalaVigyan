from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from .base import ContractModel
from .craft_page_context import SAME_FAMILY_MAX

__all__ = ["KIN_CHAPTER", "KIN_KIND", "KIN_SHARES_MAX", "KIN_UNIT", "KinCraft", "KinCraftsSpec", "KinHead"]

KIN_KIND = "related_crafts"
KIN_CHAPTER = "kin"
KIN_SHARES_MAX = 6
KIN_UNIT = r"^[a-z0-9][a-z0-9-]*$"
CRAFT_PATH = r"^/crafts/[A-Za-z0-9-]+$"


class KinHead(ContractModel):
    title: str = Field(min_length=1, max_length=200)
    family: str | None = Field(default=None, max_length=200)


class KinCraft(ContractModel):
    name: str = Field(min_length=1, max_length=300)
    path: str = Field(pattern=CRAFT_PATH)
    place: str | None = Field(default=None, max_length=300)
    gi: bool
    monograph: bool
    shares: list[str] = Field(max_length=KIN_SHARES_MAX)
    sentence: str = Field(pattern=KIN_UNIT)


class KinCraftsSpec(ContractModel):
    head: KinHead
    crafts: list[KinCraft] = Field(min_length=1, max_length=SAME_FAMILY_MAX)

    @model_validator(mode="after")
    def _each_kin_craft_once(self) -> Self:
        paths = [craft.path for craft in self.crafts]
        if len(set(paths)) != len(paths):
            raise ValueError("a kin craft is shown once")
        sentences = [craft.sentence for craft in self.crafts]
        if len(set(sentences)) != len(sentences):
            raise ValueError("each kin craft carries its own cited sentence")
        return self
