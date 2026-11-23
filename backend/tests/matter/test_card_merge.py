import dataclasses
import uuid
from typing import Any

import pytest

from app.services import craft_matter as craft_matter_module, matter_builders
from app.services.craft_matter import CraftMatter, MaterialRows
from app.services.material_cards import card_offers, merged_materials

from ..science.golden_process import claim_id
from .fixtures import (
    ALUM_OWN_CLAIM,
    PA_CLAIM,
    POTASSIUM_ALUM_CID,
    RED_CLAIM,
    CardModel,
    chemistry_ask,
    material_row,
    matter,
)
from .test_matter_builders import tools


def twinned() -> tuple[CraftMatter, uuid.UUID]:
    found = matter(alum_linked=True)
    (alum,) = [m for m in found.materials if m.compound and m.compound.pubchem_cid == POTASSIUM_ALUM_CID]
    taken = {claim for m in found.materials for use in m.uses for claim in use.claim_ids}
    taken |= {claim_id(PA_CLAIM), claim_id(RED_CLAIM)}
    spare = next(claim for claim in found.records.claims if claim not in taken)
    use = dataclasses.replace(
        alum.uses[0],
        id=uuid.uuid4(),
        material_id=material_row("twin"),
        name="Potassium alum",
        claim_ids=(spare,),
    )
    twin = MaterialRows(material_row("twin"), (use,), ())
    return dataclasses.replace(found, materials=(*found.materials, twin)), spare


def test_materials_sharing_a_pubchem_compound_are_offered_as_one_card() -> None:
    found, spare = twinned()
    assert len(merged_materials(found.materials)) == len(found.materials) - 1
    ask = chemistry_ask()
    (offer,) = [o for o in card_offers(found, ask.blocks, ask.cited) if o.material.compound is not None]
    assert offer.material.name == "Potassium alum"
    assert offer.material.compound.pubchem_cid == POTASSIUM_ALUM_CID
    assert {claim.id for claim in offer.statements.values()} == {claim_id(ALUM_OWN_CLAIM), spare}
    assert "Alum (fatakdi)" in offer.brief().names


def test_a_merged_card_is_offered_when_the_prose_names_only_the_row_not_chosen_as_its_name() -> None:
    found, _ = twinned()
    linked = [m for m in found.materials if m.compound and m.compound.pubchem_cid == POTASSIUM_ALUM_CID]
    (alum,) = [m for m in linked if m.name != "Potassium alum"]
    named = dataclasses.replace(alum.uses[0], name="Alum")
    plain = dataclasses.replace(alum, uses=(named, *alum.uses[1:]), terms=())
    renamed = dataclasses.replace(found, materials=tuple(plain if m is alum else m for m in found.materials))
    ask = chemistry_ask()
    (offer,) = [o for o in card_offers(renamed, ask.blocks, ask.cited) if o.material.compound is not None]
    assert offer.material.name == "Potassium alum"
    assert "Alum" in offer.material.surfaces()


def test_a_claim_the_section_s_prose_already_states_is_never_offered_to_a_card() -> None:
    ask = chemistry_ask()
    offered = {
        claim.id
        for offer in card_offers(matter(), ask.blocks, ask.cited)
        for claim in offer.statements.values()
    }
    assert offered
    assert not offered & {claim_id(PA_CLAIM), claim_id(RED_CLAIM)}


@pytest.fixture
def stored_twins(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found, spare = twinned()

    async def load(sessions: Any, craft: Any) -> CraftMatter:
        return found

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)
    return {"spare": spare}


async def test_one_card_shows_a_compound_named_by_two_materials(stored_twins: dict[str, Any]) -> None:
    reply = {"cards": [{"material": "m1", "facts": ["m1.c1", "m1.c2"], "handling": []}]}
    built = await matter_builders.MaterialCardBuilder(tools(CardModel(reply))).build(chemistry_ask())
    (card,) = [block for block in built.blocks if block.pubchem_cid == POTASSIUM_ALUM_CID]
    assert card.name == "Potassium alum"
    assert {sentence.citations[0].claim_id for sentence in card.facts} == {
        str(claim_id(ALUM_OWN_CLAIM)),
        str(stored_twins["spare"]),
    }
