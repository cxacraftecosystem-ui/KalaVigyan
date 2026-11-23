from collections.abc import AsyncIterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Update, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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


async def seeded(sessions: async_sessionmaker[AsyncSession], key: str) -> Compound:
    async with sessions() as session:
        compound = await session.get(Compound, seed_id("compound", key))
    assert compound is not None
    return compound


class ChangingFinder(FakeFinder):
    def __init__(self, sessions: async_sessionmaker[AsyncSession], change: Update) -> None:
        super().__init__({"Alizarin": [ALIZARIN]})
        self.sessions = sessions
        self.change: Update | None = change

    async def compounds(self, text: str, k: int) -> list[PubChemCompound]:
        if self.change is not None:
            async with self.sessions() as session:
                await session.execute(self.change)
                await session.commit()
            self.change = None
        return await super().compounds(text, k)


async def test_a_seeded_compound_is_linked_to_its_pubchem_record(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    report = await link_compounds(sessions, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    assert report.linked == ["Alizarin"]
    assert "Indigo" in report.not_found and report.failed == []
    alizarin = await seeded(sessions, "alizarin")
    assert (alizarin.pubchemCid, alizarin.formula, alizarin.molecularWeight) == (
        6293,
        "C14H8O4",
        Decimal("240.21"),
    )
    assert alizarin.sourceId == record_source_id(6293)
    async with sessions() as session:
        source = await session.get(Source, alizarin.sourceId)
    assert (source.kind, source.url, source.reliability) == (
        "COMPOUND_RECORD",
        "https://pubchem.ncbi.nlm.nih.gov/compound/6293",
        "A",
    )
    again = await link_compounds(sessions, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    assert again.linked == []
    async with sessions() as session:
        sources = (await session.scalars(select(Source).where(Source.url == source.url))).all()
    assert len(sources) == 1


async def test_a_seeded_cid_gets_its_record_only_when_pubchem_holds_the_same_composition(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    leuco = await seeded(sessions, "leucoindigo")
    assert (leuco.pubchemCid, leuco.formula, leuco.sourceId) == (23035, "C16H12N2O2", None)
    wrong = await link_compounds(sessions, FakeFinder({}, {23035: INDIGO_AT_LEUCO_CID}), now=NOW)
    assert "Leucoindigo" in wrong.not_found and (await seeded(sessions, "leucoindigo")).sourceId is None
    report = await link_compounds(sessions, FakeFinder({}, {23035: LEUCOINDIGO}), now=NOW)
    assert "Leucoindigo" in report.filled
    leuco = await seeded(sessions, "leucoindigo")
    assert (leuco.pubchemCid, leuco.formula, leuco.sourceId) == (23035, "C16H12N2O2", record_source_id(23035))
    assert leuco.inchiKey == "VIFKLIUAPGUEBV-UHFFFAOYSA-N"


async def test_seeding_again_keeps_a_cid_the_lookup_linked(
    sessions: async_sessionmaker[AsyncSession],
) -> None:
    await link_compounds(sessions, FakeFinder({"Alizarin": [ALIZARIN]}), now=NOW)
    async with sessions() as session:
        await seed_science(session)
        alizarin = await session.get(Compound, seed_id("compound", "alizarin"))
        await session.refresh(alizarin)
    assert (alizarin.pubchemCid, alizarin.sourceId) == (6293, record_source_id(6293))


@pytest.mark.parametrize(
    ("change", "kept"),
    [
        (
            update(Compound).where(Compound.id == seed_id("compound", "alizarin")).values(pubchemCid=6293),
            6293,
        ),
        (update(Compound).where(Compound.id == seed_id("compound", "indigo")).values(pubchemCid=6293), None),
    ],
    ids=["linked by another run", "its CID taken by another compound"],
)
async def test_a_compound_changed_while_pubchem_is_asked_is_left_for_the_next_run(
    sessions: async_sessionmaker[AsyncSession], change: Update, kept: int | None
) -> None:
    report = await link_compounds(sessions, ChangingFinder(sessions, change), now=NOW)
    assert report.linked == [] and report.failed == []
    assert "Alizarin" not in report.not_found
    alizarin = await seeded(sessions, "alizarin")
    assert (alizarin.pubchemCid, alizarin.sourceId) == (kept, None)
