from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Compound, Source
from app.services.claim_seed import seed_id
from app.services.compound_lookup import link_compounds, record_source_id
from app.services.science_seed import seed_science
from app.sources.reference.pubchem import PubChemCompound

from ..science.test_compound_lookup import FakeFinder

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 16, 9, 30, tzinfo=UTC)
ALIZARIN = PubChemCompound(
    6293,
    "Alizarin",
    "C14H8O4",
    "240.21",
    "1,2-dihydroxyanthracene-9,10-dione",
    "RGCKGOZRHPZPFP-UHFFFAOYSA-N",
    None,
)
LEUCOINDIGO = PubChemCompound(
    23035,
    "Leucoindigo",
    "C16H12N2O2",
    "264.28",
    "2-(3-hydroxy-1H-indol-2-yl)-1H-indol-3-ol",
    "VIFKLIUAPGUEBV-UHFFFAOYSA-N",
    None,
)
INDIGO_AT_LEUCO_CID = PubChemCompound(23035, "Indigo", "C16H10N2O2", None, None, None, None)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def test_a_seeded_compound_is_linked_to_its_pubchem_record(session: AsyncSession) -> None:
    report = await link_compounds(session, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    assert report.linked == ["Alizarin"]
    assert "Indigo" in report.not_found and report.failed == []
    alizarin = await session.get(Compound, seed_id("compound", "alizarin"))
    assert (alizarin.pubchemCid, alizarin.formula, alizarin.molecularWeight) == (
        6293,
        "C14H8O4",
        Decimal("240.21"),
    )
    assert alizarin.sourceId == record_source_id(6293)
    source = await session.get(Source, alizarin.sourceId)
    assert (source.kind, source.url, source.reliability) == (
        "COMPOUND_RECORD",
        "https://pubchem.ncbi.nlm.nih.gov/compound/6293",
        "A",
    )
    again = await link_compounds(session, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    assert again.linked == []
    sources = (await session.scalars(select(Source).where(Source.url == source.url))).all()
    assert len(sources) == 1


async def test_a_seeded_cid_gets_its_record_only_when_pubchem_holds_the_same_composition(
    session: AsyncSession,
) -> None:
    leuco = await session.get(Compound, seed_id("compound", "leucoindigo"))
    assert (leuco.pubchemCid, leuco.formula, leuco.sourceId) == (23035, "C16H12N2O2", None)
    wrong = await link_compounds(session, FakeFinder({}, {23035: INDIGO_AT_LEUCO_CID}), now=NOW)
    assert "Leucoindigo" in wrong.not_found and leuco.sourceId is None
    report = await link_compounds(session, FakeFinder({}, {23035: LEUCOINDIGO}), now=NOW)
    assert "Leucoindigo" in report.filled
    assert (leuco.pubchemCid, leuco.formula, leuco.sourceId) == (23035, "C16H12N2O2", record_source_id(23035))
    assert leuco.inchiKey == "VIFKLIUAPGUEBV-UHFFFAOYSA-N"


async def test_seeding_again_keeps_a_cid_the_lookup_linked(session: AsyncSession) -> None:
    await link_compounds(session, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    await seed_science(session)
    alizarin = await session.get(Compound, seed_id("compound", "alizarin"))
    await session.refresh(alizarin)
    assert (alizarin.pubchemCid, alizarin.sourceId) == (6293, record_source_id(6293))
