import pytest

from app.data.places_abroad import load_places_abroad, parse_places_abroad
from app.services.write_back_crafts import (
    SKIP_ABROAD,
    SKIP_OTHER_PLACE,
    SKIP_SEVERAL_CRAFTS,
    SKIP_UNNAMED,
    CraftFiling,
    craft_filing,
)

from ..research.fixtures import AJRAKH
from .names import BAGH, BLUE_POTTERY, KHURJA, MUD_FAMILY, TEXTILE_FAMILY, names_for

KHURJA_NAMES = names_for(KHURJA, family=MUD_FAMILY)
KHOREZM = (
    "In Khorezm practice, clay is kneaded thoroughly by hand because if air remains in the clay, "
    "the container may have holes."
)
NIGERIAN = (
    "In a Nigerian porcelain study, the 43.2 wt.% Si2O in the feldspar can contribute to the "
    "formulation of the liquid phase."
)
PORCELAIN = (
    "Porcelain is made by heating refined kaolinite clay in a kiln at temperatures between 1200 °C - 1400 °C."
)
KILN_SCHEDULE = "A kiln-schedule guide likewise says damp or thick-walled work needs a longer candle."
POLYMER = "It adds that synthetic and polymer clays offer greater consistency, durability, and ease of use."
IN_KHURJA = "In Khurja, shaped items are air-dried and then fired in kilns, often wood-fired or coal-fired."


def filed(text: str, *quotes: str, field: str | None = "MATERIALS", names=KHURJA_NAMES) -> CraftFiling:
    return craft_filing(text, quotes, field=field, names=names)


def test_a_fact_naming_khurja_stays_under_khurja() -> None:
    assert filed(IN_KHURJA, field="PROCESS") == CraftFiling(KHURJA.slug)
    assert filed("Khurja pottery is glazed before its second firing.", field="PROCESS").slug == KHURJA.slug


def test_a_fact_whose_quote_names_khurja_stays_under_khurja() -> None:
    quote = "In Khurja, shaped items are air-dried"
    assert filed("Shaped items are air-dried before firing.", quote, field="PROCESS").slug == KHURJA.slug


@pytest.mark.parametrize(("text", "place"), [(KHOREZM, "Khorezm"), (NIGERIAN, "Nigerian")])
def test_a_fact_about_a_place_outside_india_is_not_written_back_for_an_indian_craft(
    text: str, place: str
) -> None:
    assert filed(text) == CraftFiling(None, SKIP_ABROAD.format(places=place))
    assert filed(text, field="PROCESS") == CraftFiling(None, SKIP_ABROAD.format(places=place))


def test_a_quote_from_abroad_keeps_a_general_statement_out_of_the_family() -> None:
    quote = "the 43.2 wt.% Si2O in the Nigerian feldspar"
    assert filed("Feldspar can contribute to the liquid phase.", quote).refused == SKIP_ABROAD.format(
        places="Nigerian"
    )


@pytest.mark.parametrize("text", [PORCELAIN, POLYMER])
def test_material_science_naming_no_craft_and_no_place_goes_to_the_family(text: str) -> None:
    assert filed(text) == CraftFiling(None, family=MUD_FAMILY)
    assert filed(text, field="CHEMISTRY") == CraftFiling(None, family=MUD_FAMILY)


def test_a_statement_naming_no_craft_outside_material_science_has_no_home() -> None:
    assert filed(KILN_SCHEDULE, field="PROCESS") == CraftFiling(None, SKIP_UNNAMED)
    assert filed(KILN_SCHEDULE, field="PHYSICS") == CraftFiling(None, family=MUD_FAMILY)
    assert filed(POLYMER, field="HISTORY") == CraftFiling(None, SKIP_UNNAMED)


def test_without_a_family_material_science_naming_no_craft_has_no_home() -> None:
    assert filed(PORCELAIN, names=names_for(KHURJA, family=None)) == CraftFiling(None, SKIP_UNNAMED)


def test_a_fact_naming_another_catalogued_craft_goes_to_that_craft() -> None:
    text = "Jaipur blue pottery is made of quartz frit rather than clay."
    assert filed(text, field="PROCESS") == CraftFiling(BLUE_POTTERY.slug)


def test_a_fact_naming_another_indian_place_but_no_craft_has_no_home() -> None:
    assert filed("Clays from Azamgarh fire black.") == CraftFiling(
        None, SKIP_OTHER_PLACE.format(places="azamgarh")
    )
    assert filed("In Uttar Pradesh, kaolin is fired white.").refused == SKIP_OTHER_PLACE.format(
        places="uttar pradesh"
    )


def test_a_place_word_in_another_sense_names_no_place_abroad() -> None:
    assert filed("China clay is kaolinite, which fires white.") == CraftFiling(None, family=MUD_FAMILY)
    assert filed("Turkey red is an alizarin lake on oiled cotton.").family == MUD_FAMILY
    assert filed("Porcelain from China is fired hard.").refused == SKIP_ABROAD.format(places="China")


def test_names_match_as_whole_words() -> None:
    assert filed("The Khurjan kiln is fired with wood.", field="PROCESS") == CraftFiling(None, SKIP_UNNAMED)
    assert filed("Ochre gives a brown colour.") == CraftFiling(None, family=MUD_FAMILY)


def test_research_for_no_craft_files_nothing_under_a_craft() -> None:
    assert filed(KHOREZM, names=names_for(None)) == CraftFiling(None)


def test_in_a_comparison_one_named_craft_takes_the_fact_and_two_skip_it() -> None:
    names = names_for(AJRAKH, (BAGH,), family=TEXTILE_FAMILY)
    assert filed("Bagh printers boil the cloth with dhawdi flowers.", names=names).slug == BAGH.slug
    assert filed("Ajrakh printers wash the cloth in the river.", names=names).slug == AJRAKH.slug
    both = filed("Ajrakh and Bagh printers both mordant the cloth with alum.", names=names)
    assert both == CraftFiling(None, SKIP_SEVERAL_CRAFTS)
    in_kutch = filed("In Kutch the print is washed in Madhya's rivers.", names=names)
    assert in_kutch == CraftFiling(None, SKIP_SEVERAL_CRAFTS)
    plain = filed("Printers mordant the cloth with alum before the madder bath.", names=names)
    assert plain == CraftFiling(None, family=TEXTILE_FAMILY)


def test_a_craft_is_named_by_its_gi_place_but_not_by_its_state() -> None:
    names = names_for(AJRAKH)
    assert filed("In Kutch the cloth is washed twice.", field="PROCESS", names=names).slug == AJRAKH.slug
    assert filed("In Kachchh the cloth is washed twice.", field="PROCESS", names=names).slug == AJRAKH.slug
    assert filed("In Gujarat the cloth is washed twice.", field="PROCESS", names=names).refused == (
        SKIP_OTHER_PLACE.format(places="gujarat")
    )


def test_the_places_abroad_list_names_no_place_of_india_and_each_other_sense_holds_a_place() -> None:
    abroad = load_places_abroad()
    assert abroad.named_in("Indian potters in Khurja and Kutch") == ()
    assert abroad.named_in("Bone china and German silver from Persia") == ("Persia",)
    with pytest.raises(ValueError, match="names India"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"India": []}})
    with pytest.raises(ValueError, match="must hold a listed place word"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"Peru": []}, "otherSenses": ["china clay"]})
