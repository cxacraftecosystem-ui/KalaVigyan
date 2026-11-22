from app.composer.candidates import compose_request, research_summary
from app.composer.prompt import compose_message
from app.research.crafts import ANY_CRAFT_LINE, craft_block, craft_line
from app.research.research_summary import not_enough_evidence_message

from ..research.fixtures import AJRAKH
from .fixtures import PLAN, QUESTION, STORED, pack


def any_craft_pack():
    return pack(
        plan=PLAN.model_copy(update={"craft": None}), stored=STORED.model_copy(update={"craft_slug": None})
    )


def test_the_craft_line_names_the_craft_or_says_any_craft() -> None:
    assert craft_line(AJRAKH) == craft_block(AJRAKH)
    assert craft_line(None) == "Craft: any craft (the question names none on the list)" == ANY_CRAFT_LINE


def test_a_composer_for_any_craft_is_told_so_in_place_of_a_craft() -> None:
    request = compose_request(any_craft_pack(), QUESTION)
    assert request.craft is None and request.searched.craft is None
    message = compose_message(request)
    assert message.split("\n")[:2] == ["Answer language: en", ANY_CRAFT_LINE]
    assert 'ref="craft"' not in message


def test_not_enough_evidence_for_any_craft_names_no_craft() -> None:
    message = not_enough_evidence_message(research_summary(any_craft_pack()))
    assert message.startswith(
        "There is not enough cited evidence to answer this yet. Searched 2 stored claims"
    )
