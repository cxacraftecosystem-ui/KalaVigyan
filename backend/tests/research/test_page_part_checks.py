from app.research.page_layout import arranged_layout, is_picture_ref
from app.research.page_proposals import PART_KINDS, TRANSLATION
from app.services.page_part_checks import PART_CHECKS

from .test_page_layout import component, entry, layout, unit

PLAYER = "craft/chemistry/player"
MISSING = "shared/climate/jaipur-annual-rainfall-chart"


def test_every_part_kind_a_bundle_carries_is_checked_by_the_one_set_of_part_checks() -> None:
    assert set(PART_KINDS) == {*PART_CHECKS, TRANSLATION}


def test_a_layout_naming_a_component_the_page_lacks_arranges_the_page_without_it() -> None:
    default = [unit("chem", "u0001"), component("chem", PLAYER)]
    named = layout(entry(MISSING, "chem", 1, "FIGURE"), entry(PLAYER, "chem", 2, "FIGURE"))
    assert [placed.ref for placed in arranged_layout(default, named)] == [PLAYER, "u0001"]


def test_a_picture_is_named_by_its_page_s_pictures_segment() -> None:
    assert is_picture_ref("page-docs-test-craft/pictures/i01")
    assert not is_picture_ref(MISSING)
    assert not is_picture_ref("u0001")
