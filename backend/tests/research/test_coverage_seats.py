from app.research.coverage_chapters import FIELD_CHAPTERS
from app.research.coverage_seats import FIELD_LEADS, covering_seats, relevant_fields, uncovered_fields


def test_each_field_is_led_by_the_seat_that_lists_it_first() -> None:
    assert dict(FIELD_LEADS) == {
        "OVERVIEW": "HISTORIAN",
        "PROCESS": "TECHNOLOGIST",
        "CHEMISTRY": "CHEMIST",
        "PHYSICS": "PHYSICIST",
        "MATERIALS": "MATERIALS_SCIENTIST",
        "GEOGRAPHY": "HYDROLOGIST",
        "GEOLOGY": "GEOLOGIST",
        "CLIMATE": "CLIMATOLOGIST",
        "ECOLOGY": "ECOLOGIST",
        "BOTANY": "BOTANIST",
        "HISTORY": "HISTORIAN",
        "ECONOMICS": "ECONOMIST",
        "DESIGN": "DESIGN_HISTORIAN",
        "HEALTH": "TOXICOLOGIST",
        "SOCIETY": "ANTHROPOLOGIST",
        "POLICY": "POLICY_EXPERT",
    }


def test_the_chosen_seats_stay_and_a_lead_is_added_for_each_field_they_leave_out() -> None:
    seats = covering_seats(["CHEMISTRY", "HISTORY", "GEOGRAPHY"], ["CHEMIST"], limit=4)
    assert seats == ("CHEMIST", "HISTORIAN", "HYDROLOGIST")
    assert uncovered_fields(["CHEMISTRY", "HISTORY", "GEOGRAPHY"], seats) == ()


def test_one_added_seat_can_serve_several_fields_and_the_limit_holds() -> None:
    assert covering_seats(["HISTORY", "OVERVIEW"], [], limit=4) == ("HISTORIAN",)
    assert covering_seats(["CHEMISTRY", "HISTORY", "CLIMATE"], ["BOTANIST"], limit=2) == (
        "BOTANIST",
        "CHEMIST",
    )
    assert covering_seats(["CHEMISTRY"], ["HYDROLOGIST", "GEOLOGIST", "ECOLOGIST"], limit=2) == (
        "HYDROLOGIST",
        "GEOLOGIST",
    )


def test_the_artisans_voice_speaks_for_no_field_and_unknown_seats_are_dropped() -> None:
    assert covering_seats(["PROCESS"], ["ARTISAN", "ORACLE"], limit=4) == ("ARTISAN", "TECHNOLOGIST")
    assert uncovered_fields(["PROCESS", "DESIGN"], ["ARTISAN"]) == ("PROCESS", "DESIGN")


def test_relevant_fields_are_those_asked_that_the_craft_holds_claims_in() -> None:
    asked = ["CHEMISTRY", "HISTORY", "CHEMISTRY", "GEOLOGY"]
    assert relevant_fields(asked, None) == ("CHEMISTRY", "HISTORY", "GEOLOGY")
    assert relevant_fields(asked, ("HISTORY", "GEOLOGY", "BOTANY")) == ("HISTORY", "GEOLOGY")
    assert relevant_fields(asked, ()) == ()


def test_every_field_is_placed_in_the_chapter_rule_23_names() -> None:
    assert dict(FIELD_CHAPTERS) == {
        "OVERVIEW": "glance",
        "PROCESS": "made",
        "CHEMISTRY": "chem",
        "PHYSICS": "chem",
        "MATERIALS": "made",
        "GEOGRAPHY": "why",
        "GEOLOGY": "why",
        "CLIMATE": "why",
        "ECOLOGY": "why",
        "BOTANY": "chem",
        "HISTORY": "history",
        "ECONOMICS": "market",
        "DESIGN": "people",
        "HEALTH": "made",
        "SOCIETY": "people",
        "POLICY": "market",
    }
