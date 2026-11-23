from typing import Any

from pydantic import TypeAdapter

from app.models.knowledge_pieces import TITLE_COLUMN_CHARS
from app.research.composition import HEADING_MAX_CHARS
from app.research.explainer import Block, SectionHeadingEvent, SectionStartedEvent
from app.research.sections import section_specs
from app.services.answer_translation import translated_block
from app.services.explainer_events import ExplainerStream, shown_title
from app.services.follow_ups import AnswerLayout
from app.services.section_headings import headed_specs

from ..planner.fakes import FakeModel
from .fakes import translation
from .test_translation_flow import reply

BLOCK = TypeAdapter(Block)
HEADING = "Green out of the vat, blue in the air"
SUPPORTS = ["Cloth lifted from the indigo vat is bright green at first and turns blue in the air."]
TAMIL_WORD = "அவுரி "
LONG_TAMIL = (TAMIL_WORD * 25).strip()
SHORT_TAMIL = "அஜ்ரக் வேதியியல்"
HINDI_WORDS = "रंगबंधक स्नान और उनके तापमान "
LONG_HINDI = (HINDI_WORDS * 8).strip()
CARD = {
    "id": "s1.b2",
    "kind": "component",
    "version": 1,
    "reuse": None,
    "label": "kutch-ajrakh/chemistry/mordant-baths",
    "componentKind": "fact_table",
    "title": "Mordant baths and their temperatures",
    "craft": {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": "/crafts/Kutch-Ajrakh"},
    "href": "/crafts/Kutch-Ajrakh#mordant",
    "sources": [{"sourceId": "openalex:W1"}],
}


async def ignored(name: str, data: Any) -> None:
    return None


def test_the_long_translations_pass_the_limits_they_land_in() -> None:
    assert len(LONG_TAMIL) == 149 > HEADING_MAX_CHARS
    assert len(LONG_HINDI) == 231 > TITLE_COLUMN_CHARS


async def test_a_composed_heading_whose_translation_passes_the_heading_limit_keeps_its_english() -> None:
    (spec,) = section_specs(["CHEMISTRY"], "DETAILED", craft_name="Kutch Ajrakh")
    model = FakeModel([reply(**{f"heading:{spec.id}": LONG_TAMIL})])
    (headed,) = await headed_specs(
        {spec.id: HEADING},
        [(spec, SUPPORTS)],
        language="ta",
        translation=translation(model),
        claim=ExplainerStream(ignored, language="ta").claim_heading,
    )
    assert (headed.spec.title, headed.shown) == (HEADING, HEADING)
    SectionHeadingEvent.model_validate({"sectionId": spec.id, "title": headed.shown})
    assert len(model.calls) == 1


async def test_a_section_title_whose_translation_passes_the_heading_limit_keeps_its_english() -> None:
    first, second = section_specs(["CHEMISTRY", "HISTORY"], "DETAILED", craft_name="Kutch Ajrakh")
    model = FakeModel([reply(**{first.id: SHORT_TAMIL, second.id: LONG_TAMIL})])
    layout = AnswerLayout(specs=(first, second))
    titles = await layout.translated_titles(language="ta", translation=translation(model))
    assert titles == {first.id: SHORT_TAMIL}
    for spec in (first, second):
        shown = shown_title(spec, titles)
        SectionStartedEvent.model_validate(
            {
                "id": spec.id,
                "discipline": spec.discipline,
                **shown,
                "order": spec.order,
                "state": "RESEARCHING",
            }
        )
    assert shown_title(second, titles) == {"title": second.title}
    assert len(model.calls) == 1


async def test_a_component_title_whose_translation_passes_its_column_keeps_its_english() -> None:
    model = FakeModel([reply(**{"s1.b2.title": LONG_HINDI})])
    shown = await translated_block(CARD, language="hi", translation=translation(model), claim_texts={})
    assert shown == CARD
    assert BLOCK.validate_python(shown).id == "s1.b2"
    assert len(model.calls) == 1
