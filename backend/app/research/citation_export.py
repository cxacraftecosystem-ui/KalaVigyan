from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Literal, Self

from pydantic import Field, StringConstraints, model_validator

from .base import ContractModel, HttpsUrl, absent
from .datasets import DATASET_CODE_PATTERN

__all__ = [
    "BIBTEX_TYPES",
    "CITATION_FORMATS",
    "CITATION_KEY_PREFIX",
    "CSL_TYPES",
    "DATASET_ROW_KIND",
    "RIS_END",
    "RIS_TYPES",
    "CitationEntry",
    "CitationExport",
    "CslDate",
    "CslItem",
    "CslName",
    "citation_key",
]

CITATION_FORMATS = ("bib", "ris", "txt", "json")
CITATION_KEY_PREFIX = "kv"
DATASET_ROW_KIND = "DATASET"
RIS_END = "ER  - \r\n"
CSL_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "PAPER": "article-journal",
        "BOOK": "book",
        "BOOK_CHAPTER": "chapter",
        "WEB_PAGE": "webpage",
        "ENCYCLOPEDIA": "entry-encyclopedia",
        "DATASET": "dataset",
        "GI_JOURNAL": "document",
        "GOVERNMENT_REPORT": "report",
        "COMPOUND_RECORD": "dataset",
        "FIELD_TESTIMONY": "interview",
        "MEDIA": "graphic",
        "OTHER": "document",
    }
)
BIBTEX_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "PAPER": "article",
        "BOOK": "book",
        "BOOK_CHAPTER": "incollection",
        "WEB_PAGE": "misc",
        "ENCYCLOPEDIA": "misc",
        "DATASET": "misc",
        "GI_JOURNAL": "misc",
        "GOVERNMENT_REPORT": "techreport",
        "COMPOUND_RECORD": "misc",
        "FIELD_TESTIMONY": "misc",
        "MEDIA": "misc",
        "OTHER": "misc",
    }
)
RIS_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "PAPER": "JOUR",
        "BOOK": "BOOK",
        "BOOK_CHAPTER": "CHAP",
        "WEB_PAGE": "ELEC",
        "ENCYCLOPEDIA": "ENCYC",
        "DATASET": "DATA",
        "GI_JOURNAL": "GOVDOC",
        "GOVERNMENT_REPORT": "RPRT",
        "COMPOUND_RECORD": "DBASE",
        "FIELD_TESTIMONY": "PCOMM",
        "MEDIA": "ART",
        "OTHER": "GEN",
    }
)

CslType = Literal[*dict.fromkeys(CSL_TYPES.values())]
Formatted = Annotated[str, StringConstraints(strip_whitespace=False, min_length=1)]


class CslName(ContractModel):
    literal: str = Field(min_length=1)


class CslDate(ContractModel):
    date_parts: list[list[int]] = Field(alias="date-parts", min_length=1, max_length=1)


class CslItem(ContractModel):
    id: str = Field(pattern=rf"^{CITATION_KEY_PREFIX}[1-9]\d*$")
    type: CslType
    title: str = Field(min_length=1)
    author: list[CslName]
    issued: CslDate | None = Field(default=None, exclude_if=absent)
    accessed: CslDate | None = Field(default=None, exclude_if=absent)
    container_title: str | None = Field(
        default=None, alias="container-title", min_length=1, exclude_if=absent
    )
    publisher: str | None = Field(default=None, min_length=1, exclude_if=absent)
    version: str | None = Field(default=None, min_length=1, exclude_if=absent)
    doi: str | None = Field(default=None, alias="DOI", min_length=1, exclude_if=absent)
    url: HttpsUrl | None = Field(default=None, alias="URL", exclude_if=absent)


class CitationEntry(ContractModel):
    number: int = Field(ge=1)
    source_id: str | None = Field(min_length=1)
    dataset_code: str | None = Field(pattern=DATASET_CODE_PATTERN, max_length=80)
    csl: CslItem
    apa: str = Field(min_length=1)
    bibtex: Formatted
    ris: Formatted

    @model_validator(mode="after")
    def _one_cited_thing_under_one_key(self) -> Self:
        key = citation_key(self.number)
        if (self.source_id is None) == (self.dataset_code is None):
            raise ValueError(f"citation {self.number} names a source or a dataset row, not both")
        if self.csl.id != key or not re.match(rf"^@[a-z]+\{{{key},\n", self.bibtex):
            raise ValueError(f"citation {self.number} is keyed {key} in every format")
        if (
            not self.ris.startswith("TY  - ")
            or not self.ris.endswith(RIS_END)
            or "\n" in self.ris.replace("\r\n", "")
        ):
            raise ValueError(f"citation {self.number} is one RIS record with CRLF line ends")
        return self


class CitationExport(ContractModel):
    schema_version: Literal[1]
    explainer_id: uuid.UUID
    version: int = Field(ge=1)
    entries: list[CitationEntry] = Field(min_length=1)

    @model_validator(mode="after")
    def _numbered_as_the_reader_sees_them(self) -> Self:
        if [entry.number for entry in self.entries] != list(range(1, len(self.entries) + 1)):
            raise ValueError("citations are numbered 1 to n, as the explainer numbers them")
        cited = [entry.source_id or f"dataset:{entry.dataset_code}" for entry in self.entries]
        if len(set(cited)) != len(cited):
            raise ValueError("each source and dataset row is cited once")
        return self


def citation_key(number: int) -> str:
    return f"{CITATION_KEY_PREFIX}{number}"
