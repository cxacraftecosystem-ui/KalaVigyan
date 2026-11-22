import asyncio
import json
import re
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.composer.composer import ModelComposer
from app.composer.translation import ModelTranslator
from app.models import ClaimSource, Source
from app.planner.reading import ReadCache
from app.planner.understanding import ModelUnderstander
from app.providers.router import RouterError
from app.research.blocks import ImagesBlock
from app.research.composition import ComposedAnswer
from app.research.crafts import CraftCandidate, CraftQuery, CraftRef, CraftResolution, MatchReason
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.explainer import Explainer
from app.research.explainer_versions import VersionMark
from app.research.image_relevance import ClaimText
from app.research.planning import PlanRequest
from app.research.sections import AnswerPlans
from app.research.stream import ResearchProgress, event_stream
from app.research.structured import StructuredReply
from app.research.term_marking import GlossaryEntry
from app.research.understanding import Understanding
from app.science.records import ProcessRecords
from app.services import knowledge_view
from app.services.answer_events import CitedClaims, cited_claims
from app.services.answer_translation import AnswerTranslation
from app.services.answering import AnswerAsk, AnswerPipeline, answer_question
from app.services.research_write_back import sentence_claim_ids
from app.services.section_enrichment import PICTURES_WAIT_SECONDS, EnrichmentTools
from app.services.section_images import IMAGE_SEARCH_SECONDS, SectionImages, SectionImagesAsk

from ..composer.fixtures import ALUM_CLAIM_ID, GUESS_CLAIM_ID, pack
from ..images.fakes import FakeMediaStore, FakeSource, candidate
from ..planner.fakes import FakeModel
from ..research.fixtures import AJRAKH
from .piece_fakes import MemoryPieces
from .written_fakes import written_research

ANSWER_ID = uuid.UUID("0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9")
WRITTEN_LAKE_ID = uuid.UUID("6c1e0f2a-3b4d-4e5f-8a9b-0c1d2e3f4a5b")
WRITTEN_WASH_ID = uuid.UUID("8d2f1a3b-4c5e-4f60-9b1c-2d3e4f5a6b7c")
BOOK_ID = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000001")
LAKE_ID = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000002")
WEB_ID = uuid.UUID("1a2b3c4d-0000-4000-8000-000000000003")

BOOK = Source(
    id=BOOK_ID,
    kind="BOOK",
    title="Ajrakh: the printed cloth of Kutch",
    authors=["A. Author"],
    year=2016,
    doi=None,
    url=None,
    publisher="Mapin",
    licence=None,
    attribution=None,
    reliability="A",
)
LAKE = Source(
    id=LAKE_ID,
    kind="PAPER",
    title="Alizarin lakes on cotton",
    authors=["A. Author"],
    year=2019,
    doi="10.1000/lake",
    url="https://doi.org/10.1000/lake",
    publisher="Journal of Dye Chemistry",
    licence="CC BY 4.0",
    attribution=None,
    reliability="B",
)
WEB = Source(
    id=WEB_ID,
    kind="WEB_PAGE",
    title="Ajrakh fastness notes",
    authors=[],
    year=None,
    doi=None,
    url="https://crafts.example.org/ajrakh",
    publisher=None,
    licence=None,
    attribution=None,
    reliability="C",
)


def stored_view(
    claim_id: uuid.UUID,
    text: str,
    level: str,
    cite: tuple[int, Source, str | None, str | None],
    *,
    concept_id: uuid.UUID | None = None,
) -> knowledge_view.ClaimView:
    number, source, quote, locator = cite
    row = ClaimSource(
        id=uuid.UUID(f"c0000000-0000-4000-8000-{number:012d}"),
        claimId=claim_id,
        sourceId=source.id,
        quote=quote,
        locator=locator,
    )
    return knowledge_view.ClaimView(
        claim_id, text, level, "MATERIAL", concept_id, citations=[knowledge_view.citation(row, level)]
    )


VIEWS = (
    stored_view(
        ALUM_CLAIM_ID,
        "Alum is the mordant that binds alizarin to cotton in Ajrakh.",
        "REVIEWED",
        (1, BOOK, "Alum is the mordant", "p. 41"),
    ),
    stored_view(
        WRITTEN_LAKE_ID,
        "Mordant baths held 8 g/L alum and were heated to 60 °C.",
        "PROVISIONAL",
        (2, LAKE, "Mordanting baths of 8 g/L alum were heated to 60 °C", None),
    ),
    stored_view(
        WRITTEN_WASH_ID,
        "The red lake withstood 20 washes.",
        "PROVISIONAL",
        (3, WEB, "the lake withstood 20 washes", None),
    ),
    stored_view(
        GUESS_CLAIM_ID,
        "Lime in the wash water may brighten the red.",
        "HYPOTHESIS",
        (4, BOOK, None, None),
    ),
)
SOURCES = {BOOK_ID: BOOK, LAKE_ID: LAKE, WEB_ID: WEB}
WRITTEN_IDS = {VIEWS[1].text: WRITTEN_LAKE_ID, VIEWS[2].text: WRITTEN_WASH_ID}
SECTION_LINE = re.compile(r"^Section: (?P<title>.+) \(", re.MULTILINE)
GLOSSARY = (
    GlossaryEntry("alum", ("alum", "fatakdi")),
    GlossaryEntry("alizarin", ("alizarin",)),
    GlossaryEntry("cotton", ("cotton",)),
)
MORDANT_BATH = candidate(
    "commons", 1, "Alum mordant bath for alizarin dyeing", licence="CC BY-SA 4.0", author="A. Dyer"
)
WASHED_LAKE = candidate(
    "searxng", 2, "Red alizarin lake after many washes", licence=None, author=None, credit="Crafts Museum"
)


def resolved(craft: Any = AJRAKH) -> CraftResolution:
    reason = MatchReason(kind="EXACT_NAME", matched=craft.name, score=1.0)
    return CraftResolution(
        status="RESOLVED",
        craft=craft,
        candidates=[CraftCandidate(craft=craft, score=1.0, reasons=[reason])],
        normalised="kutch ajrakh",
        script="Latn",
    )


@dataclass
class FakeStore:
    stored: CitedClaims = field(default_factory=CitedClaims)
    records: ProcessRecords | None = None
    begun: list[tuple[AnswerAsk, Understanding]] = field(default_factory=list)
    kept: list[tuple[uuid.UUID, EvidencePack, ComposedAnswer]] = field(default_factory=list)
    finished: list[dict[str, Any]] = field(default_factory=list)
    asked_for: list[list[uuid.UUID]] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    modes: list[str] = field(default_factory=list)
    answer_id: uuid.UUID = ANSWER_ID
    written: Mapping[str, uuid.UUID] = field(default_factory=lambda: dict(WRITTEN_IDS))

    @property
    def understood(self) -> list[Understanding]:
        return [understanding for _, understanding in self.begun]

    async def stored_claims(self, craft_slug: str, question: str, mode: str) -> CitedClaims:
        assert craft_slug == AJRAKH.slug
        self.questions.append(question)
        self.modes.append(mode)
        return self.stored

    async def begin(self, ask: AnswerAsk, understanding: Understanding) -> uuid.UUID:
        self.begun.append((ask, understanding))
        return self.answer_id

    async def keep(
        self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer
    ) -> tuple[tuple[uuid.UUID, ...], ...]:
        self.kept.append((answer_id, pack, composed))
        return sentence_claim_ids(composed, written_research(pack, composed, answer_id, self.written))

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims:
        wanted = list(claim_ids)
        self.asked_for.append(wanted)
        return cited_claims([view for view in VIEWS if view.id in wanted], SOURCES)

    async def process(self, craft_slug: str) -> ProcessRecords | None:
        return self.records

    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[Any] = (),
        steps: Sequence[Any] = (),
    ) -> None:
        self.finished.append(
            {
                "answer_id": answer_id,
                "plans": plans,
                "claim_ids": claim_ids,
                "explainer": explainer,
                "version": version,
                "steps": list(steps),
            }
        )


@dataclass
class FakeResearch:
    pack: EvidencePack = field(default_factory=pack)
    steps: Sequence[tuple[str, int]] = (("SEARCHING_STORED", 1), ("RESEARCHING", 2), ("READING", 4))
    requests: list[PlanRequest] = field(default_factory=list)
    failure: Exception | None = None
    packs: Mapping[str, Sequence[EvidencePack]] = field(default_factory=dict)
    reads: list[ReadCache | None] = field(default_factory=list)

    async def __call__(
        self,
        request: PlanRequest,
        progress: ResearchProgress,
        trail: ResearchTrail,
        *,
        reads: ReadCache | None = None,
    ) -> EvidencePack:
        self.requests.append(request)
        self.reads.append(reads)
        found = self._pack(request)
        for step, count in self.steps:
            await progress(step, count)
            if step == "READING" and found.evidence:
                await trail.found(found.evidence)
        if self.failure is not None:
            raise self.failure
        for document in found.documents:
            await trail.read(document)
        return found

    def _pack(self, request: PlanRequest) -> EvidencePack:
        given = self.packs.get(request.focus or "", ())
        asked = sum(1 for earlier in self.requests if earlier.focus == request.focus)
        return given[asked - 1] if asked <= len(given) else self.pack


@dataclass
class SectionModel:
    replies: Mapping[str, Sequence[str]]
    gates: Mapping[str, asyncio.Event] = field(default_factory=dict)
    calls: list[dict[str, Any]] = field(default_factory=list)
    answered: list[str] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        found = SECTION_LINE.search(user)
        title = found.group("title") if found else ""
        self.calls.append({"title": title, "system": system, "user": user, "schema": schema})
        if title in self.gates:
            await self.gates[title].wait()
        count = sum(1 for call in self.calls if call["title"] == title)
        self.answered.append(title)
        return StructuredReply(text=self.replies[title][count - 1], degraded=False)


@dataclass
class MemoryCache:
    rows: dict[tuple[uuid.UUID, str], tuple[str, str]] = field(default_factory=dict)

    async def known(self, language: str, texts: Mapping[uuid.UUID, str]) -> dict[uuid.UUID, str]:
        found = {claim_id: self.rows.get((claim_id, language)) for claim_id in texts}
        return {claim_id: row[1] for claim_id, row in found.items() if row and row[0] == texts[claim_id]}

    async def remember(self, language: str, entries: Mapping[uuid.UUID, tuple[str, str]]) -> None:
        self.rows.update({(claim_id, language): entry for claim_id, entry in entries.items()})


def translation(model: FakeModel | None = None, cache: MemoryCache | None = None) -> AnswerTranslation:
    return AnswerTranslation(
        translator=ModelTranslator(model=model or FakeModel([])), cache=cache or MemoryCache()
    )


UNDERSTOOD_REPLY = {
    "craft": "",
    "craftNames": [],
    "disciplines": ["CHEMISTRY"],
    "seats": ["CHEMIST"],
}
SPENT = "The monthly AI budget has been reached. Verified answers from stored knowledge still work."


@dataclass
class SpentModel:
    calls: int = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        raise RouterError("ceiling", SPENT, reason="MONTHLY_CEILING")


@dataclass
class FakeEnrichment:
    entries: Sequence[GlossaryEntry] = ()
    sources: Sequence[FakeSource] = ()
    glossary_failure: Exception | None = None
    wait_seconds: float = PICTURES_WAIT_SECONDS
    search_seconds: float = IMAGE_SEARCH_SECONDS
    media: FakeMediaStore = field(
        default_factory=lambda: FakeMediaStore({view.id: ClaimText(view.id, view.text) for view in VIEWS})
    )
    crafts: list[str] = field(default_factory=list)
    asks: list[SectionImagesAsk] = field(default_factory=list)

    async def glossary(self, craft: CraftRef) -> list[GlossaryEntry]:
        self.crafts.append(craft.slug)
        if self.glossary_failure is not None:
            raise self.glossary_failure
        return list(self.entries)

    async def pictures(self, ask: SectionImagesAsk) -> ImagesBlock | None:
        self.asks.append(ask)
        images = SectionImages(
            sources=tuple(self.sources), store=self.media, search_seconds=self.search_seconds
        )
        return await images.block(ask)

    def tools(self) -> EnrichmentTools:
        return EnrichmentTools(glossary=self.glossary, pictures=self.pictures, wait_seconds=self.wait_seconds)


def picture_sources() -> list[FakeSource]:
    return [FakeSource("wikimedia_commons", [MORDANT_BATH]), FakeSource("searxng", [WASHED_LAKE])]


def enriched() -> FakeEnrichment:
    return FakeEnrichment(entries=GLOSSARY, sources=picture_sources())


def understanding_model(reply: Mapping[str, Any] | None = None) -> FakeModel:
    return FakeModel([json.dumps(UNDERSTOOD_REPLY if reply is None else reply)])


def pipeline(
    *,
    resolution: CraftResolution | Exception | None = None,
    research: FakeResearch | None = None,
    replies: Sequence[str] = (),
    store: FakeStore | None = None,
    translated: AnswerTranslation | None = None,
    understand_model: Any = None,
    compose_model: Any = None,
    spent: bool = False,
    pieces: MemoryPieces | None = None,
    enrichment: FakeEnrichment | None = None,
) -> AnswerPipeline:
    outcome = resolved() if resolution is None else resolution

    async def resolve(query: CraftQuery) -> CraftResolution:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    model = SpentModel() if spent else understand_model or understanding_model()
    return AnswerPipeline(
        understand=ModelUnderstander(model=model, resolve=resolve).understand,
        research=research or FakeResearch(),
        compose=ModelComposer(model=compose_model or FakeModel(list(replies))).compose,
        store=store or FakeStore(),
        translation=translated or translation(),
        pieces=MemoryPieces() if pieces is None else pieces,
        enrichment=(enrichment or FakeEnrichment()).tools(),
    )


async def streamed(ask: AnswerAsk, answer_pipeline: AnswerPipeline) -> str:
    frames = event_stream(lambda emit: answer_question(ask, answer_pipeline, emit))
    return "".join([frame async for frame in frames])
