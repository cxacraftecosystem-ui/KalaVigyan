import uuid

from app.research.explainer import explainer_blocks
from app.research.understanding import Understanding
from app.services.follow_ups import FollowUp, answer_layout

from .versions import base_version, first_explainer


def understanding(*disciplines: str) -> Understanding:
    explainer = first_explainer()
    return Understanding(
        craft=explainer.understood.crafts[0],
        candidates=[],
        disciplines=list(disciplines),
        seats=[],
        depth="EXPERT",
        language="en",
        basis="MODEL",
    )


def test_a_follow_up_deepens_sections_it_has_and_adds_the_rest_after_them() -> None:
    layout = answer_layout(
        understanding("PROCESS"), FollowUp(base=base_version(), facets=("HISTORY", "GEOGRAPHY"))
    )
    assert [(s.id, s.discipline, s.title, s.order) for s in layout.specs] == [
        ("s2", "GEOGRAPHY", "Why the water matters", 2),
        ("s4", "HISTORY", "Where Kutch Ajrakh comes from", 4),
    ]
    assert layout.titles == {"s2": "Why the water matters"}
    assert [spec.id for spec in layout.reusable] == ["s4"]
    assert [spec.id for spec in layout.untitled] == ["s4"]
    water = layout.deepening["s2"]
    assert (water.first_block, water.kinds, water.number(1)) == (2, frozenset({"prose"}), 2)


def test_a_follow_up_without_facets_deepens_what_its_question_asks() -> None:
    layout = answer_layout(understanding("PROCESS"), FollowUp(base=base_version()))
    assert [spec.id for spec in layout.specs] == ["s1"]
    process = layout.deepening["s1"]
    assert process.first_block == 3
    assert process.shows("process_ladder") and not process.adds_pictures
    cited = {uuid.UUID(c.claim_id) for b in explainer_blocks(first_explainer()) for c in b.citations()}
    assert process.claims == cited


def test_a_new_answer_lays_out_the_sections_its_question_asks() -> None:
    layout = answer_layout(understanding("CHEMISTRY", "HISTORY"), None)
    assert [(s.id, s.discipline, s.order) for s in layout.specs] == [
        ("s1", "CHEMISTRY", 1),
        ("s2", "HISTORY", 2),
    ]
    assert (layout.titles, layout.deepening, layout.follow_up) == ({}, {}, None)
    assert layout.keeps_pieces_of(layout.specs[0])
    assert (tuple(layout.shown_sections), layout.shown_kinds) == ((), frozenset())


def test_a_follow_up_names_every_section_and_kind_its_explainer_already_shows() -> None:
    layout = answer_layout(understanding("PROCESS"), FollowUp(base=base_version(), facets=("HISTORY",)))
    assert [section.id for section in layout.shown_sections] == ["s1", "s2", "s3"]
    assert layout.shown_kinds == frozenset({"process_ladder", "images", "prose"})
