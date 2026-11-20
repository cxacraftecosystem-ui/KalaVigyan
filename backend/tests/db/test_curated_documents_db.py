import itertools
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.research.component_specs import checked_spec
from app.research.component_specs_blocks import ANSWER_BLOCK_KIND, AnswerBlockSpec
from app.research.monograph_document import MonographDocument
from app.research.monograph_page import TextUnit
from app.services import knowledge_view
from app.services.craft_page_snapshots import OPEN, built_page
from app.services.curation_import import import_curation
from app.services.monograph_generated import generated_document

pytestmark = pytest.mark.db

CRAFTS = ("Bastar-Dhokra", "Kutch-Bandhani", "Bagru-Hand-Block-Print")
PICTURE_KIND = "picture_plate"
DIFFER_HEADING = "Where the sources differ"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def citations(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "sourceId" in node and "claimId" in node else []
        return own + [found for value in node.values() for found in citations(value)]
    if isinstance(node, list):
        return [found for value in node for found in citations(value)]
    return []


def blocks(document: MonographDocument) -> list[AnswerBlockSpec]:
    return [
        AnswerBlockSpec.model_validate(document.specs[component.label])
        for component in document.content.components
        if component.kind == ANSWER_BLOCK_KIND
    ]


def document_claims(document: MonographDocument) -> set[uuid.UUID]:
    shown = {uuid.UUID(claim) for unit in document.content.units.values() for claim in unit.claim_ids}
    for spec in blocks(document):
        shown |= {uuid.UUID(cite["claimId"]) for cite in citations(spec.block.model_dump(mode="json"))}
    return shown


def plate_pictures(document: MonographDocument) -> list[str]:
    return [
        document.specs[component.label]["picture"]["src"]
        for component in document.content.components
        if component.kind == PICTURE_KIND
    ]


def block_pictures(document: MonographDocument) -> set[str]:
    found: set[str] = set()
    for spec in blocks(document):
        for stage in getattr(spec.block, "stages", None) or []:
            found |= {str(picture.media.image_url) for picture in getattr(stage, "pictures", None) or []}
    return found


@pytest.mark.parametrize("slug", CRAFTS)
async def test_a_curated_craft_s_document_shows_every_cited_claim_and_figure_its_tabbed_page_showed(
    session: AsyncSession, slug: str
) -> None:
    report = await import_curation(session)
    assert report.refused == []
    craft = await knowledge_view.resolve_craft(session, slug)
    assert craft is not None
    page = await built_page(session, craft, OPEN)
    document = await generated_document(session, "craft", craft.slug)
    assert document is not None and page.curated
    missing = {claim.id for claim in page.claims} - document_claims(document)
    assert missing == set(), [claim.text for claim in page.claims if claim.id in missing]
    for component in document.content.components:
        if component.kind == ANSWER_BLOCK_KIND:
            checked_spec(ANSWER_BLOCK_KIND, document.specs[component.label])
    pictures = plate_pictures(document)
    assert len(pictures) == len(set(pictures))
    assert set(pictures).isdisjoint(block_pictures(document))
    drawn = {
        item.block.kind
        for chapter in page.chapters
        for item in chapter.items
        if item.block is not None and item.origin is None
    }
    kinds = {spec.block.kind for spec in blocks(document)}
    for kind in ("process_ladder", "reaction_player", "market_gi", "region_story"):
        assert (kind in kinds) == (kind in drawn), kind
    assert document.version >= 3


def top_units(document: MonographDocument, chapter: str) -> list[TextUnit]:
    units = document.content.units
    return [
        units[entry.ref]
        for entry in document.content.layout
        if entry.kind == "unit" and entry.within is None and entry.chapter == chapter
    ]


def unit_text(unit: TextUnit) -> str:
    return "".join(node if isinstance(node, str) else "" for node in unit.nodes).strip()


def differ_topics(document: MonographDocument) -> list[str]:
    topics: list[str] = []
    for chapter in dict.fromkeys(entry.chapter for entry in document.content.layout):
        under = False
        for unit in top_units(document, chapter):
            if unit.tag in ("h2", "h3"):
                under = unit.tag == "h3" and unit_text(unit) == DIFFER_HEADING
            elif under and unit.tag == "dt":
                topics.append(unit_text(unit))
    return topics


@pytest.mark.parametrize("slug", CRAFTS)
async def test_a_curated_craft_s_glance_leads_with_cited_facts_and_each_disagreement_reads_in_sentence_case(
    session: AsyncSession, slug: str
) -> None:
    report = await import_curation(session)
    assert report.refused == []
    craft = await knowledge_view.resolve_craft(session, slug)
    assert craft is not None
    document = await generated_document(session, "craft", craft.slug)
    assert document is not None
    kicker = document.content.units["masthead-kicker"].nodes
    assert [node["m"] for node in kicker] == ["span", "span"] and kicker[0]["c"] == ["Monograph"]
    glance = top_units(document, "glance")
    assert glance[0].tag == "h2"
    facts = list(itertools.takewhile(lambda unit: unit.tag in ("dt", "dd"), glance[1:]))
    assert len(facts) >= 4 and [unit.tag for unit in facts] == ["dt", "dd"] * (len(facts) // 2)
    assert all(unit.claim_ids for unit in facts if unit.tag == "dd")
    topics = differ_topics(document)
    assert topics and all(topic[:1].isupper() for topic in topics), topics
