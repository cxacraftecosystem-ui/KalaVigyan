import dataclasses
from pathlib import Path

import pytest

from app.services.monograph_generated import CRAFT_SECTIONS_MIN, enough_sections
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_parts import StoredSection
from app.services.monograph_generated_pictures import curated_plate
from app.services.monograph_generated_units import SubjectRecord, chapter_heading

from .generated_parts import ALUM, BAGH, RECORD, generated, media
from .pictures import picture


def title(chapter: str, record: SubjectRecord) -> str | None:
    heading = chapter_heading(chapter, record)
    return None if heading is None else str(heading[1].nodes[0])


def test_the_place_chapter_names_the_first_state_and_the_market_names_gi_only_when_registered() -> None:
    two_states = SubjectRecord(name="Bagh Print", place="Madhya Pradesh, Gujarat", gi=False)
    assert title("why", two_states) == "Why Madhya Pradesh"
    assert title("why", SubjectRecord(name="Bagh Print")) == "Where it is made"
    assert title("market", two_states) == "Market"
    assert title("market", RECORD) == "Market and GI"
    assert title("made", RECORD) == "How it is made"
    assert chapter_heading("cloth", RECORD) is None
    ref, unit = chapter_heading("sources", RECORD) or ("", None)
    assert (ref, unit.tag if unit else None) == ("chapter-sources", "h2")


@pytest.mark.parametrize(
    ("kind", "published", "enough"),
    [("craft", 2, False), ("craft", 3, True), ("family", 1, True), ("category", 1, True)],
)
def test_a_craft_needs_three_published_sections_for_a_generated_monograph(
    kind: str, published: int, enough: bool
) -> None:
    assert CRAFT_SECTIONS_MIN == 3
    assert enough_sections(kind, published) is enough


def test_the_lede_takes_at_most_three_overview_sentences_and_the_rest_stay_in_their_chapter(
    tmp_path: Path,
) -> None:
    sentences = tuple({"text": f"Bagh fact number {n} holds.", "claimIds": [str(BAGH)]} for n in range(1, 5))
    overview = StoredSection("OVERVIEW", 1, sentences)
    chemistry = StoredSection(
        "CHEMISTRY", 1, ({"text": "Alum fixes the madder red.", "claimIds": [str(ALUM)]},)
    )
    parts = dataclasses.replace(generated(), sections=(overview, chemistry), pictures=())
    built = assembled_document(parts, Drawings(root=tmp_path))
    assert built is not None
    units = built.content.units
    opening = [e.ref for e in built.content.layout if e.chapter == "opening"]
    lede = [ref for ref in opening if units[ref].tag == "p" and ref.startswith("overview-")]
    glance = [e.ref for e in built.content.layout if e.chapter == "glance"]
    assert len(lede) == 3
    assert [units[ref].tag for ref in glance] == ["h2", "h3", "p"]
    assert units[glance[1]].nodes == ["What it is"]


def test_a_picture_plate_carries_every_field_of_its_spec_and_one_off_the_picture_contract_is_left_out(
    tmp_path: Path,
) -> None:
    built = assembled_document(generated(), Drawings(root=tmp_path))
    assert built is not None
    hero = built.specs["bagh-print/pictures/i02"]
    assert (hero["row"], hero["pull"], hero["opener"], hero["masthead"]) == (None, None, None, None)
    assert hero["figure"]["captions"][0]["look"] is False and hero["figure"]["crop"] is None
    assert (hero["picture"]["loading"], hero["picture"]["fetchPriority"]) == (None, None)
    elsewhere = media("I05").model_copy(update={"image_url": "https://example.org/a.jpg"})
    shown = curated_plate(picture("I05", role="PLATE", chapter="made"), elsewhere)
    with_elsewhere = dataclasses.replace(generated(), pictures=(*generated().pictures, shown))
    rebuilt = assembled_document(with_elsewhere, Drawings(root=tmp_path))
    assert rebuilt is not None
    assert "bagh-print/pictures/i05" not in {component.label for component in rebuilt.content.components}
