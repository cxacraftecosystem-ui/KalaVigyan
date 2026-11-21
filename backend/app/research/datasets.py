from __future__ import annotations

import datetime
from collections.abc import Iterable
from typing import Literal

from pydantic import Field

from .base import ContractModel, HttpsUrl, absent

__all__ = [
    "BOUNDARY_CAPTION",
    "BOUNDARY_DATASET_CODE",
    "DATASET_BUILDS",
    "DATASET_CODE_PATTERN",
    "DOI_PATTERN",
    "SHA256_PATTERN",
    "DatasetEntry",
    "DatasetRef",
    "dataset_codes_problems",
]

DATASET_CODE_PATTERN = r"^[A-Z0-9]+(?:_[A-Z0-9]+)*$"
DOI_PATTERN = r"^10\.\d{4,9}/\S+$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"
DATASET_BUILDS = ("geo-etl", "maplayers", "contributed")
BOUNDARY_DATASET_CODE = "DR_DISTRICT_SHAPES"
BOUNDARY_CAPTION = (
    "External boundaries of India as depicted by Survey of India. District boundaries are indicative."
)


class DatasetRef(ContractModel):
    code: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1)
    publisher: str | None
    edition: str = Field(min_length=1)
    period: str = Field(min_length=1)
    native_resolution: str = Field(min_length=1)
    licence: str = Field(min_length=1)
    licence_url: HttpsUrl | None
    attribution: str | None
    citation: str | None
    url: HttpsUrl | None
    version: str | None = Field(default=None, exclude_if=absent)
    crs: str | None = Field(default=None, exclude_if=absent)
    redistributable: bool | None = Field(default=None, exclude_if=absent)
    doi: str | None = Field(default=None, pattern=DOI_PATTERN, exclude_if=absent)
    landing_url: HttpsUrl | None = Field(default=None, exclude_if=absent)
    read_on: datetime.date | None = Field(default=None, exclude_if=absent)
    sha256: str | None = Field(default=None, pattern=SHA256_PATTERN, exclude_if=absent)


class DatasetEntry(ContractModel):
    code: str = Field(pattern=DATASET_CODE_PATTERN, max_length=80)
    title: str = Field(min_length=1, max_length=300)
    publisher: str = Field(min_length=1, max_length=300)
    edition: str = Field(min_length=1, max_length=120)
    version: str = Field(min_length=1, max_length=120)
    period: str = Field(min_length=1, max_length=120)
    native_resolution: str = Field(min_length=1, max_length=120)
    crs: str = Field(min_length=1, max_length=120)
    licence: str = Field(min_length=1, max_length=200)
    licence_url: HttpsUrl | None
    attribution: str | None
    redistributable: bool
    citation: str | None
    doi: str | None = Field(pattern=DOI_PATTERN)
    landing_url: HttpsUrl
    url: HttpsUrl
    build: Literal[*DATASET_BUILDS]


def dataset_codes_problems(owner: str, datasets: Iterable[DatasetRef], needed: Iterable[str]) -> list[str]:
    codes = [dataset.code for dataset in datasets]
    problems = []
    if len(set(codes)) != len(codes):
        problems.append(f"{owner} cites each dataset once")
    missing = [code for code in dict.fromkeys(needed) if code not in codes]
    if missing:
        problems.append(f"{owner} cites the dataset rows it draws: {', '.join(missing)} missing")
    return problems
