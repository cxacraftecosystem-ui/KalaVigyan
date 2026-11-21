from app.research.sections import FALLBACK_DISCIPLINE, answer_fields, question_fields

HELD = ("OVERVIEW", "PROCESS", "CHEMISTRY")


def test_the_asked_fields_are_topped_up_to_the_depth_s_minimum_from_the_fields_held() -> None:
    assert answer_fields(["CHEMISTRY"], "DETAILED", HELD) == ["CHEMISTRY", "OVERVIEW", "PROCESS"]
    assert answer_fields(["CHEMISTRY", "HISTORY", "GEOGRAPHY"], "BASIC", HELD) == [
        "CHEMISTRY",
        "HISTORY",
        "GEOGRAPHY",
    ]
    assert answer_fields(["CHEMISTRY"], "EXPERT", HELD) == ["CHEMISTRY"]


def test_an_answer_with_no_field_at_all_still_says_what_its_craft_is() -> None:
    assert answer_fields([], "BASIC") == [FALLBACK_DISCIPLINE] == ["OVERVIEW"]
    assert answer_fields(["ASTROLOGY"], "DETAILED", ("ASTROLOGY",)) == ["OVERVIEW"]


def test_the_question_s_words_name_its_fields_leaving_the_craft_s_own_name_out() -> None:
    assert question_fields("Why does alum fix madder on cotton?") == ["CHEMISTRY", "MATERIALS"]
    assert question_fields("How is the water of Kutch Ajrakh kept clean?", "Kutch Ajrakh") == ["GEOGRAPHY"]
