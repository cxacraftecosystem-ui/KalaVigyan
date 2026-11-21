import hashlib
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.shielded import ShieldedWork
from app.models import (
    Answer,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    EnrichmentJob,
    Process,
    ProcessStage,
    Source,
)
from app.research.composition import ComposedAnswer, ComposedSection, ComposedSentence, QuotedSpan
from app.research.crafts import CraftRef
from app.research.evidence_pack import EvidencePack
from app.research.retrieval import KnowledgeHits
from app.research.sections import AnswerPlans, SectionPlan
from app.research.understanding import Understanding
from app.retrieval.indexing import replace_source_chunks
from app.services.answer_store import SqlAnswerStore
from app.services.answering import AnswerAsk
from app.services.research_write_back import store_live_research
from app.sources.adapter import build_document

from ..composer.fixtures import ABSTRACT, ABSTRACT_ITEM, LONG_ITEM, LONG_TEXT, PLAN, packed
from ..craft_fixtures import FixedEmbedder


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-write-back/{name}")


CATEGORY, FAMILY = key("category"), key("family")
CRAFT, QUIET, CATCH_ALL, RESTED = key("craft"), key("quiet"), key("catch-all"), key("rested")
ALUM_CONCEPT, STAGE_CONCEPT, PROCESS, STAGE = key("alum"), key("stage"), key("process"), key("stage-row")
IMPORTED, ANSWER = key("imported-source"), key("answer")
ZELVAR = CraftRef(slug="Zelvar-Dye", name="Zelvar Dye", path="/crafts/Zelvar-Dye")
ABSTRACT_ID, PAGE_ID = ABSTRACT_ITEM.id, LONG_ITEM.id
FIGURE_TEXT = "Mordant baths held 8 g/L alum and were heated to 60 °C."
FIGURE_QUOTE = "Mordanting baths of 8 g/L alum were heated to 60 °C"
WASH_TEXT = "The red withstood 20 washes."
WASH_QUOTE = "the lake withstood 20 washes"
UNDERSTOOD = Understanding(
    craft=ZELVAR,
    candidates=[],
    disciplines=["CHEMISTRY", "PROCESS"],
    seats=["CHEMIST", "TECHNOLOGIST"],
    depth="DETAILED",
    language="en",
    basis="MODEL",
)


async def seeded_session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(CraftCategory(id=CATEGORY, slug="test-write-back", name="Test Write Back", sortOrder=998))
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-write-back-family", name="Zelvar", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add_all(
        [
            Craft(id=CRAFT, slug=ZELVAR.slug, name=ZELVAR.name, subCategoryId=FAMILY),
            Craft(id=QUIET, slug="Zelvar-Quiet", name="Zelvar Quiet", subCategoryId=FAMILY),
            Craft(id=CATCH_ALL, slug="Zelvar-Others", name="Zelvar Others", isCatchAll=True),
            Craft(id=RESTED, slug="Zelvar-Rested", name="Zelvar Rested"),
        ]
    )
    await session.flush()
    session.add_all(
        [
            Concept(id=ALUM_CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"),
            Concept(id=STAGE_CONCEPT, craftId=CRAFT, type="PROCESS_STAGE", name="Mordant bath"),
            Process(id=PROCESS, craftId=CRAFT, name="Seed process"),
            Source(id=IMPORTED, kind="PAPER", title="Imported lake paper", doi="10.1000/LAKE"),
            Answer(id=ANSWER, question="Why does alum keep Zelvar red?", mode="HYBRID"),
            EnrichmentJob(craftId=RESTED, status="SUCCEEDED"),
        ]
    )
    await session.flush()
    session.add(
        ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, conceptId=STAGE_CONCEPT, name="Mordanting")
    )
    await replace_source_chunks(session, IMPORTED, "Curated imported text about lakes.")
    await session.flush()


def zelvar_pack(craft: CraftRef | None = ZELVAR) -> EvidencePack:
    return EvidencePack(
        plan=PLAN.model_copy(update={"craft": craft}),
        degraded=False,
        stored=KnowledgeHits(craft_slug=craft.slug if craft else None),
        coverage=({"facetIndex": 0},),
        evidence=(packed(ABSTRACT_ITEM, "crossref"), packed(LONG_ITEM, "web")),
        documents=(
            build_document(ABSTRACT_ITEM, ABSTRACT, "ABSTRACT"),
            build_document(LONG_ITEM, LONG_TEXT, "FULL_TEXT"),
        ),
    )


def said(text: str, ref: str, span: str) -> ComposedSentence:
    return ComposedSentence(text=text, evidence_ids=[ref], spans=[QuotedSpan(ref=ref, text=span)])


def answer(*sentences: ComposedSentence, guesses: tuple[ComposedSentence, ...] = ()) -> ComposedAnswer:
    sections = [ComposedSection(heading="Mordant", sentences=list(sentences))] if sentences else []
    return ComposedAnswer(sections=sections, open_questions=list(guesses))


def expected_claim_id(text: str, craft_slug: str = ZELVAR.slug, field: str = "MATERIALS") -> uuid.UUID:
    parts = ["claim-write-back/v2", craft_slug, field, text]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    return uuid.uuid5(uuid.uuid5(uuid.NAMESPACE_DNS, "craft-master.kalavigyan"), f"claim-write-back:{digest}")


async def write(session: AsyncSession, composed: ComposedAnswer, **options: object):
    fields = {"found_by": "ANSWER", "answer_id": ANSWER} | options
    return await store_live_research(session, zelvar_pack(), composed, embed=FixedEmbedder(), **fields)


def answer_store(session: AsyncSession) -> SqlAnswerStore:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlAnswerStore(sessions, embed=FixedEmbedder(), shield=ShieldedWork())


async def kept_answer(
    store: SqlAnswerStore, ask: AnswerAsk, composed: ComposedAnswer
) -> tuple[uuid.UUID, tuple[tuple[uuid.UUID, ...], ...]]:
    pack = zelvar_pack()
    answer_id = await store.begin(ask, UNDERSTOOD)
    claims_of = await store.keep(answer_id, pack, composed)
    plans = AnswerPlans(sections=[SectionPlan(section_id="s1", discipline="CHEMISTRY", plan=pack.plan)])
    claim_ids = list(dict.fromkeys(claim for claims in claims_of for claim in claims))
    await store.finish(answer_id, plans=plans, claim_ids=claim_ids, explainer=None)
    return answer_id, claims_of
