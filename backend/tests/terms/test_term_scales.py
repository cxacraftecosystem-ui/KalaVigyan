import pytest

from app.models.enums import TERM_ZOOM_LEVELS
from app.research.blocks_journey import ZOOM_LEVELS
from app.services.term_scales import SCALE_WORDS, scale_stripped, stated_zoom_level


@pytest.mark.parametrize(
    ("label", "meaning", "level"),
    [
        ("Nettle Fibre", "fine, short textile fiber from the bast of nettles (Urica sp.)", "FIBRE"),
        ("Cotton cloth", "handloom", "CLOTH"),
        ("Lace", "openwork fabric, patterned with open holes in the work", "CLOTH"),
        ("kantan", "jute cloth", "CLOTH"),
        ("Surat Zari Craft", "textile made from yarns of silk and cotton mixed with gold", "CLOTH"),
        ("Bagru Hand Block Print", "traditional hand block printing of India", None),
        ("Kut", "iron-water black paste", None),
        ("Kora", None, None),
        ("Sizing", "a fibre coat laid on the cloth", None),
    ],
)
def test_a_term_s_level_is_the_one_scale_its_label_or_its_definition_states(
    label: str, meaning: str | None, level: str | None
) -> None:
    assert stated_zoom_level(label, meaning) == level


def test_the_fibre_a_tag_names_drops_the_scale_word_its_label_ends_with() -> None:
    assert scale_stripped("Nettle Fibre", "FIBRE") == "Nettle"
    assert scale_stripped("Fibre", "FIBRE") == "Fibre"
    assert scale_stripped("Banana Fibre", "FIBRE") == "Banana"


def test_every_tag_is_a_level_of_the_zoom_and_has_its_scale_words() -> None:
    assert set(TERM_ZOOM_LEVELS) <= set(ZOOM_LEVELS)
    assert "DISTRICT" not in TERM_ZOOM_LEVELS
    assert tuple(SCALE_WORDS) == TERM_ZOOM_LEVELS
