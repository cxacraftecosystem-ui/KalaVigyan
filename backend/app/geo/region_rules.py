from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.research.base import ContractModel

__all__ = ["REGION_RULES_FILE", "RegionRules", "region_rules"]

REGION_RULES_FILE = Path(__file__).with_name("region_rules.json")
ABOUT_MIN_CHARS = 40


class RegionRules(ContractModel):
    schema_version: Literal[1]
    about: str = Field(min_length=ABOUT_MIN_CHARS)
    lithology_twin_prefix: str = Field(min_length=1)
    absent_means_zero: Mapping[str, str] = Field(min_length=1)


@lru_cache(maxsize=1)
def region_rules() -> RegionRules:
    return RegionRules.model_validate_json(REGION_RULES_FILE.read_text(encoding="utf-8"))
