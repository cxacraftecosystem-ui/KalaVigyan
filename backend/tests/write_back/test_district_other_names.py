import uuid

from app.research.crafts import CraftRef
from app.services.craft_index import CraftRecord, build_index
from app.services.write_back_crafts import HELD_OTHER_PLACE, CraftFiling, FilingTexts, craft_filing
from app.services.write_back_names import CraftNames, craft_names

from .names import TEXTILE_FAMILY, ref

ROGAN = ref("Rogan-Painting", "Rogan Painting")
BOILED = "In Kutch the castor oil is boiled for two days."
BOILED_IN_KACHCHH = "In Kachchh the castor oil is boiled for two days."


def placed(craft: CraftRef, *places: str) -> CraftNames:
    craft_id = uuid.uuid5(uuid.NAMESPACE_URL, f"test-district-other-names/{craft.slug}")
    index = build_index([CraftRecord(craft_id, craft.slug, craft.name, "ACTIVE", places=places)], [], [])
    return craft_names(index, craft, family=TEXTILE_FAMILY)


def filed(text: str, *places: str) -> CraftFiling:
    return craft_filing(FilingTexts(text), field="PROCESS", names=placed(ROGAN, *places))


def test_a_craft_placed_in_kachchh_is_named_by_kutch_the_name_its_sources_use() -> None:
    assert filed(BOILED, "Gujarat", "Kachchh") == CraftFiling(ROGAN.slug)


def test_a_craft_placed_under_kutch_is_named_by_kachchh_the_register_s_name() -> None:
    assert filed(BOILED_IN_KACHCHH, "Gujarat", "Kutch") == CraftFiling(ROGAN.slug)


def test_a_district_with_no_other_name_still_holds_a_text_naming_another_place() -> None:
    assert filed(BOILED, "Rajasthan", "Jaipur") == CraftFiling(
        ROGAN.slug, held=HELD_OTHER_PLACE.format(places="kutch")
    )
