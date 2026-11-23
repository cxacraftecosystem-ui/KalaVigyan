import uuid
from collections import Counter
from typing import Any

import pytest

from app.research.craft_origins import ItemOrigin
from app.research.craft_page import CraftPage
from app.research.craft_parts import SourcesDifferPart
from app.services.document_components import StructureBlock, document_structure
from app.services.document_components_parts import StructureText, sentence_case

from ..contracts.golden import golden_json

GOLDEN = "craft.page.golden.json"
AJRAKH_BLOCKS = {
    "made": ["process_ladder"],
    "chem": ["mordant_bath", "reaction_player", *["molecule_3d"] * 7, *["material_card"] * 4],
    "why": ["region_story", "climate_risk", "seasons"],
    "history": ["timeline_map"],
    "market": ["market_gi"],
}
KEY_FACTS = [
    "GI status",
    "Centres",
    "Makers and wearers",
    "Colours",
    "Dyes and mordants",
    "Stages",
    "Time per piece",
    "Resists",
]
PLACES = ["Ajrakhpur", "Dhamadka", "Khavda", "Barmer", "Sindh"]
HYPOTHESES = 5


@pytest.fixture(scope="module")
def raw() -> dict[str, Any]:
    return golden_json(GOLDEN)


@pytest.fixture(scope="module")
def page(raw: dict[str, Any]) -> CraftPage:
    return CraftPage.model_validate(raw)


def citations(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "sourceId" in node and "claimId" in node else []
        return own + [found for value in node.values() for found in citations(value)]
    if isinstance(node, list):
        return [found for value in node for found in citations(value)]
    return []


def blocks(found: dict[str, tuple[Any, ...]]) -> dict[str, list[str]]:
    shown = {
        chapter: [item.block.kind for item in items if isinstance(item, StructureBlock)]
        for chapter, items in found.items()
    }
    return {chapter: kinds for chapter, kinds in shown.items() if kinds}


def texts(items: tuple[Any, ...], tag: str) -> list[str]:
    return [item.text for item in items if isinstance(item, StructureText) and item.tag == tag]


def test_the_figures_the_page_draws_from_its_records_become_answer_blocks_in_their_chapters(
    page: CraftPage,
) -> None:
    structure = document_structure(page)
    assert blocks(dict(structure.trailing)) == AJRAKH_BLOCKS
    labels = [item.label for item in structure.items() if isinstance(item, StructureBlock)]
    assert len(labels) == len(set(labels)) == sum(len(kinds) for kinds in AJRAKH_BLOCKS.values())
    assert "kutch-ajrakh/blocks/made-ladder" in labels
    ladder = next(
        item
        for item in structure.items()
        if isinstance(item, StructureBlock) and item.label.endswith("ladder")
    )
    assert ladder.figure is not None and ladder.figure.title == "How Kutch Ajrakh is made, in 14 stages"


def test_a_block_carries_every_source_and_claim_its_citations_name(
    raw: dict[str, Any], page: CraftPage
) -> None:
    structure = document_structure(page)
    drawn = {
        item["block"]["id"]: item["block"]
        for chapter in raw["chapters"]
        for item in chapter["items"]
        if item["block"] is not None
    }
    for item in structure.items():
        if not isinstance(item, StructureBlock):
            continue
        cited = citations(drawn[item.block.id])
        assert set(item.source_ids) == {cite["sourceId"] for cite in cited} | set(
            item.block.cited_source_ids()
        )
        assert item.claims == {uuid.UUID(cite["claimId"]) for cite in cited}
        assert set(item.source_ids) <= set(structure.sources)


def test_key_facts_lead_the_glance_chapter_as_terms_with_their_cited_values(page: CraftPage) -> None:
    structure = document_structure(page)
    leading = structure.leading["glance"]
    assert texts(leading, "dt") == KEY_FACTS
    values = [item for item in leading if isinstance(item, StructureText) and item.tag == "dd"]
    assert len(values) == len(KEY_FACTS) and all(item.claim_ids for item in values)


def test_places_communities_differences_and_questions_follow_their_chapters_under_one_heading_each(
    page: CraftPage,
) -> None:
    structure = document_structure(page)
    why = structure.trailing["why"]
    assert texts(why, "h3") == ["The place and its resources", "Places", "Where the sources differ"]
    assert [text for text in texts(why, "dt") if text in PLACES] == PLACES
    assert texts(why, "dt")[:2] == ["Water", "Vegetation"]
    assert texts(structure.trailing["market"], "dt") == ["Workforce"]
    glance = structure.trailing["glance"]
    assert texts(glance, "h3") == ["Where the sources differ"]
    assert "Communities" in texts(structure.trailing["people"], "h3")
    sources = structure.trailing["sources"]
    assert texts(sources, "h3")[0] == "Open questions"


def held(structure: Any) -> list[StructureText]:
    found = structure.trailing.get("sources", ())
    return [item for item in found if isinstance(item, StructureText) and item.tag == "li"]


def test_every_hypothesis_is_shown_by_a_figure_or_record_or_listed_once_as_a_hypothesis(
    raw: dict[str, Any], page: CraftPage
) -> None:
    hypotheses = {claim["id"] for claim in raw["claims"] if claim["level"] == "HYPOTHESIS"}
    assert len(hypotheses) == HYPOTHESES
    structure = document_structure(page)
    assert hypotheses <= {str(claim) for claim in structure.claim_ids()}
    assert {str(claim) for item in held(structure) for claim in item.claim_ids} <= hypotheses
    bare = document_structure(page.model_copy(update={"chapters": []}))
    listed = held(bare)
    assert texts(bare.trailing["sources"], "h3") == ["Hypotheses"]
    assert {str(claim) for item in listed for claim in item.claim_ids} == hypotheses
    assert Counter(item.text for item in listed) == Counter(
        claim["text"] for claim in raw["claims"] if claim["id"] in hypotheses
    )


def test_every_unit_has_its_own_id_and_the_ladder_s_pictures_are_the_pictures_it_shows(
    raw: dict[str, Any], page: CraftPage
) -> None:
    structure = document_structure(page)
    ids = [item.unit_id for item in structure.items() if isinstance(item, StructureText)]
    assert len(ids) == len(set(ids))
    ladder = next(
        item["block"]
        for chapter in raw["chapters"]
        for item in chapter["items"]
        if item["block"] is not None and item["block"]["kind"] == "process_ladder"
    )
    pictures = {
        picture["media"]["imageUrl"] for stage in ladder["stages"] for picture in stage.get("pictures") or []
    }
    assert pictures and pictures <= structure.media_urls()


def test_an_item_a_reader_s_answer_brought_is_left_to_the_answer_it_came_from(page: CraftPage) -> None:
    origin = ItemOrigin(
        basis="READERS",
        generated=None,
        model=None,
        generated_on=None,
    )
    chapters = [
        chapter.model_copy(
            update={
                "items": [
                    item.model_copy(update={"origin": origin}) if item.kind == "market_gi" else item
                    for item in chapter.items
                ]
            }
        )
        for chapter in page.chapters
    ]
    assert "market" in blocks(dict(document_structure(page).trailing))
    assert "market" not in blocks(
        dict(document_structure(page.model_copy(update={"chapters": chapters})).trailing)
    )


def lowered_topic(item: Any) -> Any:
    part = item.part
    if not isinstance(part, SourcesDifferPart) or item.origin is not None:
        return item
    about = part.reading.about[:1].lower() + part.reading.about[1:]
    reading = part.reading.model_copy(update={"about": about})
    return item.model_copy(update={"part": part.model_copy(update={"reading": reading})})


def test_a_disagreement_s_topic_heads_its_readings_in_sentence_case(page: CraftPage) -> None:
    topics = [
        item.part.reading.about
        for chapter in page.chapters
        for item in chapter.items
        if isinstance(item.part, SourcesDifferPart) and item.origin is None
    ]
    chapters = [
        chapter.model_copy(update={"items": [lowered_topic(item) for item in chapter.items]})
        for chapter in page.chapters
    ]
    structure = document_structure(page.model_copy(update={"chapters": chapters}))
    terms = [text for items in structure.trailing.values() for text in texts(items, "dt")]
    assert topics and all(topic[:1].isupper() for topic in topics)
    assert [term for term in terms if term in topics] == topics
    assert sentence_case("  whether the vat is reduced ") == "Whether the vat is reduced"
    assert sentence_case("") == ""
