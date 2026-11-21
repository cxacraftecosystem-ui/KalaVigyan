import json
from collections.abc import Sequence

from app.core.errors import ExternalFailure
from app.planner.understanding import ModelUnderstander, understood_seats
from app.research.coverage_seats import relevant_fields, uncovered_fields
from app.research.crafts import CraftQuery, CraftResolution
from app.research.expert_panel import speaking_seats
from app.research.understanding import UnderstandAsk

from ..research.fixtures import AJRAKH
from .fakes import FakeModel
from .test_understanding import RESOLVED

QUESTION = "Why does the red of the printed cloth last, and where do its plants grow?"
ASKED = ["CHEMISTRY", "HISTORY", "GEOGRAPHY", "BOTANY"]
HELD = ("CHEMISTRY", "HISTORY", "BOTANY", "SOCIETY")
REPLY = {"craft": "", "craftNames": [], "disciplines": ASKED, "seats": ["CHEMIST"]}


async def resolved(query: CraftQuery) -> CraftResolution:
    return RESOLVED


class Held:
    def __init__(self, fields: Sequence[str] | Exception) -> None:
        self.fields = fields
        self.asked: list[str] = []

    async def __call__(self, slug: str) -> Sequence[str]:
        self.asked.append(slug)
        if isinstance(self.fields, Exception):
            raise self.fields
        return self.fields


async def understood(held: Held, depth: str = "DETAILED") -> list[str]:
    understander = ModelUnderstander(model=FakeModel([json.dumps(REPLY)]), resolve=resolved, held=held)
    found = await understander.understand(UnderstandAsk(question=QUESTION, depth=depth))
    return list(found.seats)


async def test_every_field_the_question_touches_and_the_craft_holds_gets_a_speaking_seat() -> None:
    held = Held(HELD)
    seats = await understood(held)
    assert seats == ["CHEMIST", "HISTORIAN", "BOTANIST"]
    assert held.asked == [AJRAKH.slug]
    relevant = relevant_fields(ASKED, HELD)
    assert relevant == ("CHEMISTRY", "HISTORY", "BOTANY")
    assert uncovered_fields(relevant, seats) == ()
    assert all(speaking_seats(field, seats, depth="DETAILED") for field in relevant)


async def test_a_field_the_craft_holds_no_claims_in_takes_no_seat_of_its_own() -> None:
    seats = await understood(Held(HELD))
    assert speaking_seats("GEOGRAPHY", seats, depth="DETAILED") == ()


async def test_when_the_fields_held_cannot_be_read_every_asked_field_is_seated_within_the_limit() -> None:
    failing = Held(ExternalFailure("database timed out", kind="unavailable", service="database"))
    assert await understood(failing) == ["CHEMIST", "HISTORIAN", "HYDROLOGIST", "BOTANIST"]


async def test_the_expert_depth_keeps_the_model_s_seats_because_its_panel_widens_per_field() -> None:
    assert await understood(Held(HELD), depth="EXPERT") == ["CHEMIST"]
    assert understood_seats(ASKED, ["CHEMIST"], depth="EXPERT", held=HELD) == ["CHEMIST"]


def test_the_basic_depth_seats_at_most_two() -> None:
    assert understood_seats(ASKED, [], depth="BASIC", held=None) == ["CHEMIST", "HISTORIAN"]


def test_the_model_s_experts_never_crowd_out_a_field_the_question_asks_about() -> None:
    seats = understood_seats(["CHEMISTRY"], ["HYDROLOGIST", "GEOLOGIST"], depth="BASIC", held=None)
    assert seats == ["CHEMIST", "HYDROLOGIST"]
    assert speaking_seats("CHEMISTRY", seats, depth="BASIC") == ("CHEMIST",)
