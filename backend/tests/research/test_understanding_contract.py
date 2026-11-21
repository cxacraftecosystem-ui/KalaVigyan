import pytest
from pydantic import ValidationError

from app.research import stream
from app.research.understanding import UnderstandAsk, Understanding

from .fixtures import AJRAKH, BAGRU

FIELDS = {
    "craft": AJRAKH,
    "candidates": [BAGRU],
    "disciplines": ["CHEMISTRY"],
    "seats": ["CHEMIST", "BOTANIST"],
    "depth": "BASIC",
    "language": "hi",
    "basis": "MODEL",
}


def understanding(**changes: object) -> Understanding:
    return Understanding.model_validate({**FIELDS, **changes})


def test_the_understood_event_names_the_chosen_craft_and_the_offers() -> None:
    frame = stream.event_frame("understood", understanding().understood())
    assert frame == (
        "event: understood\n"
        'data: {"crafts":[{"slug":"Kutch-Ajrakh","name":"Kutch Ajrakh","path":"/crafts/Kutch-Ajrakh"}],'
        '"candidates":[{"slug":"Bagru-Print","name":"Bagru Print","path":"/crafts/Bagru-Print"}],'
        '"depth":"BASIC","language":"hi"}\n\n'
    )


def test_any_craft_is_an_empty_craft_list() -> None:
    event = understanding(craft=None, candidates=[]).understood()
    assert (event.crafts, event.candidates) == ([], [])


def test_the_stored_understanding_keeps_its_seats_and_fields() -> None:
    assert understanding().model_dump(mode="json", by_alias=True) == {
        "schemaVersion": 1,
        "craft": AJRAKH.model_dump(),
        "candidates": [BAGRU.model_dump()],
        "disciplines": ["CHEMISTRY"],
        "seats": ["CHEMIST", "BOTANIST"],
        "depth": "BASIC",
        "language": "hi",
        "basis": "MODEL",
    }


@pytest.mark.parametrize(
    "changes",
    [
        {"candidates": [AJRAKH]},
        {"disciplines": ["CHEMISTRY", "CHEMISTRY"]},
        {"seats": ["CHEMIST", "BOTANIST", "HISTORIAN"]},
        {"disciplines": []},
        {"refusal": "The monthly AI budget has been reached."},
        {"seats": ["SOOTHSAYER"]},
        {"english_question": "?"},
    ],
)
def test_an_inconsistent_understanding_does_not_construct(changes: dict) -> None:
    with pytest.raises(ValidationError):
        understanding(**changes)


def test_a_resolver_understanding_knows_the_craft_and_may_carry_a_refusal() -> None:
    refused = understanding(basis="RESOLVER", disciplines=[], seats=[], refusal="Budget reached.")
    assert refused.refusal == "Budget reached."


def test_a_resolver_understanding_keeps_the_fields_the_question_s_words_name_and_their_seats() -> None:
    read = understanding(basis="RESOLVER", disciplines=["CHEMISTRY", "MATERIALS"], seats=["CHEMIST"])
    assert (read.disciplines, read.seats) == (["CHEMISTRY", "MATERIALS"], ["CHEMIST"])


def test_the_english_rendering_every_search_reads_is_stored_with_the_understanding() -> None:
    rendered = understanding(english_question="Why is alum added in Ajrakh?")
    assert (
        rendered.model_dump(mode="json", by_alias=True)["englishQuestion"] == "Why is alum added in Ajrakh?"
    )
    assert "englishQuestion" not in understanding().model_dump(mode="json", by_alias=True)


def test_a_question_names_one_craft_or_any_craft() -> None:
    with pytest.raises(ValidationError):
        UnderstandAsk(question="Why alum?", depth="BASIC", craft_slug="Kutch-Ajrakh", any_craft=True)
    with pytest.raises(ValidationError):
        UnderstandAsk(question="Why alum?", depth="DEEP")
    assert UnderstandAsk(question="Why alum?", depth="EXPERT", any_craft=True).language == "en"
