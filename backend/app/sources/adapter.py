from __future__ import annotations

import hashlib
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar, Literal

from pydantic import ValidationError

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import SEARCH_MAX_K, EvidenceItem, SearchQuery, SourceDocument
from app.research.fetcher import FETCH_TEXT_MAX_CHARS
from app.research.storable import storable_text
from app.research.vocabulary import LiveTier

from .http import SourceHttp
from .records import UnusableRecord, published_since

__all__ = [
    "Clock",
    "HttpSourceAdapter",
    "build_document",
    "checked_k",
    "native_id",
    "usable_records",
    "utc_now",
]

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]
DocumentContent = Literal["FULL_TEXT", "ABSTRACT", "EXCERPT"]


def utc_now() -> datetime:
    return datetime.now(UTC)


class HttpSourceAdapter(ABC):
    name: ClassVar[str]
    tier: ClassVar[LiveTier] = "T3"

    def __init__(self, http: SourceHttp, *, clock: Clock = utc_now) -> None:
        self.http = http
        self.clock = clock

    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]:
        wanted = checked_k(k)
        records = await self._search_records(query, wanted)
        retrieved_at = self.clock()
        items = self._usable_items(records, retrieved_at)
        if query.freshness_days is not None:
            cutoff = (retrieved_at - timedelta(days=query.freshness_days)).date()
            items = [item for item in items if published_since(item.published, cutoff)]
        return items[:wanted]

    async def fetch(self, item_id: str) -> SourceDocument:
        return await self._fetch_document(native_id(self.name, item_id), self.clock())

    @abstractmethod
    async def _search_records(self, query: SearchQuery, k: int) -> list[Any]: ...

    @abstractmethod
    def _item(self, record: Any, retrieved_at: datetime) -> EvidenceItem: ...

    @abstractmethod
    async def _fetch_document(self, native: str, retrieved_at: datetime) -> SourceDocument: ...

    def _usable_items(self, records: Iterable[Any], retrieved_at: datetime) -> list[EvidenceItem]:
        return usable_records(self.name, records, lambda record: self._item(record, retrieved_at))

    def _not_found(self, native: str, what: str) -> ExternalFailure:
        return ExternalFailure(f"{self.name} has {what} for {native}", kind="not_found", service=self.name)


def usable_records[T](service: str, records: Iterable[Any], build: Callable[[Any], T]) -> list[T]:
    kept: list[T] = []
    for position, record in enumerate(records):
        try:
            kept.append(build(record))
        except UnusableRecord as error:
            logger.warning("%s left out result %d: %s", service, position, error)
        except ValidationError as error:
            fields = sorted({".".join(str(p) for p in e["loc"]) for e in error.errors()})
            logger.warning("%s left out result %d: invalid %s", service, position, ", ".join(fields))
    return kept


def checked_k(k: int) -> int:
    if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= SEARCH_MAX_K:
        raise InvalidInput(f"k must be an integer from 1 to {SEARCH_MAX_K}, not {k!r}")
    return k


def native_id(adapter: str, item_id: str) -> str:
    prefix = f"{adapter}:"
    if not item_id.startswith(prefix) or len(item_id) == len(prefix):
        raise InvalidInput(f"{item_id!r} is not an id of the {adapter} adapter")
    return item_id[len(prefix) :]


def build_document(
    item: EvidenceItem, text: str, content: DocumentContent, *, truncated: bool = False
) -> SourceDocument:
    storable = storable_text(text).strip()
    kept = storable[:FETCH_TEXT_MAX_CHARS].rstrip()
    try:
        return SourceDocument(
            item=item,
            text=kept,
            text_sha256=hashlib.sha256(kept.encode("utf-8")).hexdigest(),
            truncated=truncated or len(storable) > FETCH_TEXT_MAX_CHARS,
            content=content,
        )
    except ValidationError as error:
        problems = "; ".join(problem["msg"] for problem in error.errors())
        raise ExternalFailure(
            f"{item.id} gives no usable document: {problems}", service=item.adapter
        ) from error
