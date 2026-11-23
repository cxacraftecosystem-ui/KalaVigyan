from typing import Any

from app.research.explainer import Explainer
from app.research.sections import section_specs
from app.services.explainer_events import ExplainerStream
from app.services.section_headings import headed_specs

from ..contracts.explainer_golden import DOCUMENT, golden_json
from .fakes import translation

HEADING = "Green out of the vat, blue in the air"
SUPPORTS = ["Cloth lifted from the indigo vat is bright green at first and turns blue in the air."]


async def ignored(name: str, data: Any) -> None:
    return None


async def test_three_sections_proposing_one_heading_show_it_once() -> None:
    stream = ExplainerStream(ignored, language="en")
    specs = section_specs(["CHEMISTRY", "OVERVIEW", "PROCESS"], "DETAILED")
    headed = await headed_specs(
        {spec.id: HEADING for spec in specs},
        [(spec, SUPPORTS) for spec in specs],
        language="en",
        translation=translation(),
        claim=stream.claim_heading,
    )
    assert [one.shown for one in headed] == [HEADING, None, None]
    assert [one.spec.title for one in headed[1:]] == [spec.title for spec in specs[1:]]


def test_a_heading_is_a_section_s_own_whatever_its_case_and_a_section_may_keep_it() -> None:
    stream = ExplainerStream(ignored, language="en")
    assert stream.claim_heading("s1", HEADING)
    assert stream.claim_heading("s1", HEADING)
    assert not stream.claim_heading("s5", "green out of the vat: blue in the air")
    assert stream.claim_heading("s5", "Soluble in the vat, blue and fixed in the air")


def test_a_follow_up_s_new_section_does_not_take_a_heading_its_explainer_shows() -> None:
    stream = ExplainerStream(ignored, language="en")
    stream.shown_before(Explainer.model_validate(golden_json(DOCUMENT)).sections)
    assert not stream.claim_heading("s4", "Why the water matters")
    assert not stream.claim_heading("s4", "how it is made")
    assert stream.claim_heading("s2", "Why the water matters")
