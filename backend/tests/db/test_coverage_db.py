import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.models import (
    ArticleSection,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftGiRecord,
    CuratedCraft,
    KnowledgePiece,
    Source,
)
from app.research.coverage import COVERED, MISSING, THIN
from app.research.knowledge_api import FactQuantity
from app.services.coverage import craft_coverage, held_field_lookup
from app.services.coverage_reads import read_subject_coverage
from app.services.knowledge_api import craft_facts, craft_sections

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
SLUG = "Coverage-Test-Craft"
CRAFT = uuid.UUID("c0e00000-0000-4000-8000-000000000001")
ZIRCOVANE = uuid.UUID("c0e00000-0000-4000-8000-000000000002")
PAPER = uuid.UUID("c0e00000-0000-4000-8000-000000000010")
PAGE = uuid.UUID("c0e00000-0000-4000-8000-000000000011")
LETTER = uuid.UUID("c0e00000-0000-4000-8000-000000000012")
BINDS = uuid.UUID("c0e00000-0000-4000-8000-0000000000a1")
HEATS = uuid.UUID("c0e00000-0000-4000-8000-0000000000a2")
SOAKS = uuid.UUID("c0e00000-0000-4000-8000-0000000000a3")
GUILD = uuid.UUID("c0e00000-0000-4000-8000-0000000000a4")
SECRET = uuid.UUID("c0e00000-0000-4000-8000-0000000000a5")
UNCITED = uuid.UUID("c0e00000-0000-4000-8000-0000000000a6")
PLAYER = "coverage-test-craft/chemistry/zircovane-player"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, name="Coverage Test Craft", slug=SLUG, giStatus="GI"))
    session.add(Source(id=PAPER, kind="PAPER", title="Zircovane mordants"))
    session.add(Source(id=PAGE, kind="WEB_PAGE", title="A printers' page"))
    session.add(Source(id=LETTER, kind="PAPER", title="A restricted letter", sensitivity="RESTRICTED"))
    await session.flush()
    session.add(Concept(id=ZIRCOVANE, craftId=CRAFT, type="MATERIAL", name="Zircovane"))
    await session.flush()
    for claim_id, text, changes in _claims():
        session.add(_claim(claim_id, text, **changes))
    await session.flush()
    for claim_id, source_id in (
        (BINDS, PAPER),
        (HEATS, PAPER),
        (HEATS, PAGE),
        (SOAKS, PAGE),
        (GUILD, PAPER),
        (SECRET, LETTER),
    ):
        session.add(
            ClaimSource(claimId=claim_id, sourceId=source_id, quote="a quoted passage", locator="p. 2")
        )
    await _structure(session)


def _claims() -> list[tuple[uuid.UUID, str, dict[str, Any]]]:
    return [
        (BINDS, "Zircovane binds the dye to cotton.", {"field": "CHEMISTRY"}),
        (HEATS, "The zircovane bath is heated before dyeing.", {"field": "CHEMISTRY", "fields": ["PHYSICS"]}),
        (
            SOAKS,
            "The cloth soaks in zircovane for 12 hours.",
            {"field": "CHEMISTRY", "valueNum": Decimal("12"), "valueUnit": "hours"},
        ),
        (GUILD, "The printers' guild formed in the town.", {"field": "HISTORY"}),
        (SECRET, "A secret recipe was kept by one family.", {"field": "HISTORY"}),
        (UNCITED, "Zircovane comes from a shrub.", {"field": "BOTANY"}),
    ]


async def _structure(session: AsyncSession) -> None:
    session.add(CraftGiRecord(craftId=CRAFT, claimIds=[GUILD]))
    session.add(
        CuratedCraft(
            craftId=CRAFT,
            version=1,
            curatedAt=NOW,
            coverage="THIN",
            digest="0" * 64,
            page={"communities": [{"key": "G01", "claimIds": [str(GUILD)]}]},
        )
    )
    sentences = [{"text": "Zircovane binds the dye.", "claimIds": [str(BINDS)]}] * 2
    session.add(
        ArticleSection(craftId=CRAFT, field="CHEMISTRY", version=1, status="PUBLISHED", sentences=sentences)
    )
    session.add(
        KnowledgePiece(
            craftId=CRAFT,
            kind="dip_player",
            facet="CHEMISTRY",
            fields=["PHYSICS"],
            topicKey=f"component:{PLAYER}",
            language="en",
            depth="EXPERT",
            payload={},
            claimIds=[BINDS],
            sourceIds=[str(PAPER)],
            contentHash="c" * 64,
            label=PLAYER,
            title="Zircovane dip",
            description="A dip into the zircovane bath.",
        )
    )
    await session.flush()


def _claim(claim_id: uuid.UUID, text: str, **changes: Any) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=ZIRCOVANE,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        **changes,
    )


def counts(coverage: Any, field: str) -> tuple[int, int, int, int, int, int, str]:
    count = coverage.count(field)
    return (
        count.claims,
        count.structure_claims,
        count.sources,
        count.sections,
        count.sentences,
        count.figures,
        count.standing,
    )


async def test_a_craft_s_coverage_counts_cited_claims_sources_sections_and_figures_per_field(
    session: AsyncSession,
) -> None:
    coverage = await craft_coverage(session, SLUG)
    assert (coverage.subject_kind, coverage.subject_slug, coverage.claims_min) == ("craft", SLUG, 3)
    assert counts(coverage, "CHEMISTRY") == (3, 0, 2, 1, 2, 1, COVERED)
    assert counts(coverage, "PHYSICS") == (1, 0, 2, 0, 0, 1, THIN)
    assert counts(coverage, "HISTORY") == (1, 0, 1, 0, 0, 0, THIN)
    assert counts(coverage, "BOTANY") == (0, 0, 0, 0, 0, 0, MISSING)
    assert (coverage.claims, coverage.sources) == (4, 2)


async def test_communities_count_for_society_and_the_gi_record_for_policy(session: AsyncSession) -> None:
    coverage = await craft_coverage(session, SLUG)
    assert counts(coverage, "SOCIETY") == (1, 1, 1, 0, 0, 0, THIN)
    assert counts(coverage, "POLICY") == (1, 1, 1, 0, 0, 0, THIN)
    assert coverage.covered == ["CHEMISTRY"]
    assert coverage.thin == ["PHYSICS", "HISTORY", "SOCIETY", "POLICY"]
    assert len(coverage.missing) == 11


async def test_the_understander_reads_the_fields_a_craft_holds_claims_in(session: AsyncSession) -> None:
    class Sessions:
        def __call__(self) -> Sessions:
            return self

        async def __aenter__(self) -> AsyncSession:
            return session

        async def __aexit__(self, *exc: object) -> None:
            return None

    held = held_field_lookup(Sessions())  # type: ignore[arg-type]
    assert await held(SLUG) == ("CHEMISTRY", "PHYSICS", "HISTORY", "SOCIETY", "POLICY")
    assert await held("No-Such-Craft-Anywhere") == ()


async def test_the_mcp_coverage_names_the_open_field_work_and_the_page(session: AsyncSession) -> None:
    read = await read_subject_coverage(session, "craft", SLUG, site=SITE)
    assert read.page_url == f"{SITE}/crafts/{SLUG}"
    keys = [task.key for task in read.open_work]
    assert f"MISSING_FIELD:craft:{SLUG}:BOTANY" in keys
    assert f"THIN_FIELD:craft:{SLUG}:PHYSICS" in keys
    assert f"SECTION:craft:{SLUG}:CHEMISTRY" in keys
    assert not any(key.endswith(":CHEMISTRY") and key.startswith("THIN_FIELD") for key in keys)
    assert {task.priority for task in read.open_work} == {"MEDIUM"}
    with pytest.raises(InvalidInput, match="find_crafts"):
        await read_subject_coverage(session, "craft", "No-Such-Craft-Anywhere", site=SITE)


async def test_get_facts_groups_by_field_carries_quantities_and_figures_and_names_open_fields(
    session: AsyncSession,
) -> None:
    chemistry = await craft_facts(session, SLUG, site=SITE, field="CHEMISTRY")
    assert {fact.id for fact in chemistry.facts} == {BINDS, HEATS, SOAKS}
    assert [(group.field, group.count, set(group.shown)) for group in chemistry.by_field] == [
        ("CHEMISTRY", 3, {BINDS, HEATS, SOAKS})
    ]
    facts = {fact.id: fact for fact in chemistry.facts}
    assert [figure.label for figure in facts[BINDS].figures] == [PLAYER]
    assert facts[SOAKS].quantity == FactQuantity(value=12.0, unit="hours")
    assert facts[HEATS].quantity is None and chemistry.open_work == []
    botany = await craft_facts(session, SLUG, site=SITE, field="BOTANY")
    assert (botany.facts, botany.by_field) == ([], [])
    assert [task.key for task in botany.open_work] == [f"MISSING_FIELD:craft:{SLUG}:BOTANY"]
    every = await craft_facts(session, SLUG, site=SITE)
    assert [group.field for group in every.by_field] == ["CHEMISTRY", "PHYSICS", "HISTORY"]
    keys = {task.key for task in every.open_work}
    assert {f"THIN_FIELD:craft:{SLUG}:PHYSICS", f"MISSING_FIELD:craft:{SLUG}:BOTANY"} <= keys


async def test_get_section_without_a_field_lists_every_section_and_the_fields_still_to_write(
    session: AsyncSession,
) -> None:
    read = await craft_sections(session, SLUG, site=SITE)
    assert (read.field, read.section) == (None, None)
    assert [section.field for section in read.sections] == ["CHEMISTRY"]
    assert [(entry.field, entry.sentences, entry.claims) for entry in read.by_field] == [("CHEMISTRY", 2, 1)]
    assert f"SECTION:craft:{SLUG}:CHEMISTRY" in {task.key for task in read.open_work}
