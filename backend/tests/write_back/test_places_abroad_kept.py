import json

import pytest

from app.data.historical_sites import parse_historical_sites
from app.data.places_abroad import (
    HISTORICAL_SITES_FILE,
    PLACES_ABROAD_FILE,
    AbroadReading,
    load_places_abroad,
    parse_places_abroad,
)
from app.services.craft_index import AliasRecord, CraftRecord, build_index
from app.services.write_back_crafts import (
    HELD_OTHER_PLACE,
    SKIP_ABROAD,
    CraftFiling,
    FilingTexts,
    craft_filing,
)
from app.services.write_back_names import CraftNames, craft_names

from .names import KHURJA, MUD_FAMILY, craft_id, ref

AJANTA = ref("Ajanta-Painting", "Ajanta Painting")
CAMBAY = ref("Agates-Of-Cambay", "Agates of Cambay")
INDEX = build_index(
    [
        CraftRecord(craft_id(AJANTA.slug), AJANTA.slug, AJANTA.name, "ACTIVE", places=("Maharashtra",)),
        CraftRecord(craft_id(CAMBAY.slug), CAMBAY.slug, CAMBAY.name, "ACTIVE", places=("Gujarat",)),
        CraftRecord(craft_id(KHURJA.slug), KHURJA.slug, KHURJA.name, "ACTIVE", places=("Uttar Pradesh",)),
    ],
    [AliasRecord(craft_id(CAMBAY.slug), "Agates")],
    [],
)
LAPIS = "The blue pigment was lapis lazuli imported from Badakhshan in Afghanistan."
LAPIS_PASSAGE = (
    "The painters of the Ajanta caves used lapis lazuli from Badakhshan in Afghanistan for their blue."
)
CHANHU = (
    "Bead workshops of the Indus Civilization at Chanhu-daro, in present-day Pakistan, drilled long beads."
)
CHANHU_PASSAGE = "Long carnelian beads like those of Cambay were drilled at Chanhu-daro."
SUDAN = "Carnelian beads of this kind have been found at Kerma in Sudan."
SUDAN_PASSAGE = "Carnelian beads from Cambay have been found at Kerma in Sudan."


def names(lead=CAMBAY, abroad=None) -> CraftNames:
    return craft_names(INDEX, lead, family=MUD_FAMILY, abroad=abroad)


def filed(text: str, passage: str, *, lead=CAMBAY, field: str = "HISTORY", abroad=None) -> CraftFiling:
    texts = FilingTexts(text, passages=(passage,), titles=("Beads and pigments of India",))
    return craft_filing(texts, field=field, names=names(lead, abroad))


def test_a_material_s_origin_abroad_keeps_the_craft_its_source_names() -> None:
    assert filed(LAPIS, LAPIS_PASSAGE, lead=AJANTA, field="MATERIALS") == CraftFiling(AJANTA.slug)


def test_a_site_of_undivided_india_keeps_the_craft_its_source_names() -> None:
    assert filed(CHANHU, CHANHU_PASSAGE) == CraftFiling(CAMBAY.slug)


def test_without_the_historical_sites_the_present_country_refuses_the_same_sentence() -> None:
    bare = parse_places_abroad(json.loads(PLACES_ABROAD_FILE.read_text(encoding="utf-8")))
    assert filed(CHANHU, CHANHU_PASSAGE, abroad=bare) == CraftFiling(
        None, SKIP_ABROAD.format(places="Pakistan")
    )


def test_goods_found_abroad_keep_the_craft_its_source_names() -> None:
    assert filed(SUDAN, SUDAN_PASSAGE) == CraftFiling(CAMBAY.slug)


@pytest.mark.parametrize(
    ("text", "place"),
    [
        ("In Khorezm practice, clay is kneaded thoroughly by hand.", "Khorezm"),
        ("In a Nigerian porcelain study, the feldspar forms the liquid phase.", "Nigerian"),
        ("In Sudan, carnelian beads are drilled with a bow drill.", "Sudan"),
        ("Researchers found that Nigerian kaolin fires white.", "Nigerian"),
        ("In Afghanistan, painters grind lapis lazuli for their blue.", "Afghanistan"),
    ],
)
def test_practice_abroad_is_still_refused_whatever_its_source_names(text: str, place: str) -> None:
    assert filed(text, SUDAN_PASSAGE, field="PROCESS") == CraftFiling(None, SKIP_ABROAD.format(places=place))


def test_a_kept_place_abroad_with_no_craft_named_waits_for_a_reviewer_instead_of_the_family() -> None:
    texts = FilingTexts("Porcelain from China is fired hard.")
    filing = craft_filing(texts, field="MATERIALS", names=names(KHURJA))
    assert filing == CraftFiling(KHURJA.slug, held=HELD_OTHER_PLACE.format(places="China"))


def test_the_reading_tells_practice_from_origin_trade_and_history() -> None:
    abroad = load_places_abroad()
    assert abroad.read(LAPIS) == AbroadReading((), ("Afghanistan",))
    assert abroad.read("Indian carnelian was exported to Mesopotamia.") == AbroadReading((), ("Mesopotamia",))
    assert abroad.read(CHANHU) == AbroadReading((), ("Pakistan",))
    assert abroad.read("Potters in Pakistan glaze tiles blue.") == AbroadReading(("Pakistan",), ())
    assert abroad.read("Cobalt from Persia; in Persia potters paint it.") == AbroadReading(("Persia",), ())


def test_the_historical_sites_name_their_source_and_lie_in_countries_listed_abroad() -> None:
    raw = json.loads(HISTORICAL_SITES_FILE.read_text(encoding="utf-8"))
    assert (raw["source"]["name"], raw["source"]["licence"]) == ("Wikidata", "CC0-1.0")
    assert {site["country"] for site in raw["sites"]} <= {"Pakistan", "Bangladesh", "Afghanistan"}
    sites = load_places_abroad().history
    for name in ("chanhu daro", "mohenjo daro", "harappa", "taxila", "mahasthangarh", "gandhara"):
        assert name in sites.countries
    assert sites.countries["mahasthangarh"] == frozenset({"bangladesh", "bangladeshi"})
    with pytest.raises(ValueError, match="not listed abroad: Atlantis"):
        parse_historical_sites(
            {**raw, "cultures": [], "sites": [{"name": "Kerma", "country": "Atlantis"}]}, {}
        )
    with pytest.raises(ValueError, match="name their source"):
        parse_historical_sites({**raw, "source": {}}, {})
