from dataclasses import replace

from app.models.enums import SOURCE_KINDS
from app.research.expert_panel import EXPERT_PANEL
from app.services.seat_search import seat_query

from ..experts.fixtures import QUESTION, build_ask

ENGLISH = "When did the Khatri printers bring Ajrakh to Kutch?"


def test_a_seat_search_is_filtered_by_the_seats_own_fields() -> None:
    chemist = seat_query(build_ask(("CHEMIST",), discipline="CHEMISTRY"), EXPERT_PANEL["CHEMIST"])
    assert chemist.fields == ("CHEMISTRY", "PROCESS", "MATERIALS", "HEALTH")
    historian = seat_query(build_ask(("HISTORIAN",)), EXPERT_PANEL["HISTORIAN"])
    assert historian.fields == ("HISTORY", "OVERVIEW")


def test_a_seat_search_asks_for_reranking() -> None:
    assert seat_query(build_ask(("CHEMIST",), discipline="CHEMISTRY"), EXPERT_PANEL["CHEMIST"]).rerank is True


def test_a_seat_searches_the_english_rendering_when_the_answer_has_one() -> None:
    ask = build_ask(("HISTORIAN",))
    rendered = replace(ask, request=ask.request.model_copy(update={"english_question": ENGLISH}))
    assert seat_query(rendered, EXPERT_PANEL["HISTORIAN"]).text.startswith(ENGLISH)
    assert seat_query(ask, EXPERT_PANEL["HISTORIAN"]).text.startswith(QUESTION)


READERS = {
    "BOOK_CHAPTER": (
        "CHEMIST PHYSICIST MATERIALS_SCIENTIST TECHNOLOGIST GEOLOGIST HYDROLOGIST SOIL_SCIENTIST CLIMATOLOGIST "
        "ECOLOGIST BOTANIST TOXICOLOGIST HISTORIAN ANTHROPOLOGIST ECONOMIST DESIGN_HISTORIAN CONSERVATOR"
    ),
    "OTHER": (
        "MATERIALS_SCIENTIST TECHNOLOGIST HYDROLOGIST ECOLOGIST HISTORIAN ANTHROPOLOGIST ECONOMIST "
        "DESIGN_HISTORIAN CONSERVATOR POLICY_EXPERT"
    ),
    "WEB_PAGE": (
        "CHEMIST PHYSICIST MATERIALS_SCIENTIST TECHNOLOGIST GEOLOGIST BOTANIST HISTORIAN ANTHROPOLOGIST "
        "ECONOMIST DESIGN_HISTORIAN CONSERVATOR POLICY_EXPERT ARTISAN"
    ),
    "GI_JOURNAL": "CHEMIST PHYSICIST MATERIALS_SCIENTIST TECHNOLOGIST HISTORIAN POLICY_EXPERT",
    "MEDIA": "HISTORIAN DESIGN_HISTORIAN",
}


def readers(kind: str) -> list[str]:
    return [seat for seat, brief in EXPERT_PANEL.items() if kind in brief.source_kinds]


def test_every_source_kind_is_read_by_the_seats_whose_work_it_serves() -> None:
    assert {kind for brief in EXPERT_PANEL.values() for kind in brief.source_kinds} == set(SOURCE_KINDS)
    for kind, seats in READERS.items():
        assert readers(kind) == seats.split(), kind


def test_a_seat_keeps_its_earlier_kinds_first_so_its_reading_order_holds() -> None:
    assert EXPERT_PANEL["CHEMIST"].source_kinds[:4] == ("PAPER", "BOOK", "COMPOUND_RECORD", "ENCYCLOPEDIA")
    assert EXPERT_PANEL["HISTORIAN"].source_kinds[:4] == ("BOOK", "PAPER", "GI_JOURNAL", "ENCYCLOPEDIA")
    assert EXPERT_PANEL["ARTISAN"].source_kinds == ("FIELD_TESTIMONY", "WEB_PAGE")
