from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.core.errors import InvalidInput
from app.curation.check_file import CheckFile
from app.curation.dossier import Dossier
from app.research.blocks import ProseBlock

from .curated_category_index import CuratedCategoryPage
from .curated_index import CuratedPage

__all__ = [
    "CLAIM_COLUMNS",
    "GI_COLUMNS",
    "MARKER_COLUMNS",
    "MEDIA_COLUMNS",
    "PRICE_COLUMNS",
    "QUOTE_COLUMNS",
    "SOURCE_COLUMNS",
    "STAGE_COLUMNS",
    "USE_COLUMNS",
    "WORKFORCE_COLUMNS",
    "GitDossier",
    "PieceSentence",
    "Row",
    "StoredCuration",
    "StoredMarket",
    "guided",
    "id_number",
    "keyed",
    "piece_sentences",
    "projected",
]

Row = Mapping[str, Any]

CLAIM_COLUMNS = ("id", "subjectId", "text", "field", "evidenceLevel", "sensitivity", "status")
MARKER_COLUMNS = ("claimId", "key", "discipline")
QUOTE_COLUMNS = ("claimId", "sourceId", "locator", "quote", "quoteCheck", "foundBy")
SOURCE_COLUMNS = (
    "id",
    "kind",
    "evidenceKind",
    "title",
    "authors",
    "publisher",
    "year",
    "url",
    "doi",
    "licence",
    "reliability",
    "retrievedAt",
    "externalIds",
)
STAGE_COLUMNS = ("id", "name", "stageType")
USE_COLUMNS = ("stageId", "materialId", "claimId")
MEDIA_COLUMNS = ("id", "pageUrl", "imageUrl", "author", "licence", "licenceUrl")
GI_COLUMNS = (
    "applicationNumber",
    "certificateNumber",
    "filedOn",
    "registeredOn",
    "journalIssue",
    "proprietors",
    "authorisedUserCount",
    "claimIds",
    "imitationClaimIds",
)
PRICE_COLUMNS = ("id", "claimId", "pricedOn", "placeName")
WORKFORCE_COLUMNS = ("claimId", "year")
EMPTY: Mapping[uuid.UUID, Row] = MappingProxyType({})


@dataclass(frozen=True)
class GitDossier:
    file: str
    text: str
    dossier: Dossier
    check: CheckFile | None


@dataclass(frozen=True)
class PieceSentence:
    id: str
    text: str
    claim_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class StoredMarket:
    gi: Row | None = None
    prices: tuple[Row, ...] = ()
    workforce: tuple[Row, ...] = ()


@dataclass(frozen=True)
class StoredCuration:
    slug: str
    scope: str
    page: CuratedPage | CuratedCategoryPage
    claims: Mapping[uuid.UUID, Row]
    markers: Mapping[uuid.UUID, Row]
    quotes: tuple[Row, ...]
    sources: Mapping[uuid.UUID, Row]
    subjects: Mapping[uuid.UUID, str | None]
    media: Mapping[uuid.UUID, Row]
    sentences: Mapping[uuid.UUID, tuple[PieceSentence, ...]]
    claim_order: tuple[uuid.UUID, ...] = ()
    stages: Mapping[uuid.UUID, Row] = field(default_factory=lambda: EMPTY)
    uses: tuple[Row, ...] = ()
    market: StoredMarket = field(default_factory=StoredMarket)


def id_number(key: str) -> int:
    return int(key[1:])


def keyed(claim_ids: Iterable[uuid.UUID], keys: Mapping[uuid.UUID, str]) -> list[str]:
    listed = list(claim_ids)
    unknown = [str(claim_id) for claim_id in listed if claim_id not in keys]
    if unknown:
        raise InvalidInput(f"the stored record cites claims the dossier does not hold: {', '.join(unknown)}")
    return [keys[claim_id] for claim_id in listed]


def guided[T, K](
    items: Iterable[T],
    identity: Callable[[T], K],
    guides: Sequence[Sequence[K]],
    fallback: Callable[[T], Any],
) -> list[T]:
    positions = [{known: index for index, known in enumerate(guide)} for guide in guides]

    def rank(item: T) -> tuple[int, int, Any]:
        found = identity(item)
        tier = next((tier for tier, position in enumerate(positions) if found in position), len(positions))
        place = positions[tier][found] if tier < len(positions) else 0
        return tier, place, fallback(item)

    return sorted(items, key=rank)


def projected(rows: Iterable[Row], columns: tuple[str, ...]) -> tuple[dict[str, Any], ...]:
    found = []
    for row in rows:
        missing = [column for column in columns if column not in row]
        if missing:
            raise InvalidInput(f"a stored row lacks the columns the export reads: {', '.join(missing)}")
        found.append({column: row[column] for column in columns})
    return tuple(found)


def piece_sentences(block: ProseBlock) -> tuple[PieceSentence, ...]:
    return tuple(
        PieceSentence(
            id=sentence.id,
            text=sentence.text,
            claim_ids=tuple(dict.fromkeys(uuid.UUID(citation.claim_id) for citation in sentence.citations)),
        )
        for sentence in block.sentences
    )
