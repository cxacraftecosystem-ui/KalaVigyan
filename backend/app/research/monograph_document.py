from __future__ import annotations

from typing import Any, Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, absent
from .coverage import FieldCoverage
from .monograph_page import MonographContent

__all__ = [
    "ENGLISH",
    "FRAGMENT_FILE_SUFFIX",
    "LANGUAGE_MAX_CHARS",
    "LANGUAGE_TAG",
    "MONOGRAPH_DOCUMENT_SCHEMA_VERSION",
    "SERVED_LANGUAGES",
    "SPEC_FILE_SUFFIX",
    "SUBJECT_KINDS",
    "MonographDocument",
    "fragment_file_name",
    "served_language",
    "spec_file_name",
]

MONOGRAPH_DOCUMENT_SCHEMA_VERSION = 1
SUBJECT_KINDS = ("craft", "family", "category")
ENGLISH = "en"
SERVED_LANGUAGES = (ENGLISH,)
LANGUAGE_TAG = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"
LANGUAGE_MAX_CHARS = 16
SPEC_FILE_SUFFIX = ".json"
FRAGMENT_FILE_SUFFIX = ".html"
LABEL_SEPARATOR = "/"
FILE_SEPARATOR = "__"


class MonographDocument(ContractModel):
    schema_version: Literal[1] = MONOGRAPH_DOCUMENT_SCHEMA_VERSION
    subject_kind: Literal[*SUBJECT_KINDS]
    subject_slug: str = Field(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9-]+$")
    language: str = Field(default=ENGLISH, max_length=LANGUAGE_MAX_CHARS, pattern=LANGUAGE_TAG)
    title: str = Field(min_length=1, max_length=300)
    version: int = Field(ge=1)
    content: MonographContent
    specs: dict[str, dict[str, Any]] = Field(default_factory=dict)
    fragments: dict[str, str] = Field(default_factory=dict)
    shell: str | None = None
    page_url: str
    coverage: FieldCoverage | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _each_component_drawn_once(self) -> Self:
        labels = {component.label for component in self.content.components}
        unknown = (set(self.specs) | set(self.fragments)) - labels
        if unknown:
            raise ValueError(f"specs or fragments name components the content lacks: {sorted(unknown)}")
        both = set(self.specs) & set(self.fragments)
        if both:
            raise ValueError(f"a component is drawn from a spec or a fragment, not both: {sorted(both)}")
        return self


def served_language(asked: str | None) -> str:
    wanted = (asked or ENGLISH).strip().lower()
    return wanted if wanted in SERVED_LANGUAGES else ENGLISH


def spec_file_name(label: str) -> str:
    return label.replace(LABEL_SEPARATOR, FILE_SEPARATOR) + SPEC_FILE_SUFFIX


def fragment_file_name(label: str) -> str:
    return label.replace(LABEL_SEPARATOR, FILE_SEPARATOR) + FRAGMENT_FILE_SUFFIX
