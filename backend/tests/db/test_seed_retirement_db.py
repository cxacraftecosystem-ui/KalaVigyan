import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import InvalidInput
from app.curation.checks import default_context
from app.curation.files import CURATION_DIR
from app.models import (
    Claim,
    Concept,
    CraftGiRecord,
    CraftLocation,
    CraftPrice,
    CraftWorkforce,
    CuratedClaim,
    CuratedCraft,
    KnowledgePiece,
    Process,
    Term,
    TermSummary,
)
from app.models.science import live_process
from app.research.retrieval import HIDDEN_CLAIM_STATUSES
from app.retrieval.statements import EVERY_CRAFT, claim_conditions
from app.services import knowledge_view
from app.services.claim_seed import SEED_PROCESS_VARIANT
from app.services.craft_page import craft_page
from app.services.craft_page_records import craft_page_records
from app.services.craft_process import process_records
from app.services.curated_index import CuratedPage
from app.services.curation_import import import_curation, import_path
from app.services.curation_keys import CURATED_PROCESS_VARIANT, curated_id
from app.services.curation_retire import retire_dossier
from app.services.curation_seed_rows import (
    SEED_RESTORED_NOTE,
    SEED_RETIRED_NOTE,
    retire_curated_seed_rows,
    seed_claim,
)

from ..curation.import_support import AJRAKH, raw
from ..migration_scripts import migration

pytestmark = pytest.mark.db

SEEDED_AND_CURATED = (
    "Bagh-Prints-Of-Madhya-Pradesh",
    "Bagru-Hand-Block-Print",
    AJRAKH,
    "Machilipatnam-Kalamkari",
    "Sanganeri-Hand-Block-Printing",
)
AJRAKH_GI_RECORDS, AJRAKH_PRICES, AJRAKH_WORKFORCE = 1, 1, 5
KASANU = "kasanu"
KASANU_CLAIM = "C067"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def craft_id(session: AsyncSession, slug: str) -> uuid.UUID:
    craft = await knowledge_view.resolve_craft(session, slug)
    assert craft is not None
    return craft.id


def seed_claims_of(owner: uuid.UUID) -> list[Any]:
    concepts = select(Concept.id).where(Concept.craftId == owner)
    return [Claim.subjectType == "CONCEPT", Claim.subjectId.in_(concepts), seed_claim()]


async def shown_seed_rows(session: AsyncSession, slug: str) -> tuple[int, int]:
    owner = await craft_id(session, slug)
    shown = select(func.count()).where(*seed_claims_of(owner), Claim.status.not_in(HIDDEN_CLAIM_STATUSES))
    live = select(func.count()).where(
        Process.craftId == owner, Process.variant == SEED_PROCESS_VARIANT, live_process()
    )
    return (await session.execute(shown)).scalar_one(), (await session.execute(live)).scalar_one()


async def every_seed_row(session: AsyncSession) -> dict[str, tuple[int, int]]:
    return {slug: await shown_seed_rows(session, slug) for slug in SEEDED_AND_CURATED}


async def test_the_import_leaves_a_curated_craft_only_its_curated_rows(session: AsyncSession) -> None:
    before = await every_seed_row(session)
    assert all(shown > 0 and live == 1 for shown, live in before.values()), before
    report = await import_curation(session)
    assert report.refused == []
    assert report.retired_seed_rows.processes == len(SEEDED_AND_CURATED)
    assert report.retired_seed_rows.claims == sum(shown for shown, _ in before.values())
    assert await every_seed_row(session) == dict.fromkeys(SEEDED_AND_CURATED, (0, 0))
    owner = await craft_id(session, AJRAKH)
    craft = await knowledge_view.resolve_craft(session, AJRAKH)
    assert craft is not None
    records = await process_records(session, craft)
    assert [process.variant for process in records.processes] == [CURATED_PROCESS_VARIANT]
    seeded = set((await session.scalars(select(Claim.id).where(*seed_claims_of(owner)))).all())
    page = craft_page(await craft_page_records(session, craft))
    assert seeded and seeded.isdisjoint(claim.id for claim in page.claims)
    searched = select(func.count()).where(Claim.id.in_(seeded), *claim_conditions(EVERY_CRAFT, mode="DEEP"))
    assert (await session.execute(searched)).scalar_one() == 0


async def test_a_seed_row_that_comes_back_is_retired_again(session: AsyncSession) -> None:
    await import_curation(session)
    owner = await craft_id(session, AJRAKH)
    one = await session.scalar(select(Claim.id).where(*seed_claims_of(owner)).limit(1))
    await session.execute(update(Claim).where(Claim.id == one).values(status="PROPOSED"))
    await session.execute(update(Process).where(Process.craftId == owner).values(archivedAt=None))
    retired = await retire_curated_seed_rows(session)
    assert (retired.claims, retired.processes) == (1, 1)
    assert await shown_seed_rows(session, AJRAKH) == (0, 0)


async def test_the_migration_downgrade_restores_the_seed_rows_and_its_upgrade_retires_them(
    session: AsyncSession,
) -> None:
    before = await every_seed_row(session)
    await import_curation(session)
    steps = migration("0067_seed_rows_retired")
    for statement in steps.restore_statements():
        await session.execute(statement)
    assert await every_seed_row(session) == before
    for statement in steps.retire_statements():
        await session.execute(statement)
    assert await every_seed_row(session) == dict.fromkeys(SEEDED_AND_CURATED, (0, 0))


def test_the_migration_and_the_import_retire_with_one_note() -> None:
    params = migration("0067_seed_rows_retired").SEED_PARAMS
    assert (params["retired_note"], params["restored_note"]) == (SEED_RETIRED_NOTE, SEED_RESTORED_NOTE)
    assert params["seed_variant"] == SEED_PROCESS_VARIANT


async def test_a_retired_dossier_leaves_its_claims_superseded_and_its_seed_rows_restored(
    session: AsyncSession, tmp_path: Path
) -> None:
    before = await shown_seed_rows(session, AJRAKH)
    await import_curation(session)
    owner = await craft_id(session, AJRAKH)
    page = CuratedPage.model_validate(
        await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == owner))
    )
    with pytest.raises(InvalidInput):
        await retire_dossier(session, AJRAKH)
    retired = await retire_dossier(session, AJRAKH, directory=tmp_path)
    curated = select(CuratedClaim.claimId).where(CuratedClaim.craftId == owner)
    statuses = await session.scalars(select(Claim.status).where(Claim.id.in_(curated)).distinct())
    assert set(statuses.all()) == {"SUPERSEDED"}
    assert retired.claims == len(raw(AJRAKH)["claims"]) and retired.processes == 1
    overview = list(page.piece_ids().values())
    stale = await session.scalars(select(KnowledgePiece.staleSince).where(KnowledgePiece.id.in_(overview)))
    assert overview and all(stamp is not None for stamp in stale.all())
    assert await session.scalar(select(CuratedCraft.craftId).where(CuratedCraft.craftId == owner)) is None
    curated_process = select(func.count()).where(
        Process.craftId == owner, Process.variant == CURATED_PROCESS_VARIANT, live_process()
    )
    assert (await session.execute(curated_process)).scalar_one() == 0
    assert await shown_seed_rows(session, AJRAKH) == before


async def test_a_retired_dossier_leaves_no_gi_record_place_price_or_workforce_row(
    session: AsyncSession, tmp_path: Path
) -> None:
    outcome = await import_path(session, CURATION_DIR / f"{AJRAKH}.json", default_context())
    assert outcome.status == "IMPORTED", outcome.problems
    owner = await craft_id(session, AJRAKH)
    page = CuratedPage.model_validate(
        await session.scalar(select(CuratedCraft.page).where(CuratedCraft.craftId == owner))
    )
    places = list(page.location_ids())
    assert places
    before = await curated_records(session, owner, places)
    assert before == (AJRAKH_GI_RECORDS, len(places), AJRAKH_PRICES, AJRAKH_WORKFORCE)
    retired = await retire_dossier(session, AJRAKH, directory=tmp_path)
    assert retired.records == sum(before)
    assert await curated_records(session, owner, places) == (0, 0, 0, 0)


async def curated_records(
    session: AsyncSession, owner: uuid.UUID, places: list[uuid.UUID]
) -> tuple[int, int, int, int]:
    counted = [
        (await session.execute(select(func.count()).select_from(model).where(condition))).scalar_one()
        for model, condition in (
            (CraftGiRecord, CraftGiRecord.craftId == owner),
            (CraftLocation, CraftLocation.id.in_(places)),
            (CraftPrice, CraftPrice.craftId == owner),
            (CraftWorkforce, CraftWorkforce.craftId == owner),
        )
    ]
    return counted[0], counted[1], counted[2], counted[3]


async def test_a_curated_glossary_meaning_reaches_the_term_route_as_a_stored_summary(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    term_id = await session.scalar(select(Term.id).where(Term.key == KASANU))
    row = await session.scalar(
        select(TermSummary).where(TermSummary.termId == term_id, TermSummary.language == "en")
    )
    assert row is not None and row.basis == "STORED"
    claim = curated_id(AJRAKH, KASANU_CLAIM)
    assert row.claimIds == [claim]
    stated = next(item["text"] for item in raw(AJRAKH)["claims"] if item["id"] == KASANU_CLAIM)
    assert [sentence["text"] for sentence in row.payload["summary"]] == [stated]
