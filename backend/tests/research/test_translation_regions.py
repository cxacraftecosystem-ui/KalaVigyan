import pytest

from app.core.errors import InvalidInput
from app.research.open_work import parse_task_key
from app.research.page_translations import PageTranslationPart, task_problem
from app.research.translation_regions import home_languages, offered_languages, translation_priority

HASH = "c" * 64


@pytest.mark.parametrize(
    ("states", "offered"),
    [
        (["Gujarat"], ("gu", "hi")),
        (["Tamil Nadu", "Kerala"], ("ta", "ml", "hi")),
        (["Uttar Pradesh"], ("hi",)),
        (["Jammu and Kashmir"], ("ur", "hi")),
        (["West  bengal"], ("bn", "hi")),
        (["All India"], ("hi",)),
        (["Goa"], ("hi",)),
        ([], ("hi",)),
    ],
)
def test_a_craft_s_home_state_offers_its_language_first_and_hindi_always(
    states: list[str], offered: tuple[str, ...]
) -> None:
    assert offered_languages(states) == offered


def test_the_home_language_keeps_the_page_s_priority_and_hindi_comes_one_step_after() -> None:
    assert home_languages(["Odisha"]) == ("or",)
    assert translation_priority("HIGH", "or", ["Odisha"]) == "HIGH"
    assert translation_priority("HIGH", "hi", ["Odisha"]) == "MEDIUM"
    assert translation_priority("LOW", "hi", ["Odisha"]) == "LOW"
    assert translation_priority("MEDIUM", "hi", ["Rajasthan"]) == "MEDIUM"


def test_a_translate_task_key_names_its_page_and_language() -> None:
    task = parse_task_key("TRANSLATE:craft:Kutch-Ajrakh:gu")
    assert (task.kind, task.subject_kind, task.slug, task.detail) == (
        "TRANSLATE",
        "craft",
        "Kutch-Ajrakh",
        "gu",
    )
    with pytest.raises(InvalidInput, match="neither a field nor a component need"):
        parse_task_key("TRANSLATE:craft:Kutch-Ajrakh:en")
    page = ("craft", "Kutch-Ajrakh")
    assert task_problem("TRANSLATE:craft:kutch-ajrakh:gu", page, "gu") is None
    assert task_problem(None, page, "gu") is None
    other = task_problem("TRANSLATE:craft:Kutch-Ajrakh:hi", page, "gu")
    assert other == (
        "TRANSLATE:craft:Kutch-Ajrakh:hi is not the TRANSLATE task of this part: name "
        "TRANSLATE:craft:Kutch-Ajrakh:gu, or no task_key."
    )


def test_a_translation_part_keeps_each_text_s_spaces_and_names_each_passage_once() -> None:
    part = PageTranslationPart.model_validate(
        {"language": "hi", "passages": [{"key": "u1", "source_hash": HASH, "texts": ["रंग ", " झाड़ी है।"]}]}
    )
    assert part.passages[0].texts == ["रंग ", " झाड़ी है।"]
    with pytest.raises(ValueError, match="u1 is named twice"):
        PageTranslationPart.model_validate(
            {
                "language": "hi",
                "passages": [
                    {"key": "u1", "source_hash": HASH, "texts": ["एक"]},
                    {"key": "u1", "source_hash": HASH, "texts": ["दो"]},
                ],
            }
        )
    with pytest.raises(ValueError, match="language"):
        PageTranslationPart.model_validate(
            {"language": "en", "passages": [{"key": "u1", "source_hash": HASH, "texts": ["one"]}]}
        )
