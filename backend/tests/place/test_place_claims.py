import uuid

from app.research.blocks_place import DistrictRef
from app.services.knowledge_view import ClaimView
from app.services.place_claims import PLACE_CONCEPT_TYPE, ranked_place_views

KACHCHH = DistrictRef(district_lgd=449, name="Kachchh", state_name="Gujarat", other_names=["Kutch"])


def view(
    n: int, text: str, *, rank: float, concept_type: str = PLACE_CONCEPT_TYPE, quote: str = ""
) -> ClaimView:
    citation = {"id": str(uuid.UUID(int=100 + n)), "sourceId": "s", "quote": quote or None}
    return ClaimView(
        id=uuid.UUID(int=n),
        text=text,
        level="PROVISIONAL",
        concept_type=concept_type,
        concept_id=None,
        rank=rank,
        citations=[citation],
    )


def test_place_claims_naming_a_craft_district_come_first_then_by_the_question_s_rank() -> None:
    views = [
        view(1, "Groundwater in the plains is saline.", rank=0.9),
        view(2, "The Rann floods each monsoon.", rank=0.2, quote="the Rann of Kutch floods"),
        view(3, "Dyers in Kachchh use well water.", rank=0.1),
        view(4, "Madder roots are dried.", rank=0.95, concept_type="MATERIAL"),
        view(5, "Kachchh receives little rain.", rank=0.5),
        view(6, "The river dried by 1989.", rank=0.3),
    ]
    ranked = ranked_place_views(views, [KACHCHH], held=[uuid.UUID(int=6)])
    assert [found.id.int for found in ranked] == [5, 2, 3, 1]


def test_without_districts_place_claims_follow_the_question_s_rank_alone() -> None:
    views = [view(1, "Low rank.", rank=0.1), view(2, "High rank.", rank=0.8), view(3, "Also high.", rank=0.8)]
    assert [found.id.int for found in ranked_place_views(views, [])] == [3, 2, 1]
