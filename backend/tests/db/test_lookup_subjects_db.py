import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Compound, Concept, Material
from app.services.lookup_subjects import compound_subjects, entity_subjects
from app.services.open_work_subjects import subject_by_key
from app.services.page_keys import page_keys
from app.services.source_lookup_models import EntityRecord

from .component_places_seed import CLAY, KACHCHH, KUTCH_CATEGORY_SLUG, KUTCH_SLUG, UP_SLUG, seed
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

CID = 900000001
COMPOUND = uuid.UUID("5b1e0000-0000-4000-8000-000000000001")
SHARED_ALUM = uuid.UUID("5b1e0000-0000-4000-8000-000000000002")
HIDDEN_ALUM = uuid.UUID("5b1e0000-0000-4000-8000-000000000003")
COMPOUND_NAME = "Lookup test potash alum"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        await seed(opened)
        await _held(opened)
        yield opened


async def _held(session: AsyncSession) -> None:
    session.add(Compound(id=COMPOUND, pubchemCid=CID, name=COMPOUND_NAME, synonyms=["Lookup test kalabash"]))
    session.add(Concept(id=SHARED_ALUM, type="MATERIAL", name="lookup test kalabash"))
    session.add(Concept(id=HIDDEN_ALUM, type="MATERIAL", name=COMPOUND_NAME, sensitivity="RESTRICTED"))
    await session.flush()
    session.add(
        Material(name="Places test clay", nameNorm="places test clay", conceptId=CLAY, compoundId=COMPOUND)
    )
    await session.flush()


def entity(label: str, *, cid: str | None = None) -> EntityRecord:
    return EntityRecord(
        qid="Q900001",
        label=label,
        url="https://www.wikidata.org/wiki/Q900001",
        licence="CC0 1.0",
        open_licence=True,
        grade="B",
        pubchem_cid=cid,
        lines=[],
    )


async def test_a_held_compound_gives_its_id_and_the_open_concepts_that_hold_it(session: AsyncSession) -> None:
    found = await compound_subjects(session, [CID])
    assert [(subject.kind, subject.key, subject.record, subject.craft_slug) for subject in found] == [
        ("COMPOUND", str(COMPOUND), str(CID), None),
        ("CONCEPT", str(SHARED_ALUM), str(CID), None),
        ("CONCEPT", str(CLAY), str(CID), UP_SLUG),
    ]
    assert found[0].name == COMPOUND_NAME
    assert await compound_subjects(session, []) == []


async def test_a_wikidata_district_or_craft_gives_its_place_key_or_its_slug(session: AsyncSession) -> None:
    district = await entity_subjects(session, [entity("Kachchh district", cid=str(CID))])
    assert [(subject.kind, subject.key, subject.record) for subject in district] == [
        ("PLACE", f"lgd:{KACHCHH}", "Q900001"),
        ("COMPOUND", str(COMPOUND), "Q900001"),
        ("CONCEPT", str(SHARED_ALUM), "Q900001"),
        ("CONCEPT", str(CLAY), "Q900001"),
    ]
    craft = await entity_subjects(session, [entity("Places Test Kutch Print")])
    assert [(subject.kind, subject.key) for subject in craft] == [("CRAFT", KUTCH_SLUG)]


async def test_a_craft_page_s_keys_are_the_craft_and_its_districts(session: AsyncSession) -> None:
    keys = await page_keys(session, await subject_by_key(session, "craft", KUTCH_SLUG))
    assert [(key.kind, key.key, key.name) for key in keys] == [
        ("CRAFT", KUTCH_SLUG, "Places Test Kutch Print"),
        ("PLACE", f"lgd:{KACHCHH}", "Kachchh"),
    ]
    assert await page_keys(session, await subject_by_key(session, "category", KUTCH_CATEGORY_SLUG)) == []
