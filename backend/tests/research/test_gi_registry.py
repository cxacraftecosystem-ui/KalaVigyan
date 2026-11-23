from decimal import Decimal
from typing import Any

import pytest

from app.research.gi_registry import (
    GiFields,
    gi_fields,
    gi_status_name,
    merged_fields,
    names_registry,
    states_imitation,
)
from app.research.stated_prices import stated_prices

from ..contracts.phase_d_golden import phase_d_blocks


def stated(sentences: list[dict[str, Any]]) -> list[str]:
    return [text for s in sentences for text in (s["text"], *(c["quote"] for c in s["citations"]))]


def golden_fields(gi: dict[str, Any]) -> GiFields:
    return GiFields(
        application_number=gi["applicationNumber"],
        certificate_number=gi["certificateNumber"],
        filed_on=gi["filedOn"],
        registered_on=gi["registeredOn"],
        journal_issue=gi["journalIssue"],
        proprietors=tuple(gi["proprietors"]),
        authorised_user_count=gi["authorisedUserCount"],
    )


@pytest.mark.parametrize("block_id", ["s5.b1", "s5.b2"])
def test_the_fixture_s_gi_records_are_read_from_their_sentences_and_quotes(block_id: str) -> None:
    gi = phase_d_blocks()[block_id]["gi"]
    texts = stated(gi["sentences"])
    found = gi_fields(texts)
    assert found == golden_fields(gi)
    assert gi_status_name(found, texts) == gi["status"] == "REGISTERED"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Bastar Dhokra is registered as a geographical indication under application number 83, "
            "filed by the Chhattisgarh Hastshilp Vikas Board on 12 March 2007.",
            GiFields(application_number="83", filed_on="2007-03-12"),
        ),
        (
            "Application filed 16-04-2007, published in journal Supplementary 1 (available 24-03-2008), "
            "certificate no. 71 dated 10-07-2008, valid up to 15-04-2027.",
            GiFields(certificate_number="71", filed_on="2007-04-16", registered_on="2008-07-10"),
        ),
        (
            "| Applicant Name | Chhattisgarh Hastshilp Vikas Board | Journal Number | 24 |",
            GiFields(journal_issue="24", proprietors=("Chhattisgarh Hastshilp Vikas Board",)),
        ),
        (
            "The GI registry's record of application 83 lists 110 authorised users.",
            GiFields(application_number="83", authorised_user_count=110),
        ),
        ("The application was filed on 31-02-2023.", GiFields()),
        ("Journal Copy - 19-12-2023 | 19/12/2023", GiFields()),
    ],
)
def test_each_registry_field_is_read_by_its_label(text: str, expected: GiFields) -> None:
    assert gi_fields([text]) == expected


def test_two_texts_stating_different_numbers_give_no_record() -> None:
    assert gi_fields(["GI application 183 was filed.", "GI application 184 was filed."]) is None
    same = merged_fields([GiFields(proprietors=("The Board",)), GiFields(proprietors=("the board",))])
    assert same == GiFields(proprietors=("The Board",))


@pytest.mark.parametrize(
    ("found", "text", "status"),
    [
        (GiFields(application_number="1", certificate_number="2"), "", "REGISTERED"),
        (GiFields(application_number="845"), "Application 845 status is Pre Examination.", "APPLIED"),
        (GiFields(application_number="147"), "Application 147 appears in the registry list.", "APPLIED"),
        (GiFields(application_number="9"), "Kutch Ajrakh is a registered GI, application 9.", None),
        (GiFields(application_number="9"), "Application 9 was withdrawn.", "WITHDRAWN"),
        (GiFields(application_number="9", registered_on="2020-01-01"), "It was withdrawn.", None),
        (GiFields(journal_issue="188"), "Journal 188.", None),
    ],
)
def test_the_status_is_only_what_the_record_shows(found: GiFields, text: str, status: str | None) -> None:
    assert gi_status_name(found, [text]) == status


def test_a_logo_application_is_not_the_craft_s_registry_record() -> None:
    assert not names_registry("Logo application No. 505 was filed 08-01-2015 in Class 24.")
    assert names_registry("Bagru Hand Block Print is a registered GI (application 183).")
    assert not names_registry("Kutch Ajrakh is printed with natural dyes.")


@pytest.mark.parametrize(
    ("text", "imitation"),
    [
        ("Fake screen-printed Bagru textiles were being sold all over India.", True),
        ("Machine-made bindis replaced tikulis.", True),
        ("Power loom copies are passed off as Banarasi.", True),
        ("Ajrakh indigo is natural indigo or a synthesised substitute known as German indigo.", False),
        ("Ajrakh is printed in Ajrakhpur.", False),
    ],
)
def test_imitation_is_read_from_its_own_words(text: str, imitation: bool) -> None:
    assert states_imitation(text) is imitation


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "In Barmer an ajrakh piece was valued at Rs. 7 in 1975.",
            [("Rs. 7", Decimal(7), None, "INR", None, None)],
        ),
        (
            "In 2025 brass cost about ₹550 per kilogram in Kondagaon.",
            [("₹550", Decimal(550), None, "INR", None, "kilogram")],
        ),
        (
            "A tray was priced at Rs 800 and table mats at Rs 1000 to 2400.",
            [
                ("Rs 800", Decimal(800), None, "INR", None, None),
                ("Rs 1000 to 2400", Decimal(1000), Decimal(2400), "INR", None, None),
            ],
        ),
        ("A saree fetched 2 lakh rupees.", [("2 lakh rupees", Decimal(2), None, "INR", "LAKH", None)]),
        ("Exports sold at USD 15 per yard.", [("USD 15", Decimal(15), None, "USD", None, "yard")]),
        (
            "Kalamkari sold at Rs 1,500 a metre and Rs. 90 an hour of work.",
            [
                ("Rs 1,500", Decimal(1500), None, "INR", None, "metre"),
                ("Rs. 90", Decimal(90), None, "INR", None, "hour"),
            ],
        ),
        (
            "A basket cost Rs 50 a few years back and Rs 70 a year ago.",
            [
                ("Rs 50", Decimal(50), None, "INR", None, None),
                ("Rs 70", Decimal(70), None, "INR", None, None),
            ],
        ),
        ("It took 5 hours to print.", []),
        ("Prices fell from Rs 900 to 400.", []),
    ],
)
def test_a_price_is_a_currency_with_its_numbers_as_stated(text: str, expected: list[object]) -> None:
    found = [(p.stated, p.low, p.high, p.currency, p.scale, p.per) for p in stated_prices(text)]
    assert found == expected
