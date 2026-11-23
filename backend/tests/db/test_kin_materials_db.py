import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Concept, Craft, Term, TermConcept, TermCraft
from app.services.monograph_generated_kin import shared_materials

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

OWN, KIN, OTHER = "Kin-Test-Own-Print", "Kin-Test-Kin-Print", "Kin-Test-Other-Print"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-kin-materials/{name}")


def term(name: str, label: str) -> Term:
    return Term(id=key(f"term/{name}"), key=f"test-kin-{name}", label=label, localNames=[], aliases=[])


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        crafts = {slug: key(f"craft/{slug}") for slug in (OWN, KIN, OTHER)}
        opened.add_all(
            [Craft(id=craft_id, slug=slug, name=slug.replace("-", " ")) for slug, craft_id in crafts.items()]
        )
        opened.add_all(
            [
                Concept(id=key("concept/alum"), type="MATERIAL", name="Alum"),
                Concept(id=key("concept/block"), type="TOOL", name="Block"),
                Concept(id=key("concept/madder"), type="MATERIAL", name="Madder"),
                term("alum", "Alum"),
                term("block", "Block"),
                term("madder", "Madder"),
            ]
        )
        await opened.flush()
        links = [
            ("alum", OWN),
            ("alum", KIN),
            ("alum", OTHER),
            ("block", OWN),
            ("block", KIN),
            ("madder", OWN),
        ]
        opened.add_all([TermCraft(termId=key(f"term/{name}"), craftId=crafts[slug]) for name, slug in links])
        opened.add_all(
            [
                TermConcept(termId=key(f"term/{name}"), conceptId=key(f"concept/{name}"))
                for name in ("alum", "block", "madder")
            ]
        )
        await opened.flush()
        yield opened


async def test_a_kin_craft_shares_the_material_terms_both_crafts_name_and_no_tool(
    session: AsyncSession,
) -> None:
    found = await shared_materials(session, key(f"craft/{OWN}"), [KIN])
    assert found == {KIN: ("Alum",)}
