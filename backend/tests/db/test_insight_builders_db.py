import uuid
from collections.abc import AsyncIterator
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, CuratedClaim
from app.research.crafts import CraftRef
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.services import knowledge_view
from app.services.curation_import import import_curation
from app.services.market_builder import market_block
from app.services.market_store import market_offers
from app.services.measure_regions import stated_region
from app.services.measure_store import craft_places, regional_factors

pytestmark = pytest.mark.db

AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
DHOKRA = CraftRef(slug="Bastar-Dhokra", name="Bastar Dhokra", path="/crafts/Bastar-Dhokra")
TIKULI = CraftRef(slug="Tikuli-Painting", name="Tikuli Painting", path="/crafts/Tikuli-Painting")
KACHCHH, GUJARAT, BARMER = 449, 24, 90
SEER_QUOTE = "In Kachchh a seer weighed 0.933 kg."


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


async def test_the_imported_registry_records_and_dated_prices_reach_the_market_blocks(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    ajrakh, dhokra, tikuli = await market_offers(session, [AJRAKH, DHOKRA, TIKULI])
    block = market_block(ajrakh, block_id="s5.market1")
    assert block is not None and block.gi is not None
    assert (block.gi.status, block.gi.application_number, block.gi.registered_on) == (
        "REGISTERED",
        "1050",
        "2024-04-22",
    )
    assert [(p.stated, p.priced_on, p.place, p.district_lgd) for p in block.prices] == [
        ("Rs. 7", "1975", "Barmer", BARMER)
    ]
    bastar = market_block(dhokra, block_id="s5.market2")
    assert bastar is not None and bastar.gi is not None and bastar.gi.authorised_user_count == 110
    assert [p.stated for p in bastar.prices] == ["₹550"]
    assert tikuli.record is None and market_block(tikuli, block_id="s5.market3") is None


async def test_a_seer_converts_only_once_a_stored_quote_states_its_value_for_kachchh(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    craft = await knowledge_view.resolve_craft(session, AJRAKH.slug)
    assert craft is not None
    places = await craft_places(session, craft)
    assert KACHCHH in places.districts and {GUJARAT, 8} <= places.states
    assert (await regional_factors(session, AJRAKH.slug, {"seer"})).factors == {}
    curated = select(CuratedClaim.claimId).where(CuratedClaim.craftId == craft.id)
    candidates = await session.scalars(
        select(Claim.id).where(Claim.id.in_(curated), Claim.evidenceLevel == "PROVISIONAL").order_by(Claim.id)
    )
    ordered = list(candidates)
    views, _ = await knowledge_view.claims_by_id(session, ordered, acls=EVERY_CHUNK_ACLS)
    shown = next(
        views[claim_id]
        for claim_id in ordered
        if claim_id in views
        and views[claim_id].citations
        and stated_region([SEER_QUOTE, views[claim_id].text]) is not None
    )
    cite = await session.get(ClaimSource, uuid.UUID(shown.citations[0]["id"]))
    assert cite is not None
    cite.quote = SEER_QUOTE
    await session.flush()
    found = await regional_factors(session, AJRAKH.slug, {"seer"})
    factor = found.factors["seer"]
    assert (factor.factor, factor.metric_unit, factor.region.district_lgd) == (
        Decimal("0.933"),
        "kg",
        KACHCHH,
    )
    assert factor.citation.id == str(cite.id) and str(cite.sourceId) in found.sources
    assert (await regional_factors(session, AJRAKH.slug, {"maund"})).factors == {}
