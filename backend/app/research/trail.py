from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from .base import ContractModel, HttpsUrl
from .evidence import EVIDENCE_ID_MAX_CHARS

__all__ = [
    "PIECE_PREFIX",
    "STORED_SOURCE_PREFIX",
    "STORED_TRAIL_PREFIXES",
    "TRAIL_GROUPS",
    "TRAIL_GROUP_OF_SOURCE",
    "TRAIL_KEY_PATTERN",
    "TRAIL_PUBLISHER_MAX_CHARS",
    "TRAIL_STAGES",
    "TRAIL_TITLE_MAX_CHARS",
    "PacedEvent",
    "ServiceWait",
    "TrailEvent",
]

TRAIL_STAGES = ("FOUND", "READ", "QUOTED")
TRAIL_GROUPS = ("PAPERS", "ENCYCLOPAEDIA", "DATASETS", "WEB", "STORED")
TRAIL_KEY_PATTERN = r"^[a-z][a-z0-9_]{1,39}:\S+$"
STORED_SOURCE_PREFIX = "source"
PIECE_PREFIX = "piece"
STORED_TRAIL_PREFIXES = (STORED_SOURCE_PREFIX, PIECE_PREFIX)
TRAIL_TITLE_MAX_CHARS = 1000
TRAIL_PUBLISHER_MAX_CHARS = 300
SERVICE_NAME_MAX_CHARS = 40
TRAIL_GROUP_OF_SOURCE: Mapping[str, str] = MappingProxyType(
    {
        "PAPER": "PAPERS",
        "BOOK": "PAPERS",
        "BOOK_CHAPTER": "PAPERS",
        "GI_JOURNAL": "PAPERS",
        "GOVERNMENT_REPORT": "PAPERS",
        "FIELD_TESTIMONY": "PAPERS",
        "ENCYCLOPEDIA": "ENCYCLOPAEDIA",
        "DATASET": "DATASETS",
        "COMPOUND_RECORD": "DATASETS",
        "WEB_PAGE": "WEB",
        "MEDIA": "WEB",
        "OTHER": "WEB",
    }
)

TrailStage = Literal[*TRAIL_STAGES]
TrailGroup = Literal[*TRAIL_GROUPS]


class TrailEvent(ContractModel):
    key: str = Field(min_length=3, max_length=EVIDENCE_ID_MAX_CHARS, pattern=TRAIL_KEY_PATTERN)
    stage: TrailStage
    group: TrailGroup
    title: str = Field(min_length=1, max_length=TRAIL_TITLE_MAX_CHARS)
    url: HttpsUrl | None
    publisher: str | None = Field(max_length=TRAIL_PUBLISHER_MAX_CHARS)
    year: int | None
    source_id: str | None
    stored_at: AwareDatetime | None

    @model_validator(mode="after")
    def _stored_knowledge_is_marked_as_such(self) -> Self:
        prefix, _, rest = self.key.partition(":")
        stored = prefix in STORED_TRAIL_PREFIXES
        if stored != (self.group == "STORED"):
            raise ValueError(f"trail {self.key} is STORED exactly when it is a stored source or piece")
        if stored and self.stage == "READ":
            raise ValueError(f"trail {self.key} is stored knowledge, found or quoted, never read again")
        if (prefix == PIECE_PREFIX) != (self.stored_at is not None):
            raise ValueError(
                f"trail {self.key} carries the date of earlier research exactly when it is a piece"
            )
        if prefix == "source" and self.source_id != rest:
            raise ValueError(f"trail {self.key} names its stored source")
        return self


class ServiceWait(ContractModel):
    service: str = Field(min_length=1, max_length=SERVICE_NAME_MAX_CHARS)
    waited_seconds: float = Field(ge=0)
    waited_requests: int = Field(ge=0)
    refusals: int = Field(ge=0)
    unsent: int = Field(ge=0)


class PacedEvent(ContractModel):
    services: list[ServiceWait] = Field(min_length=1)
