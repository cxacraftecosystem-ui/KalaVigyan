import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.craft_contributed import ContributedPlate, contributed_credit
from app.research.craft_parts import ContributedPart

PICTURE = uuid.UUID("5c0e0000-0000-4000-8000-000000000001")
OTHER = uuid.UUID("5c0e0000-0000-4000-8000-000000000002")
STAGE = uuid.UUID("5c0e0000-0000-4000-8000-000000000003")
CITATION = {
    "id": "q1",
    "claimId": str(uuid.UUID(int=9)),
    "sourceId": "s1",
    "quote": "The cloth is washed in the river.",
    "locator": "p. 2",
    "context": None,
    "evidence": "QUOTED",
    "level": "PROVISIONAL",
}
PLATE_FIELDS = {
    "contributionId",
    "url",
    "mime",
    "width",
    "height",
    "origin",
    "madeWith",
    "caption",
    "altText",
    "credit",
    "stageId",
    "sentences",
}


def plate(**changes: Any) -> dict[str, Any]:
    values: dict[str, Any] = {
        "contributionId": str(PICTURE),
        "url": f"/api/crafts/contributed/{PICTURE}",
        "mime": "image/jpeg",
        "width": 1200,
        "height": 800,
        "origin": "PHOTOGRAPH",
        "madeWith": None,
        "caption": "Cloth drying on the riverbank after its wash",
        "altText": "Long red and blue cloths laid out on sand beside a river",
        "credit": "Contributed to KalaVigyan",
        "stageId": str(STAGE),
        "sentences": [],
    }
    return values | changes


def sentence(level: str) -> dict[str, Any]:
    return {
        "id": "contributed-5c0e0000.1",
        "text": "The cloth is washed.",
        "level": level,
        "citations": [CITATION],
        "terms": [],
    }


def illustration(**changes: Any) -> dict[str, Any]:
    made = {
        "origin": "AI_GENERATED",
        "madeWith": "Midjourney v6",
        "credit": "Illustration, made with Midjourney v6",
        "mime": "image/png",
        "stageId": None,
    }
    return plate(**(made | changes))


def test_a_photograph_or_a_drawing_is_credited_to_kalavigyan_and_names_no_one() -> None:
    for origin in ("PHOTOGRAPH", "DRAWING"):
        shown = ContributedPlate.model_validate(plate(origin=origin))
        dumped = shown.model_dump(mode="json", by_alias=True)
        assert dumped["credit"] == "Contributed to KalaVigyan"
        assert set(dumped) == PLATE_FIELDS
    assert contributed_credit("DRAWING", None) == "Contributed to KalaVigyan"


def test_an_ai_image_is_always_an_illustration_made_with_its_tool() -> None:
    shown = ContributedPlate.model_validate(illustration())
    assert shown.credit == "Illustration, made with Midjourney v6"
    assert (
        contributed_credit("AI_GENERATED", "ChatGPT (GPT-4o)") == "Illustration, made with ChatGPT (GPT-4o)"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"credit": "Contributed to KalaVigyan"},
        {"credit": "Photograph"},
        {"madeWith": None, "credit": "Illustration, made with "},
    ],
    ids=["shown as a photograph", "labelled a photograph", "no tool named"],
)
def test_an_ai_image_shown_as_anything_but_its_illustration_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ContributedPlate.model_validate(illustration(**changes))


@pytest.mark.parametrize(
    "changes",
    [
        {"credit": "Photo: Asha Patel"},
        {"credit": "Photograph"},
        {"madeWith": "Midjourney v6"},
        {"url": f"/api/crafts/contributed/{OTHER}"},
        {"mime": "image/gif"},
        {"sentences": [sentence("HYPOTHESIS")]},
    ],
    ids=[
        "a person credited",
        "a label as credit",
        "a tool on a photograph",
        "another address",
        "a gif",
        "a hypothesis",
    ],
)
def test_a_photograph_credited_otherwise_or_served_elsewhere_is_refused(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ContributedPlate.model_validate(plate(**changes))


@pytest.mark.parametrize("mime", ["image/png", "image/jpeg", "image/webp", "image/avif", "image/svg+xml"])
def test_every_kept_picture_type_is_shown(mime: str) -> None:
    assert ContributedPlate.model_validate(plate(mime=mime)).mime == mime


def test_a_plate_shows_the_facts_it_illustrates() -> None:
    shown = ContributedPlate.model_validate(plate(sentences=[sentence("PROVISIONAL")]))
    assert [s.text for s in shown.sentences] == ["The cloth is washed."]


def test_a_shelf_draws_each_picture_once_and_at_most_six() -> None:
    other = plate(contributionId=str(OTHER), url=f"/api/crafts/contributed/{OTHER}")
    assert (
        len(ContributedPart.model_validate({"kind": "contributed", "pictures": [plate(), other]}).pictures)
        == 2
    )
    with pytest.raises(ValidationError):
        ContributedPart.model_validate({"kind": "contributed", "pictures": [plate(), plate()]})
    many = [
        plate(contributionId=str(uuid.UUID(int=n)), url=f"/api/crafts/contributed/{uuid.UUID(int=n)}")
        for n in range(1, 8)
    ]
    with pytest.raises(ValidationError):
        ContributedPart.model_validate({"kind": "contributed", "pictures": many})
    with pytest.raises(ValidationError):
        ContributedPart.model_validate({"kind": "contributed", "pictures": []})
