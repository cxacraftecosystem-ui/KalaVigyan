import dataclasses

from app.composer.supply_map import SupplyLinkChoice
from app.services.supply_links import SupplyOffer, supply_links

from .season_supply_fixtures import GOLDEN_LINKS, INDIGO_TERM, SUPPLY, indigo_rows, supply_claims


def offer(sentence_name: str | None) -> SupplyOffer:
    indigo, blocks = supply_claims()
    term = dataclasses.replace(INDIGO_TERM, sentence_name=sentence_name)
    rows = dataclasses.replace(indigo_rows(indigo), terms=(term,))
    return SupplyOffer(materials={"m1": rows}, statements={"c1": indigo, "c2": blocks})


def materials(sentence_name: str | None) -> list[str]:
    choices = [SupplyLinkChoice.model_validate(link) for link in GOLDEN_LINKS["links"]]
    return [link.material for link in supply_links(offer(sentence_name), choices, block_id=SUPPLY)]


def test_a_material_is_carried_by_its_glossary_term_s_sentence_name() -> None:
    assert materials("indigo") == ["indigo", "indigo", "Blocks"]


def test_without_a_sentence_name_the_material_keeps_its_label() -> None:
    assert materials(None) == ["Indigo", "Indigo", "Blocks"]
