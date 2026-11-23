from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Compound, Material, Source
from app.services.compound_lookup import link_compounds, record_source_id
from app.services.curation_import import import_curation
from app.sources.reference.pubchem import PubChemCompound

from ..science.test_compound_lookup import FakeFinder

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 18, 9, 30, tzinfo=UTC)
CURATED_CIDS = {
    10340: "Soda ash",
    6093208: "Lime",
    24393: "Ferrous sulphate",
    24489: "Sodium hydrosulphite (hydros)",
    14798: "Caustic soda",
}
SODA_ASH_RECORD = PubChemCompound(
    10340, "Sodium Carbonate", "CNa2O3", "105.988", "disodium;carbonate", None, None
)


@pytest.fixture
async def sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            yield async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
        finally:
            await transaction.rollback()


@pytest.fixture
async def session(sessions: async_sessionmaker[AsyncSession]) -> AsyncIterator[AsyncSession]:
    async with sessions() as session:
        yield session


async def compounds(session: AsyncSession) -> dict[int, Compound]:
    rows = await session.scalars(select(Compound).where(Compound.pubchemCid.in_(list(CURATED_CIDS))))
    return {int(row.pubchemCid or 0): row for row in rows}


async def test_every_curated_cid_has_a_compound_linked_to_its_material_and_pubchem_record(
    session: AsyncSession,
) -> None:
    report = await import_curation(session)
    assert report.refused == []
    found = await compounds(session)
    assert set(found) == set(CURATED_CIDS)
    for cid, compound in found.items():
        linked = (await session.scalars(select(Material).where(Material.compoundId == compound.id))).all()
        assert CURATED_CIDS[cid] in {material.name for material in linked}
        source = await session.get(Source, compound.sourceId)
        assert source is not None and source.kind == "COMPOUND_RECORD"
        assert source.url == f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}"
    assert found[10340].formula is None


async def test_a_second_import_writes_no_compound_again(session: AsyncSession) -> None:
    await import_curation(session)
    before = {cid: compound.id for cid, compound in (await compounds(session)).items()}
    again = await import_curation(session)
    assert all("compounds" not in outcome.changed for outcome in again.dossiers)
    assert {cid: compound.id for cid, compound in (await compounds(session)).items()} == before


async def test_the_compound_lookup_fills_the_formula_of_a_curated_record_from_pubchem(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    async with sessions() as session:
        await import_curation(session)
        await session.commit()
    report = await link_compounds(sessions, FakeFinder({}, {10340: SODA_ASH_RECORD}), now=NOW)
    async with sessions() as session:
        soda = (await compounds(session))[10340]
        sources = (await session.scalars(select(Source).where(Source.url == SODA_ASH_RECORD.url))).all()
    assert soda.name in report.filled
    assert (soda.formula, soda.sourceId) == ("CNa2O3", record_source_id(10340))
    assert len(sources) == 1
