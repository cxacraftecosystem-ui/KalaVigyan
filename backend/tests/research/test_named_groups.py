import pytest

from app.research.named_groups import NAMED_GROUP_KINDS, group_name_key, names_a_listed_group

LISTED = ("Khatri", "Ismail Mohammad Khatri", "Bhil")


@pytest.mark.parametrize(
    "text",
    [
        "The Khatri community prints Ajrakh.",
        "Khatris print the resist by hand.",
        "KHATRI printers wash the cloth.",
        "Designed by Ismail  Mohammad\nKhatri in Ajrakhpur.",
        "Most of the miners are local Bhil tribals.",
        "The Khatri's workshop stands by the river.",
    ],
)
def test_a_listed_name_is_found_in_any_case_spacing_or_plural(text: str) -> None:
    assert names_a_listed_group(text, LISTED)


@pytest.mark.parametrize(
    "text",
    [
        "Alum fixes the red dye to the cotton.",
        "The Kharif crop ripens after the rains.",
        "Bhilala women wear the printed cloth.",
        "Indigo is reduced in the vat.",
    ],
)
def test_an_unlisted_ordinary_word_passes(text: str) -> None:
    assert not names_a_listed_group(text, LISTED)


def test_no_names_and_blank_names_name_nothing() -> None:
    assert not names_a_listed_group("The Khatri community prints Ajrakh.", ())
    assert not names_a_listed_group("The Khatri community prints Ajrakh.", ("", "   "))


def test_a_name_s_key_is_case_folded_with_its_spaces_collapsed() -> None:
    assert group_name_key("  Ismail   Mohammad KHATRI ") == "ismail mohammad khatri"
    assert NAMED_GROUP_KINDS == ("COMMUNITY", "PERSON")
