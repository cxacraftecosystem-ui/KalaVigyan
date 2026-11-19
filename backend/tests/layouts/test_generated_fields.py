import uuid
from decimal import Decimal
from pathlib import Path

from app.research.coverage import CoverageSubject, Holdings, field_coverage
from app.research.monograph_document import MonographDocument
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_grids import StatedValue, fact_grid
from app.services.monograph_generated_parts import StoredSection
from app.services.monograph_generated_units import DraftUnit

from .generated_parts import ALUM_PAPER, generated, view

PLACED = {
    "PROCESS": "made",
    "CHEMISTRY": "chem",
    "PHYSICS": "chem",
    "MATERIALS": "made",
    "GEOGRAPHY": "why",
    "GEOLOGY": "why",
    "CLIMATE": "why",
    "ECOLOGY": "why",
    "BOTANY": "chem",
    "HISTORY": "history",
    "ECONOMICS": "market",
    "DESIGN": "people",
    "HEALTH": "made",
    "SOCIETY": "people",
    "POLICY": "market",
}
WRITTEN = ("MATERIALS", "DESIGN", "HEALTH", "BOTANY", "POLICY", "SOCIETY", "GEOLOGY", "PHYSICS")
OPENING = "opening"


def claim(field: str, n: int = 1) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"https://example.org/claims/{field}/{n}")


def sentence(field: str, n: int = 1) -> dict[str, object]:
    return {"text": f"A cited sentence number {n} about {field.lower()}.", "claimIds": [str(claim(field, n))]}


def built(tmp_path: Path, fields: tuple[str, ...], **changes: object) -> MonographDocument:
    sections = tuple(StoredSection(field, 1, (sentence(field),)) for field in fields)
    visible = {claim(field): view(claim(field), str(sentence(field)["text"]), ALUM_PAPER) for field in fields}
    parts = generated(sections=sections, visible=visible, pictures=(), components=(), **changes)
    document = assembled_document(parts, Drawings(root=tmp_path))
    assert document is not None
    return document


def test_each_written_field_sits_in_the_chapter_rule_23_names(tmp_path: Path) -> None:
    document = built(tmp_path, WRITTEN)
    units = document.content.units
    placed = {
        unit.field: entry.chapter
        for entry in document.content.layout
        if entry.kind == "unit"
        and entry.chapter != OPENING
        and (unit := units[entry.ref]).tag == "p"
        and unit.field
    }
    assert placed == {field: PLACED[field] for field in WRITTEN}


def test_a_field_without_a_section_never_appears_even_as_a_heading(tmp_path: Path) -> None:
    document = built(tmp_path, ("MATERIALS", "DESIGN"))
    shown = {unit.field for unit in document.content.units.values() if unit.field and unit.chapter != OPENING}
    assert shown == {"MATERIALS", "DESIGN"}
    assert "h-climate" not in document.content.units
    chapters = [entry.chapter for entry in document.content.layout]
    assert "why" not in chapters and "chem" not in chapters
    assert chapters.index("made") < chapters.index("people") < chapters.index("sources")


def test_the_generated_document_carries_its_coverage_and_omits_it_when_unknown(tmp_path: Path) -> None:
    coverage = field_coverage(
        CoverageSubject("craft", "Bagh-Print", "Bagh Print"),
        Holdings(filed={"c1": frozenset({"MATERIALS"})}, sources={"c1": frozenset({"s1"})}),
        claims_min=3,
    )
    covered = built(tmp_path, ("MATERIALS",), coverage=coverage)
    assert covered.coverage == coverage
    assert covered.model_dump(mode="json", by_alias=True)["coverage"]["thin"] == ["MATERIALS"]
    assert "coverage" not in built(tmp_path, ("MATERIALS",)).model_dump(mode="json", by_alias=True)


def test_two_stored_quantities_in_a_field_become_a_cited_fact_grid_beside_its_sentences(
    tmp_path: Path,
) -> None:
    sentences = (sentence("MATERIALS", 1), sentence("MATERIALS", 2))
    visible = {
        claim("MATERIALS", n): view(claim("MATERIALS", n), str(sentences[n - 1]["text"]), ALUM_PAPER)
        for n in (1, 2)
    }
    values = {
        claim("MATERIALS", 1): StatedValue("Alum bath", Decimal("8.000000"), "g/L"),
        claim("MATERIALS", 2): StatedValue("Dye bath", Decimal("60.5"), "°C"),
    }
    parts = generated(
        sections=(StoredSection("MATERIALS", 1, sentences),),
        visible=visible,
        pictures=(),
        components=(),
        values=values,
    )
    document = assembled_document(parts, Drawings(root=tmp_path))
    assert document is not None
    units = document.content.units
    made = [units[entry.ref] for entry in document.content.layout if entry.chapter == "made"]
    assert [unit.tag for unit in made] == ["h2", "h3", "p", "p", "dt", "dd", "dt", "dd"]
    assert [unit.nodes for unit in made if unit.tag == "dt"] == [["Alum bath"], ["Dye bath"]]
    first = made[5]
    assert (first.field, first.claim_ids) == ("MATERIALS", [str(claim("MATERIALS", 1))])
    assert first.nodes[0]["c"][0] == "8 "
    assert first.nodes[0]["c"][1]["c"] == ["g/L"]


def test_one_stored_quantity_is_not_a_grid() -> None:
    draft = DraftUnit("materials-1", "made", "MATERIALS", "Alum binds.", (claim("MATERIALS"),))
    alone = fact_grid([draft], {claim("MATERIALS"): StatedValue("Alum bath", Decimal("8"), "g/L")})
    assert (alone.terms, alone.values, alone.refs) == ({}, (), ())
    assert StatedValue("Dye bath", Decimal("60.500"), "°C").text() == "60.5 °C"
