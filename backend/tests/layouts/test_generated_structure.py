import uuid
from collections import defaultdict
from typing import Any

import pytest

from app.research.component_specs import checked_spec
from app.research.component_specs_blocks import ANSWER_BLOCK_KIND, AnswerBlockSpec
from app.research.craft_page import CraftPage
from app.research.monograph_document import MonographDocument
from app.services.document_components import document_structure
from app.services.knowledge_view import ClaimView
from app.services.monograph_generated_assembly import GeneratedParts, assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_parts import StoredSection
from app.services.monograph_generated_structure import with_page_claims
from app.services.monograph_generated_units import SubjectRecord, stored_source

from ..contracts.golden import golden_json

GOLDEN = "craft.page.golden.json"
SLUG = "Kutch-Ajrakh"
HYPOTHESIS = "HYPOTHESIS"


@pytest.fixture(scope="module")
def page() -> CraftPage:
    return CraftPage.model_validate(golden_json(GOLDEN))


def curated_sections(page: CraftPage) -> list[StoredSection]:
    by_field: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for claim in page.claims:
        if claim.level != HYPOTHESIS and claim.provenance == "CURATED":
            by_field[claim.discipline].append({"text": claim.text, "claimIds": [str(claim.id)]})
    return [StoredSection(field, 1, tuple(sentences)) for field, sentences in by_field.items()]


def parts(page: CraftPage, sections: list[StoredSection]) -> GeneratedParts:
    structure = document_structure(page)
    visible = {
        claim.id: ClaimView(
            claim.id,
            claim.text,
            claim.level,
            "MATERIAL",
            None,
            citations=[
                {"sourceId": cite.source_id, "quote": cite.quote, "locator": cite.locator}
                for cite in claim.citations
            ],
        )
        for claim in page.claims
    }
    sources = {source.id: stored_source(source.model_dump(mode="json")) for source in page.sources}
    return GeneratedParts(
        subject_kind="craft",
        subject_slug=SLUG,
        page_url=f"https://kalavigyan.example/crafts/{SLUG}",
        record=SubjectRecord(name=page.craft.name, kicker="Textiles", place="Kachchh, Gujarat", gi=True),
        sections=tuple(with_page_claims(sections, structure)),
        visible=visible,
        sources=sources,
        structure=structure,
    )


@pytest.fixture(scope="module")
def document(page: CraftPage) -> MonographDocument:
    built = assembled_document(parts(page, curated_sections(page)), Drawings())
    assert built is not None
    return built


def blocks(document: MonographDocument) -> list[tuple[str, AnswerBlockSpec]]:
    return [
        (component.label, AnswerBlockSpec.model_validate(document.specs[component.label]))
        for component in document.content.components
        if component.kind == ANSWER_BLOCK_KIND
    ]


def shown_claims(document: MonographDocument) -> set[uuid.UUID]:
    shown = {uuid.UUID(claim) for unit in document.content.units.values() for claim in unit.claim_ids}
    for _, spec in blocks(document):
        shown |= {uuid.UUID(claim) for claim in spec.block.cited_claim_ids()}
        shown |= {uuid.UUID(cite["claimId"]) for cite in _citations(spec.block.model_dump(mode="json"))}
    return shown


def _citations(node: Any) -> list[dict[str, Any]]:
    if isinstance(node, dict):
        own = [node] if "sourceId" in node and "claimId" in node else []
        return own + [found for value in node.values() for found in _citations(value)]
    if isinstance(node, list):
        return [found for value in node for found in _citations(value)]
    return []


def test_every_claim_the_tabbed_page_shows_is_in_the_document(
    page: CraftPage, document: MonographDocument
) -> None:
    assert {claim.id for claim in page.claims} <= shown_claims(document)


def test_every_figure_is_an_answer_block_whose_spec_its_kind_validates(document: MonographDocument) -> None:
    drawn = blocks(document)
    assert len(drawn) == 19
    for label, _ in drawn:
        checked_spec(ANSWER_BLOCK_KIND, document.specs[label])
    figures = [
        spec.figure.number for _, spec in drawn if spec.figure is not None and spec.figure.kind == "FIGURE"
    ]
    tables = [
        spec.figure.number for _, spec in drawn if spec.figure is not None and spec.figure.kind == "TABLE"
    ]
    assert figures == list(range(1, len(figures) + 1))
    assert tables == list(range(1, len(tables) + 1))


def test_a_block_s_sources_are_the_document_s_numbered_sources(document: MonographDocument) -> None:
    sources = document.content.sources
    for _, spec in blocks(document):
        for listed in spec.sources:
            assert listed.key in sources
            assert sources[listed.key].title == listed.ref.title


def test_a_sentence_a_figure_or_record_already_shows_is_not_retold_in_its_field_s_prose(
    page: CraftPage, document: MonographDocument
) -> None:
    structure = document_structure(page)
    structured = structure.claim_ids()
    prose = [
        unit
        for ref, unit in document.content.units.items()
        if unit.tag == "p" and unit.claim_ids and not ref.startswith("s-") and unit.chapter != "opening"
    ]
    assert prose
    assert all(not {uuid.UUID(claim) for claim in unit.claim_ids} <= structured for unit in prose)


def test_the_document_numbers_its_chapters_from_the_page_and_lists_its_sources(
    document: MonographDocument,
) -> None:
    chapters = list(dict.fromkeys(entry.chapter for entry in document.content.layout))
    assert chapters[0] == "opening" and chapters[-1] == "sources"
    assert {"glance", "made", "chem", "why", "history", "market", "people"} <= set(chapters)
    assert sorted(source.number for source in document.content.sources.values()) == list(
        range(1, len(document.content.sources) + 1)
    )
