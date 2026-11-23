from app.data.english_words import load_english_words
from app.services.craft_index import AliasRecord, CraftRecord, build_index
from app.services.write_back_crafts import HELD_UNNAMED, CraftFiling, FilingTexts, craft_filing
from app.services.write_back_names import craft_names

from ..research.fixtures import AJRAKH
from .names import ALIASES, CRAFTS, KHURJA, MUD_FAMILY, PLACES, craft_id, ref

METAL_CASTING = ref("Metal-Casting", "Metal Casting")
BIDRIWARE = ref("Bidriware", "Bidriware")
BANDHANI = ref("Kutch-Bandhani", "Kutch Bandhani")
KALAMKARI = ref("Srikalahasthi-Kalamkari", "Srikalahasthi Kalamkari")
MORE_ALIASES = {
    METAL_CASTING: ("casting", "Cast metal"),
    BIDRIWARE: ("Bidri",),
    BANDHANI: ("Bandhani", "बांधनी"),
    KALAMKARI: ("Kalamkari",),
}
INDEX = build_index(
    [
        *(CraftRecord(craft_id(c.slug), c.slug, c.name, "ACTIVE", places=PLACES[c.slug]) for c in CRAFTS),
        *(CraftRecord(craft_id(c.slug), c.slug, c.name, "ACTIVE") for c in MORE_ALIASES),
    ],
    [
        *(AliasRecord(craft_id(slug), alias) for slug, aliases in ALIASES.items() for alias in aliases),
        *(AliasRecord(craft_id(c.slug), alias) for c, aliases in MORE_ALIASES.items() for alias in aliases),
    ],
    [],
)
KHURJA_NAMES = craft_names(INDEX, KHURJA, family=MUD_FAMILY)
TITLE = "Slip casting, pug mills and kilns in ceramic production"
MIXERS = "Modern equipment such as clay mixers and pug mills streamline clay preparation"
POLYMER = "Synthetic and polymer clays offer greater consistency, durability, and ease of use"
PORCELAIN = (
    "Porcelain is made by heating refined kaolinite clay in a kiln at temperatures between 1200 °C - 1400 °C"
)


def filed(sentence: str, *, field: str) -> CraftFiling:
    passage = f"{sentence}, and the body is then shaped by slip casting."
    texts = FilingTexts(f"{sentence}.", quotes=(sentence,), passages=(passage,), titles=(TITLE,))
    return craft_filing(texts, field=field, names=KHURJA_NAMES)


def test_clay_facts_whose_source_says_slip_casting_are_not_filed_under_metal_casting() -> None:
    assert filed(MIXERS, field="PROCESS") == CraftFiling(KHURJA.slug, held=HELD_UNNAMED)
    assert filed(POLYMER, field="PROCESS") == CraftFiling(KHURJA.slug, held=HELD_UNNAMED)
    assert filed(PORCELAIN, field="CHEMISTRY") == CraftFiling(None, family=MUD_FAMILY)


def test_an_ordinary_english_word_names_no_other_craft_but_its_full_name_and_longer_aliases_do() -> None:
    assert KHURJA_NAMES.catalogued(["The vase was made by slip casting."]) == []
    assert KHURJA_NAMES.catalogued(["Metal casting uses lost wax."]) == [METAL_CASTING]
    assert KHURJA_NAMES.catalogued(["Cast metal bells ring true."]) == [METAL_CASTING]


def test_a_distinctive_one_word_alias_still_names_its_craft() -> None:
    assert KHURJA_NAMES.catalogued(["Bidri inlay darkens with soil."]) == [BIDRIWARE]
    assert KHURJA_NAMES.catalogued(["Bandhani cloth is tied before dyeing."]) == [BANDHANI]
    assert KHURJA_NAMES.catalogued(["Ajrakh is printed on both sides."]) == [AJRAKH]
    assert KHURJA_NAMES.catalogued(["बांधनी"]) == [BANDHANI]


def test_the_researched_craft_is_not_named_by_an_ordinary_english_word_of_its_own_name() -> None:
    casting = craft_names(INDEX, METAL_CASTING)
    assert casting.researched(["The vase was made by slip casting."]) == []
    assert casting.researched(["Metal parts are joined."]) == []
    assert casting.researched(["Metal casting uses lost wax."]) == [METAL_CASTING]
    assert casting.researched(["Cast metal bells ring true."]) == [METAL_CASTING]
    texts = FilingTexts("The vase was made by slip casting.", titles=(TITLE,))
    assert craft_filing(texts, field="PROCESS", names=casting) == CraftFiling(
        METAL_CASTING.slug, held=HELD_UNNAMED
    )


def test_the_researched_craft_keeps_its_distinctive_one_word_names() -> None:
    bidri = craft_names(INDEX, BIDRIWARE)
    assert bidri.researched(["Bidri inlay darkens with soil."]) == [BIDRIWARE]
    assert bidri.researched(["Bidriware is cast from zinc."]) == [BIDRIWARE]
    assert craft_names(INDEX, KHURJA).researched(["Khurja glazes are blue."]) == [KHURJA]
    assert craft_names(INDEX, KHURJA).researched(["Pottery is fired."]) == []


def test_a_one_word_alias_three_crafts_share_in_their_names_names_none_of_them() -> None:
    assert KHURJA_NAMES.catalogued(["Kalamkari is drawn with a pen."]) == []
    assert KHURJA_NAMES.catalogued(["Srikalahasthi Kalamkari is drawn with a pen."]) == [KALAMKARI]


def test_the_vendored_english_words_hold_craft_techniques_and_no_craft_names() -> None:
    words = load_english_words()
    assert {"casting", "weaving", "carving", "printing", "pottery", "embroidery"} <= words
    assert not {"ajrakh", "bidri", "bandhani", "kalamkari", "phulkari"} & words
