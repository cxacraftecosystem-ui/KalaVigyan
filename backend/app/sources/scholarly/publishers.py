from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import EvidenceItem, OpenAccessLocator, SourceDocument

from ..adapter import build_document

__all__ = ["FULL_TEXT_FROM", "PublisherFullText", "PublisherReader", "PublisherText", "doi_prefix"]

FULL_TEXT_FROM = "full_text_from"


@dataclass(frozen=True)
class PublisherText:
    text: str
    licence: str


class PublisherReader(Protocol):
    name: str
    doi_prefixes: tuple[str, ...]

    async def full_text(self, doi: str) -> PublisherText: ...


class PublisherFullText:
    name = "publisher_full_text"

    def __init__(self, locator: OpenAccessLocator, readers: Sequence[PublisherReader]) -> None:
        if not readers:
            raise ValueError("publisher full text needs at least one publisher whose key is set")
        self._locator = locator
        self._readers = tuple(readers)

    @property
    def publishers(self) -> tuple[str, ...]:
        return tuple(reader.name for reader in self._readers)

    def holds(self, doi: str) -> bool:
        return self._reader(doi) is not None

    async def read(self, item: EvidenceItem) -> SourceDocument:
        if item.doi is None:
            raise InvalidInput(f"{item.id} has no DOI, so no publisher full text can be asked for")
        reader = self._reader(item.doi)
        if reader is None:
            raise self._failure(f"no publisher whose key is set holds {item.doi}")
        location = await self._locator.locate(item.doi)
        if location.is_open:
            raise self._failure(f"{self._locator.name} reports an open copy of {item.doi}, read in its place")
        found = await reader.full_text(item.doi)
        read = item.model_copy(
            update={
                "licence": found.licence,
                "external_ids": {**item.external_ids, FULL_TEXT_FROM: reader.name},
            }
        )
        return build_document(read, found.text, "FULL_TEXT")

    def _reader(self, doi: str) -> PublisherReader | None:
        prefix = doi_prefix(doi)
        return next((reader for reader in self._readers if prefix in reader.doi_prefixes), None)

    def _failure(self, message: str) -> ExternalFailure:
        return ExternalFailure(message, kind="not_found", service=self.name)


def doi_prefix(doi: str) -> str:
    return doi.split("/", 1)[0].lower()
