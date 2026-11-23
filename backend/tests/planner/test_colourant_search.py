from app.planner.colourants import asks_what_gives_a_colour
from app.planner.drafting import PlanDraft
from app.planner.plans import retrieval_plan
from app.research.crafts import CraftRef
from app.research.planning import FacetCoverage

from ..research.fixtures import AJRAKH
from .fakes import request

KHURJA = CraftRef(slug="Khurja-Pottery", name="Khurja Pottery", path="/crafts/Khurja-Pottery")
QUESTION = "What gives Khurja's glazes their blue and turquoise colours?"
COLOURANT = (
    "Khurja Pottery blue turquoise glaze colourant "
    "cobalt oxide copper oxide iron oxide manganese oxide chromium oxide"
)
OPEN = (FacetCoverage(facet_index=0), FacetCoverage(facet_index=1))


def draft(*extra: dict[str, object]) -> PlanDraft:
    return PlanDraft.model_validate(
        {
            "intent": "SCIENCE",
            "needsRegion": False,
            "facets": [
                {"type": "MECHANISM", "target": "glaze colour chemistry"},
                {"type": "MATERIAL", "target": "glaze colourants"},
            ],
            "queries": [
                {"facetIndex": 0, "tier": "T3", "text": "Khurja pottery glaze chemistry"},
                {"facetIndex": 1, "tier": "T4", "text": "Khurja blue glaze"},
                *extra,
            ],
        }
    )


def test_a_question_asking_what_gives_a_glaze_its_colour_searches_the_colourant_oxides() -> None:
    plan = retrieval_plan(request(question=QUESTION, craft=KHURJA), draft(), OPEN, mode="HYBRID")
    assert [(q.tier, q.facet_index, q.query.text) for q in plan.queries] == [
        ("T3", 0, "Khurja pottery glaze chemistry"),
        ("T4", 1, "Khurja blue glaze"),
        ("T3", 1, COLOURANT),
        ("T4", 1, COLOURANT),
    ]


def test_the_colourant_queries_stay_within_the_mode_s_query_limit() -> None:
    later = {"facetIndex": 0, "tier": "T3", "text": "Khurja kiln firing"}
    plan = retrieval_plan(request(question=QUESTION, craft=KHURJA), draft(later), OPEN, mode="HYBRID")
    assert len(plan.queries) == 4
    assert "Khurja kiln firing" not in [q.query.text for q in plan.queries]


def test_only_a_question_about_what_gives_a_mineral_surface_its_colour_asks_for_oxides() -> None:
    assert asks_what_gives_a_colour(QUESTION, KHURJA)
    assert asks_what_gives_a_colour("How is the blue glass of Firozabad coloured?", None)
    assert not asks_what_gives_a_colour("What gives Ajrakh its red colour?", AJRAKH)
    assert not asks_what_gives_a_colour("Which colours does Khurja use?", KHURJA)
    assert not asks_what_gives_a_colour("How are Khurja's glazes fired?", KHURJA)
    plan = retrieval_plan(request(question="What gives Ajrakh its red colour?"), draft(), OPEN, mode="HYBRID")
    assert len(plan.queries) == 2
