import hashlib
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from app.api import mcp_tools
from app.api.mcp_lookup_tools import lookup_tools
from app.api.mcp_tool_base import ToolContext
from app.core.errors import ExternalFailure
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, READ_SCOPE
from app.models import User
from app.research.evidence import EvidenceItem, OpenAccessLocation, Quote, SearchQuery, SourceDocument
from app.research.fetcher import FetchedPage, FetchRequest, PageMetadata
from app.research.images import ImageCandidate, ImageQuery
from app.services.craft_resolver import CraftIndexStore
from app.services.source_lookup_calls import LookupDeps
from app.services.source_lookup_sources import LookupSources

SITE = "https://kalavigyan.example"
FETCHED_AT = datetime(2026, 11, 21, 8, 0, tzinfo=UTC)
PAGE_URL = "https://crafts.example.org/ajrakh/indigo"
PDF_URL = "https://repository.example.edu/ajrakh.pdf"
PAGE_TEXT = (
    "Ajrakh printing in Kutch\n"
    "The cloth is dyed in an indigo vat kept with lime and jaggery for several days.\n"
    "Printers re-\nprint the resist with a paste of lime and gum arabic before the second dyeing.\n"
    "\n"
    "“Mud resist” is called dabu by the printers of Rajasthan.\n"
)
PAGE_LINES = (
    "Ajrakh printing in Kutch",
    "The cloth is dyed in an indigo vat kept with lime and jaggery for several days.",
    "Printers reprint the resist with a paste of lime and gum arabic before the second dyeing.",
    '"Mud resist" is called dabu by the printers of Rajasthan.',
)


def page(url: str = PAGE_URL, text: str = PAGE_TEXT, **options: Any) -> FetchedPage:
    return FetchedPage(
        url=url,
        final_url=url,
        status=200,
        content_type=options.get("content_type", "text/html"),
        bytes=len(text.encode("utf-8")),
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        fetched_at=FETCHED_AT,
        text=text,
        truncated=False,
        metadata=PageMetadata(title=options.get("title", "Indigo in Ajrakh"), licence=options.get("licence")),
    )


def item(adapter: str, url: str, **options: Any) -> EvidenceItem:
    return EvidenceItem(
        id=f"{adapter}:{options.get('native', url)}",
        adapter=adapter,
        tier=options.get("tier", "T3"),
        source_type=options.get("source_type", "PAPER"),
        url=url,
        title=options.get("title", "Indigo dyeing in Kutch"),
        retrieved_at=FETCHED_AT,
        licence=options.get("licence"),
        doi=options.get("doi"),
        trust=options.get("trust", "A"),
        quotes=[Quote(text=text) for text in options.get("quotes", ())],
        external_ids=options.get("external_ids", {}),
    )


def document(found: EvidenceItem, text: str) -> SourceDocument:
    return SourceDocument(
        item=found,
        text=text,
        text_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        truncated=False,
        content="EXCERPT",
    )


class FakeFetcher:
    def __init__(self, pages: Mapping[str, FetchedPage | Exception]) -> None:
        self.pages = dict(pages)
        self.asked: list[str] = []

    async def fetch(self, request: FetchRequest) -> FetchedPage:
        self.asked.append(request.url)
        found = self.pages[request.url]
        if isinstance(found, Exception):
            raise found
        return found


@dataclass
class FakeSearcher:
    name: str
    found: Sequence[EvidenceItem] = ()
    failure: Exception | None = None
    documents: Mapping[str, SourceDocument | Exception] = field(default_factory=dict)
    tier: str = "T3"
    asked: list[str] = field(default_factory=list)

    async def search(self, query: SearchQuery, k: int) -> list[EvidenceItem]:
        self.asked.append(query.text)
        if self.failure is not None:
            raise self.failure
        return list(self.found)[:k]

    async def fetch(self, item_id: str) -> SourceDocument:
        found = self.documents.get(item_id)
        if found is None:
            raise ExternalFailure(f"{self.name} has no {item_id}", kind="not_found", service=self.name)
        if isinstance(found, Exception):
            raise found
        return found


class FakeLocator:
    name = "unpaywall"

    def __init__(self, copies: Mapping[str, OpenAccessLocation]) -> None:
        self.copies = dict(copies)
        self.asked: list[str] = []

    async def locate(self, doi: str) -> OpenAccessLocation:
        self.asked.append(doi)
        if doi not in self.copies:
            raise ExternalFailure("unpaywall has no record", kind="not_found", service=self.name)
        return self.copies[doi]


def open_location(doi: str, pdf_url: str, licence: str | None = "cc-by") -> OpenAccessLocation:
    return OpenAccessLocation(
        doi=doi,
        status="GREEN",
        pdf_url=pdf_url,
        licence=licence,
        host_type="REPOSITORY",
        checked_at=FETCHED_AT,
    )


@dataclass
class FakePictures:
    name: str
    found: Sequence[ImageCandidate] = ()
    asked: list[str] = field(default_factory=list)

    async def images(self, query: ImageQuery, k: int) -> list[ImageCandidate]:
        self.asked.append(query.text)
        return list(self.found)[:k]


@dataclass
class FakeArchiver:
    snapshot: str
    saved: list[str] = field(default_factory=list)

    async def save(self, url: str) -> str:
        self.saved.append(url)
        return self.snapshot


@dataclass
class FakeSnapshots:
    snapshot: str | None = None

    async def closest(self, url: str) -> str | None:
        return self.snapshot


class FakeSession:
    def __init__(self, scalar: Any = None, rows: Sequence[Any] = ()) -> None:
        self.scalar_value = scalar
        self.rows = list(rows)

    async def scalar(self, statement: Any) -> Any:
        return self.scalar_value

    async def scalars(self, statement: Any) -> list[Any]:
        return self.rows

    async def commit(self) -> None:
        return None

    async def rollback(self) -> None:
        return None


def person(role: str, number: int = 41) -> User:
    return User(id=uuid.UUID(int=number), name="Researcher", email=f"r{number}@example.org", role=role)


def tool_context(user: User | None, session: Any = None) -> ToolContext:
    scopes = frozenset({READ_SCOPE, CONTRIBUTE_SCOPE}) if user is not None else frozenset()
    return ToolContext(
        session=session or FakeSession(), index=CraftIndexStore(), site=SITE, user=user, scopes=scopes
    )


def deps(sources: LookupSources, tier: str = "NEW") -> LookupDeps:
    async def given() -> LookupSources:
        return sources

    async def tier_of(session: Any, user: User) -> str:
        return tier

    return LookupDeps(sources=given, tier=tier_of)


def serve(monkeypatch: Any, sources: LookupSources, tier: str = "NEW") -> None:
    tools = {tool.name: tool for tool in lookup_tools(deps(sources, tier))}
    monkeypatch.setattr(mcp_tools, "TOOLS", {**mcp_tools.TOOLS, **tools})


async def call(name: str, arguments: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    message = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    }
    reply = await mcp_tools.answer(message, context)
    assert reply is not None and "result" in reply, reply
    return reply["result"]
