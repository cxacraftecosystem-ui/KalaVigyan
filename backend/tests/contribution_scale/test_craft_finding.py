import pytest

from app.research.craft_finding import CraftSignals, finder_score, query_words, ranked_crafts, standing_score
from app.research.crafts import CraftRef


def craft(slug: str, name: str) -> CraftRef:
    return CraftRef(slug=slug, name=name, path=f"/crafts/{slug}")


METAL_CASTING = CraftSignals(
    craft=craft("Metal-Casting", "Metal Casting"), lexical=1.0, named_words=frozenset({"metal", "casting"})
)
DHOKRA = CraftSignals(
    craft=craft("Bastar-Dhokra", "Bastar Dhokra"),
    held_words=frozenset({"bell", "metal", "casting"}),
    held_hits=14,
    curated=True,
    claims=120,
    fields=11,
)
SARTHEBARI = CraftSignals(
    craft=craft("Sarthebari-Bell-Metal-Craft", "Sarthebari Bell Metal Craft"),
    lexical=0.7,
    named_words=frozenset({"bell", "metal"}),
)
BANARAS = CraftSignals(
    craft=craft("Banaras-Metal-Casting-Craft", "Banaras Metal Casting Craft"),
    lexical=0.6,
    named_words=frozenset({"metal", "casting"}),
    held_words=frozenset({"metal"}),
    held_hits=2,
    claims=4,
    fields=4,
)
AJRAKH = CraftSignals(
    craft=craft("Kutch-Ajrakh", "Kutch Ajrakh"), lexical=0.97, named_words=frozenset({"ajrakh"})
)
EVERYONE = (METAL_CASTING, DHOKRA, SARTHEBARI, BANARAS, AJRAKH)
GOLDEN = [
    (
        "bell metal casting",
        ["Bastar-Dhokra", "Banaras-Metal-Casting-Craft", "Metal-Casting", "Sarthebari-Bell-Metal-Craft"],
    ),
    (
        "Metal Casting",
        ["Metal-Casting", "Banaras-Metal-Casting-Craft", "Bastar-Dhokra", "Sarthebari-Bell-Metal-Craft"],
    ),
    ("Ajrakh", ["Kutch-Ajrakh"]),
    ("ajrak", ["Kutch-Ajrakh"]),
]


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("Bell-metal casting of India", ("bell", "metal", "casting")),
        ("the CRAFT of lost wax", ("lost", "wax")),
        ("अजरख", ()),
    ],
)
def test_the_query_s_content_words_are_kept_and_generic_ones_dropped(
    text: str, words: tuple[str, ...]
) -> None:
    assert query_words(text) == words


def test_curated_crafts_stand_highest_and_an_empty_row_stands_nowhere() -> None:
    assert standing_score(DHOKRA) == 1.0
    assert standing_score(METAL_CASTING) == 0.0
    assert standing_score(BANARAS) == 0.625


def test_a_name_counts_only_for_the_query_words_it_covers() -> None:
    words = query_words("bell metal casting")
    assert finder_score(METAL_CASTING, words) == pytest.approx(0.55 * 2 / 3, abs=1e-6)
    assert finder_score(DHOKRA, words) == pytest.approx(0.30 + 0.15, abs=1e-6)
    assert finder_score(SARTHEBARI, words) == pytest.approx(0.55 * 0.7 * 2 / 3, abs=1e-6)
    assert finder_score(BANARAS, words) == pytest.approx(
        0.55 * 0.6 * 2 / 3 + 0.30 / 3 + 0.15 * 0.625, abs=1e-6
    )


def test_a_query_that_is_a_craft_s_whole_name_puts_that_craft_first() -> None:
    words = query_words("Metal Casting")
    assert finder_score(METAL_CASTING, words) == pytest.approx(0.55 + 0.10, abs=1e-6)
    assert finder_score(BANARAS, words) == pytest.approx(0.55 * 0.6 + 0.30 / 2 + 0.15 * 0.625, abs=1e-6)


@pytest.mark.parametrize(("query", "order"), GOLDEN)
def test_the_golden_list(query: str, order: list[str]) -> None:
    found = ranked_crafts(EVERYONE, query_words(query))
    assert [scored.signals.craft.slug for scored in found] == order
