from __future__ import annotations

from typing import Literal

from pydantic import Field

from .base import ContractModel
from .vocabulary import CANONICAL_LANGUAGE, TextDirection

__all__ = ["SCRIPT_CODE", "DocumentTranslation"]

SCRIPT_CODE = r"^[A-Z][a-z]{3}$"


class DocumentTranslation(ContractModel):
    source_language: Literal["en"] = CANONICAL_LANGUAGE
    source_version: int = Field(ge=1)
    script: str = Field(pattern=SCRIPT_CODE)
    direction: TextDirection
    passages: int = Field(ge=0)
    translated: int = Field(ge=0)
    held: int = Field(ge=0)
