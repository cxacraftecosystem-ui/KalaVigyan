import pytest

from app.data.places_abroad import (
    load_places_abroad,
    load_sovereign_names,
    parse_places_abroad,
    parse_sovereign_names,
)
from app.services.write_back_crafts import (
    HELD_OTHER_PLACE,
    HELD_UNNAMED,
    SKIP_ABROAD,
    SKIP_SEVERAL_CATALOGUED,
    SKIP_SEVERAL_CRAFTS,
    CraftFiling,
    FilingTexts,
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
KHURJA_STUDY = "Clay bodies and glazes of Khurja pottery"
BAGH_BOILED = "Bagh print cloth is boiled with alum and madder for three hours."
ANY_CRAFT = names_for(None, family=None)


def filed(text: str, *quotes: str, field: str | None = "MATERIALS", names=KHURJA_NAMES) -> CraftFiling:
    return craft_filing(FilingTexts(text, tuple(quotes)), field=field, names=names)


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


def test_a_statement_naming_no_craft_outside_material_science_is_held_for_the_craft_researched() -> None:
    assert filed(KILN_SCHEDULE, field="PROCESS") == CraftFiling(KHURJA.slug, held=HELD_UNNAMED)
    assert filed(KILN_SCHEDULE, field="PHYSICS") == CraftFiling(None, family=MUD_FAMILY)
    assert filed(POLYMER, field="HISTORY") == CraftFiling(KHURJA.slug, held=HELD_UNNAMED)


def test_without_a_family_material_science_naming_no_craft_is_held() -> None:
    names = names_for(KHURJA, family=None)
    assert filed(PORCELAIN, names=names) == CraftFiling(KHURJA.slug, held=HELD_UNNAMED)


def test_a_fact_naming_another_catalogued_craft_goes_to_that_craft() -> None:
    text = "Jaipur blue pottery is made of quartz frit rather than clay."
    assert filed(text, field="PROCESS") == CraftFiling(BLUE_POTTERY.slug)


def test_a_fact_naming_another_indian_place_but_no_craft_is_held() -> None:
    assert filed("Clays from Azamgarh fire black.") == CraftFiling(
        KHURJA.slug, held=HELD_OTHER_PLACE.format(places="azamgarh")
    )
    assert filed("In Uttar Pradesh, kaolin is fired white.").held == HELD_OTHER_PLACE.format(
        places="uttar pradesh"
    )


def test_a_place_word_in_another_sense_names_no_place_abroad() -> None:
    assert filed("China clay is kaolinite, which fires white.") == CraftFiling(None, family=MUD_FAMILY)
    assert filed("Turkey red is an alizarin lake on oiled cotton.").family == MUD_FAMILY
    assert filed("Porcelain in China is fired hard.").refused == SKIP_ABROAD.format(places="China")


def test_names_match_as_whole_words() -> None:
    assert filed("The Khurjan kiln is fired with wood.", field="PROCESS") == CraftFiling(
        KHURJA.slug, held=HELD_UNNAMED
    )
    assert filed("Ochre gives a brown colour.") == CraftFiling(None, family=MUD_FAMILY)


def test_research_for_any_craft_files_a_fact_naming_one_catalogued_craft_under_that_craft() -> None:
    assert filed(BAGH_BOILED, field="PROCESS", names=ANY_CRAFT) == CraftFiling(BAGH.slug)
    blue = "Jaipur blue pottery is made of quartz frit rather than clay."
    assert filed(blue, names=ANY_CRAFT) == CraftFiling(BLUE_POTTERY.slug)


def test_research_for_any_craft_refuses_a_fact_naming_several_crafts_or_a_practice_abroad() -> None:
    both = filed("Khurja pottery and Jaipur blue pottery both use quartz.", names=ANY_CRAFT)
    assert both == CraftFiling(
        None, SKIP_SEVERAL_CATALOGUED.format(crafts="Blue Pottery of Jaipur, Khurja Pottery")
    )
    assert filed(KHOREZM, names=ANY_CRAFT) == CraftFiling(None, SKIP_ABROAD.format(places="Khorezm"))


def test_research_for_any_craft_reads_the_passage_then_the_title_when_the_sentence_names_no_craft() -> None:
    unnamed = "The cloth is boiled with alum and madder for three hours."
    passage = FilingTexts(unnamed, passages=(BAGH_BOILED,), titles=(KHURJA_STUDY,))
    assert craft_filing(passage, field="PROCESS", names=ANY_CRAFT) == CraftFiling(BAGH.slug)
    titled = FilingTexts(unnamed, titles=("Bagh Prints of Madhya Pradesh: dyeing with alum",))
    assert craft_filing(titled, field="PROCESS", names=ANY_CRAFT) == CraftFiling(BAGH.slug)


def test_research_for_any_craft_keeps_what_names_no_craft_on_the_shared_concepts() -> None:
    plain = "Printers boil the cloth with alum and madder for three hours."
    assert filed(plain, field="PROCESS", names=ANY_CRAFT) == CraftFiling(None)
    assert filed("Clays from Azamgarh fire black.", names=ANY_CRAFT) == CraftFiling(None)
    assert filed(PORCELAIN, names=ANY_CRAFT) == CraftFiling(None)


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
    assert filed("In Gujarat the cloth is washed twice.", field="PROCESS", names=names) == CraftFiling(
        AJRAKH.slug, held=HELD_OTHER_PLACE.format(places="gujarat")
    )


def test_the_places_abroad_list_names_no_place_of_india_and_each_other_sense_holds_a_place() -> None:
    abroad = load_places_abroad()
    assert abroad.named_in("Indian potters in Khurja and Kutch") == ()
    assert abroad.named_in("Bone china and German silver from Persia") == ("Persia",)
    with pytest.raises(ValueError, match="names India"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"India": []}})
    with pytest.raises(ValueError, match="must hold a listed place word"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"Peru": []}, "otherSenses": ["china clay"]})


def test_every_sovereign_state_natural_earth_lists_is_a_place_abroad_or_left_out_for_a_reason() -> None:
    abroad = load_places_abroad()
    names = load_sovereign_names()
    assert len(names) == 197
    assert [name for name in names if not abroad.accounts_for(name)] == []
    assert abroad.accounts_for("United Republic of Tanzania") and abroad.accounts_for("Mali")
    assert abroad.named_in("Potters of Mali and Tonga") == ()
    assert not abroad.accounts_for("Khurja")


def test_a_name_left_out_says_why_and_is_not_also_listed() -> None:
    with pytest.raises(ValueError, match="left out but listed: Peru"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"Peru": []}, "leftOut": {"Peru": "a reason"}})
    with pytest.raises(ValueError, match="says why: Mali"):
        parse_places_abroad({"schemaVersion": 1, "countries": {"Peru": []}, "leftOut": {"Mali": ""}})
    with pytest.raises(ValueError, match="leave India out"):
        parse_sovereign_names({"schemaVersion": 1, "names": ["Peru", "India"]})


def test_the_sentence_s_own_words_decide_before_its_passage_and_its_source_s_title() -> None:
    texts = FilingTexts(
        "In Uttar Pradesh, kaolin is fired white.",
        passages=("Jaipur blue pottery is fired once.",),
        titles=(KHURJA_STUDY,),
    )
    assert craft_filing(texts, field="PROCESS", names=KHURJA_NAMES) == CraftFiling(
        KHURJA.slug, held=HELD_OTHER_PLACE.format(places="uttar pradesh")
    )


def test_a_passage_decides_before_the_title_and_a_place_in_the_passage_alone_holds_the_fact() -> None:
    blue = FilingTexts(
        "The body is fired once.", passages=("Jaipur blue pottery is fired once.",), titles=(KHURJA_STUDY,)
    )
    assert craft_filing(blue, field="PROCESS", names=KHURJA_NAMES) == CraftFiling(BLUE_POTTERY.slug)
    elsewhere = FilingTexts(
        "The clay is aged.", passages=("Clays from Azamgarh are aged.",), titles=(KHURJA_STUDY,)
    )
    assert craft_filing(elsewhere, field="PROCESS", names=KHURJA_NAMES) == CraftFiling(KHURJA.slug)
    untitled = FilingTexts("The clay is aged.", passages=("Clays from Azamgarh are aged.",))
    assert craft_filing(untitled, field="CHEMISTRY", names=KHURJA_NAMES) == CraftFiling(
        KHURJA.slug, held=HELD_OTHER_PLACE.format(places="azamgarh")
    )


def test_a_title_from_abroad_refuses_what_its_passage_left_unnamed() -> None:
    texts = FilingTexts("Feldspar melts first.", titles=("Characterisation of Nigerian porcelain bodies",))
    assert craft_filing(texts, field="CHEMISTRY", names=KHURJA_NAMES) == CraftFiling(
        None, SKIP_ABROAD.format(places="Nigerian")
    )
