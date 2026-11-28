from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Craft, CuratedClaim
from app.services.compose_components import ComposeDeps, compose_component
from app.services.compose_held import About
from app.services.compose_named import UNNAMED
from app.services.compose_reads import craft_held
from app.services.curation_import import import_curation
from app.services.curation_keys import curated_id
from app.sources.reference.pubchem import PubChemCompound

from ..compose.held import CONFORMER_SDF

pytestmark = pytest.mark.db

SANGANERI = "Sanganeri-Hand-Block-Printing"
AJRAKH = "Kutch-Ajrakh"
RECORDS = {
    6293: PubChemCompound(6293, "Alizarin", "C14H8O4", "240.21", None, None, None),
    969516: PubChemCompound(969516, "Curcumin", "C21H20O6", "368.4", None, None, None),
}


class Records:
    async def compound(self, cid: int) -> PubChemCompound | None:
        return RECORDS.get(cid)

    async def synonyms(self, cid: int) -> list[str]:
        return []


class Conformers:
    async def conformer(self, cid: int) -> str | None:
        return CONFORMER_SDF


async def pubchem() -> Records:
    return Records()


async def conformers() -> Conformers:
    return Conformers()


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            sessions = async_sessionmaker(
                bind=connection,
                expire_on_commit=False,
                autoflush=False,
                join_transaction_mode="create_savepoint",
            )
            async with sessions() as opened:
                yield opened
        finally:
            await transaction.rollback()


async def owned(session: AsyncSession, slug: str) -> set[object]:
    rows = await session.scalars(
        select(CuratedClaim.claimId).join(Craft, Craft.id == CuratedClaim.craftId).where(Craft.slug == slug)
    )
    return set(rows)


async def test_sanganeri_s_own_reactions_compose_its_player_and_cite_none_of_kutch_ajrakh_s_facts(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    result = await compose_component(session, ComposeDeps(), SANGANERI, "reaction_player", About())
    assert result.composed, result.missing
    (component,) = result.components
    spec = component.proposal.spec
    assert spec is not None
    assert [step["name"] for step in spec["steps"]] == [
        "Mordant printing",
        "Alizarin dyeing",
        "Alizarin dyeing: black colour",
        "Indigo dyeing",
    ]
    cited = {claim for unit in component.proposal.units.values() for claim in unit.claim_ids}
    assert cited == {curated_id(SANGANERI, key) for key in ("C059", "C060", "C063")}
    assert cited <= await owned(session, SANGANERI)
    assert not cited & await owned(session, AJRAKH)


async def test_a_page_without_its_colours_after_is_told_what_to_propose_and_ajrakh_s_dips_in_its_own(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    refused = await compose_component(session, ComposeDeps(), SANGANERI, "dip_player", About())
    assert refused.components == ()
    assert any(
        "propose_structure STAGE_AFTER for Sanganeri-Hand-Block-Printing" in gap for gap in refused.missing
    )
    held = await craft_held(session, AJRAKH)
    assert held is not None
    indigo = held.stage("P08")
    assert indigo is not None and indigo.after is not None
    assert indigo.after.tokens[0] == "--dye-indigo"
    dip = await compose_component(session, ComposeDeps(), AJRAKH, "dip_player", About())
    assert dip.composed, dip.missing
    (component,) = dip.components
    assert component.proposal.spec is not None
    assert component.proposal.spec["dips"][:3] == ["--dye-cloth", "--dye-harda", "--dye-lime"]


async def test_a_compound_sanganeri_s_own_facts_name_is_composed_and_one_they_never_name_is_refused(
    session: AsyncSession,
) -> None:
    await import_curation(session)
    deps = ComposeDeps(conformers=conformers, records=pubchem)
    found = await compose_component(session, deps, SANGANERI, "molecule_3d", About(compound=6293))
    assert found.composed, found.missing
    (component,) = found.components
    spec = component.proposal.spec
    assert spec is not None
    assert [(model["cid"], model["name"]) for model in spec["molecules"]] == [(6293, "Alizarin")]
    sides = [component.proposal.units[block["unit"]].text for block in spec["side"]]
    assert sides and all("alizarin" in text.lower() for text in sides)
    cited = {claim for unit in component.proposal.units.values() for claim in unit.claim_ids}
    assert cited and cited <= await owned(session, SANGANERI)
    assert not cited & await owned(session, AJRAKH)
    held = await craft_held(session, SANGANERI)
    assert held is not None
    unnamed = await compose_component(session, deps, SANGANERI, "molecule_3d", About(compound=969516))
    assert unnamed.components == ()
    assert unnamed.missing == (UNNAMED.format(craft=held.name, name="Curcumin", cid=969516),)
