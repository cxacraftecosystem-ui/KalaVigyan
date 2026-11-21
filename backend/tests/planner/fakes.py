import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.core.errors import ExternalFailure
from app.research.evidence import EvidenceItem, OpenAccessLocation, SearchQuery, SourceDocument
from app.research.fetcher import FetchedPage, FetchRefused, FetchRequest
from app.research.planning import PlanRequest
from app.research.retrieval import ClaimHit, KnowledgeHits, KnowledgeQuery
from app.research.structured import StructuredReply
from app.sources.adapter import build_document

from ..research.fixtures import AJRAKH, RETRIEVED, evidence_item

CHECKED = datetime(2026, 11, 16, 10, 0, tzinfo=UTC)

TWO_FACET_PLAN = {
    "intent": "SCIENCE",
    "needsRegion": False,
    "facets": [
        {"type": "MATERIAL", "target": "alum"},
        {"type": "MECHANISM", "target": "mordant binding"},
    ],
    "queries": [
        {"facetIndex": 0, "tier": "T3", "text": "Ajrakh alum mordant"},
        {"facetIndex": 1, "tier": "T4", "text": "alizarin alum lake chemistry"},
    ],
}


def request(mode: str = "HYBRID", **changes: object) -> PlanRequest:
    fields: dict[str, object] = {
        "question": "Why does alum make Ajrakh red last?",
        "mode": mode,
        "craft": AJRAKH,
    }
    fields.update(changes)
    return PlanRequest.model_validate(fields)


@dataclass
class FakeModel:
    replies: list[str]
    degraded: bool = False
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls.append({"system": system, "user": user, "schema": schema})
        return StructuredReply(text=self.replies[len(self.calls) - 1], degraded=self.degraded)


def model_for(plan: Mapping[str, Any] = TWO_FACET_PLAN, *, degraded: bool = False) -> FakeModel:
    return FakeModel([json.dumps(plan)], degraded=degraded)


def claim(text: str, *, level: str = "PROVISIONAL", lexical: int | None = 1) -> ClaimHit:
    return ClaimHit(
        claim_id=uuid.uuid5(uuid.NAMESPACE_URL, text),
        text=text,
        level=level,
        subject_type="CONCEPT",
        subject_id=uuid.uuid5(uuid.NAMESPACE_DNS, text),
        score=0.03,
        lexical_rank=lexical,
        vector_rank=1,
    )


@dataclass
class FakeRetriever:
    claims_by_text: dict[str, list[ClaimHit]] = field(default_factory=dict)
    queries: list[KnowledgeQuery] = field(default_factory=list)

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        return KnowledgeHits(
            craft_slug=query.craft_slug, claims=tuple(self.claims_by_text.get(query.text, []))
        )


def scholarly(native: str, *, doi: str | None, trust: str = "A", adapter: str = "openalex") -> EvidenceItem:
    return evidence_item(
        id=f"{adapter}:{native}",
        adapter=adapter,
        url=f"https://doi.org/{doi}" if doi else f"https://works.example.org/{native}",
        title=f"Work {native}",
        doi=doi,
        trust=trust,
        quotes=[],
    )


def web_page(path: str, *, adapter: str = "searxng") -> EvidenceItem:
    url = f"https://crafts.example.org/{path}"
    return evidence_item(
        id=f"{adapter}:{url}",
        adapter=adapter,
        tier="T4",
        sourceType="WEB_PAGE",
        url=url,
        title=f"Page {path}",
        doi=None,
        licence=None,
        trust="C",
        quotes=[],
    )


@dataclass
class FakeAdapter:
    name: str
    tier: str
    results: list[EvidenceItem] = field(default_factory=list)
    texts: dict[str, str] = field(default_factory=dict)
    search_failure: ExternalFailure | None = None
    searched: list[tuple[str, int]] = field(default_factory=list)
    languages: list[str] = field(default_factory=list)
    fetched: list[str] = field(default_factory=list)

    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]:
        self.searched.append((query.text, k))
        self.languages.append(query.language)
        if self.search_failure is not None:
            raise self.search_failure
        return self.results[:k]

    async def fetch(self, item_id: str) -> SourceDocument:
        self.fetched.append(item_id)
        known = {item.id: item for item in self.results}
        if item_id not in self.texts:
            raise ExternalFailure(
                f"{self.name} has no text for {item_id}", kind="not_found", service=self.name
            )
        item = known.get(item_id) or self._referenced(item_id)
        return build_document(item, self.texts[item_id], "ABSTRACT")

    def _referenced(self, item_id: str) -> EvidenceItem:
        doi = item_id.split(":", 1)[1]
        return scholarly(doi, doi=doi, adapter=self.name)


@dataclass
class FakeLocator:
    open_copies: dict[str, str] = field(default_factory=dict)
    name: str = "unpaywall"
    asked: list[str] = field(default_factory=list)
    licence: str | None = "CC BY 4.0"
    version: str | None = None

    async def locate(self, doi: str) -> OpenAccessLocation:
        self.asked.append(doi)
        url = self.open_copies.get(doi)
        if url is None:
            return OpenAccessLocation(doi=doi, status="CLOSED", checked_at=CHECKED)
        return OpenAccessLocation(
            doi=doi,
            status="GREEN",
            pdf_url=url,
            licence=self.licence,
            version=self.version,
            host_type="REPOSITORY",
            checked_at=CHECKED,
        )


@dataclass
class FakeFetcher:
    pages: dict[str, str] = field(default_factory=dict)
    requests: list[str] = field(default_factory=list)

    async def fetch(self, request: FetchRequest) -> FetchedPage:
        self.requests.append(request.url)
        text = self.pages.get(request.url)
        if text is None:
            raise FetchRefused(request.url, "ROBOTS_DISALLOWED", "not served in the test")
        return FetchedPage.model_validate(
            {
                "url": request.url,
                "finalUrl": request.url,
                "status": 200,
                "contentType": "application/pdf",
                "bytes": len(text),
                "sha256": "c" * 64,
                "fetchedAt": RETRIEVED,
                "text": text,
                "truncated": False,
                "metadata": {},
            }
        )


def ids(entries: Sequence[Any]) -> list[str]:
    return [entry.item.id for entry in entries]
