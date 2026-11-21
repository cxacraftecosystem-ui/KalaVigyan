import dataclasses
import hashlib
from pathlib import Path
from typing import Any

from app.research.why_here import WHY_HERE_KIND
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_parts import StoredSection
from app.services.monograph_generated_units import DraftUnit
from app.services.monograph_generated_why_here import (
    ground_hash,
    kept_refs,
    note_readings,
    why_here_label,
    with_why_here,
)

from ..geo.ground_fixtures import fixture_ground
from .generated_parts import BAGH, generated

RIVER = "The Baghini river runs past the printers' village."
RAIN = "Monsoon rain stops the printing for three months."
LABEL = "bagh-print/geography/why-here"
SLOT = f'<div class="kv-page kv-why-here" data-app=""><kv-slot component="{LABEL}"></kv-slot></div>'


def draft(unit_id: str, text: str, field: str = "GEOGRAPHY", tag: str = "p") -> DraftUnit:
    return DraftUnit(unit_id, "why", field, text, (BAGH,), tag)


def plain(nodes: list[Any]) -> str:
    return "".join(
        node if isinstance(node, str) else plain(node.get("c", [])) if isinstance(node, dict) else ""
        for node in nodes
    )


def stored_body(**content: Any) -> dict[str, Any]:
    return {"subjectSlug": "Bagh-Print", "specs": {}, "content": {"components": [], "layout": [], **content}}


def test_a_label_is_the_craft_slug_under_geography() -> None:
    assert why_here_label("Bagh-Print") == LABEL
    assert why_here_label("Kutch_Ajrakh--") == "kutchajrakh/geography/why-here"


def test_the_sentence_about_the_river_is_held_beside_its_reading_and_rain_stays_without_a_reading(
    tmp_path: Path,
) -> None:
    geography = StoredSection(
        "GEOGRAPHY", 1, ({"text": RIVER, "claimIds": [str(BAGH)]}, {"text": RAIN, "claimIds": [str(BAGH)]})
    )
    base = generated()
    parts = dataclasses.replace(
        base, sections=(*base.sections, geography), pictures=(), ground=fixture_ground()
    )
    built = assembled_document(parts, Drawings(root=tmp_path))
    assert built is not None
    why = [entry for entry in built.content.layout if entry.chapter == "why"]
    texts = {plain(unit.nodes): ref for ref, unit in built.content.units.items()}
    river, rain = texts[RIVER], texts[RAIN]
    assert [(e.kind, e.ref, e.within) for e in why if e.ref in (LABEL, river, rain)] == [
        ("unit", rain, None),
        ("component", LABEL, None),
        ("unit", river, LABEL),
    ]
    [entry] = [c for c in built.content.components if c.label == LABEL]
    assert (entry.kind, entry.chapter, entry.title) == (
        WHY_HERE_KIND,
        "why",
        "The ground under Ground fixture",
    )
    assert built.specs[LABEL]["notes"] == [{"reading": "river", "unit": river}]


def test_each_reading_holds_at_most_two_sentences_and_only_place_sentences_are_read() -> None:
    drafts = [
        draft("u1", "The river is near."),
        draft("u2", "A second river sentence."),
        draft("u3", "A third river sentence."),
        draft("u4", "A lake supplies the vats."),
        draft("u5", "A deposit of ore lies near.", field="CHEMISTRY"),
        draft("u6", "The hills rise to the east.", tag="h3"),
    ]
    notes = note_readings(drafts, fixture_ground())
    assert [(note.reading, note.unit) for note in notes] == [("river", "u1"), ("river", "u2"), ("lake", "u4")]


def test_a_heading_left_without_its_sentences_is_dropped() -> None:
    assert kept_refs(["h-geography", "u1", "h-climate", "u2", "u3"], {"u1"}) == ("h-climate", "u2", "u3")
    assert kept_refs(["h-geography", "u1", "u2", "h-climate", "u3"], {"u3"}) == ("h-geography", "u1", "u2")


def test_a_stored_document_gains_the_figure_after_the_last_entry_of_its_place_chapter() -> None:
    layout = [
        {"chapter": "why", "kind": "unit", "ref": "u1", "within": None},
        {"chapter": "why", "kind": "unit", "ref": "u2", "within": None},
        {"chapter": "sources", "kind": "unit", "ref": "u3", "within": None},
    ]
    placed = with_why_here(stored_body(layout=layout), fixture_ground())
    assert [entry["ref"] for entry in placed["content"]["layout"]] == ["u1", "u2", LABEL, "u3"]
    assert [component["kind"] for component in placed["content"]["components"]] == [WHY_HERE_KIND]
    assert placed["specs"][LABEL]["notes"] == []
    assert placed["specs"][LABEL]["ground"]["craft"]["slug"] == "Ground-Fixture"


def test_an_authored_shell_gains_the_slot_at_the_end_of_its_place_chapter() -> None:
    why = '<section class="kv-ch" id="why-kachchh" data-ch="4"><div>a</div></section>'
    after = '<section class="kv-ch" id="history" data-ch="5"><p>b</p></section>'
    placed = with_why_here({**stored_body(), "shell": why + after}, fixture_ground())
    assert placed["shell"] == why.replace("</div></section>", "</div>" + SLOT + "</section>") + after
    assert placed["content"]["layout"] == []
    assert LABEL in placed["specs"]


def test_a_document_without_a_place_chapter_or_a_ground_is_served_as_stored() -> None:
    body = stored_body(layout=[{"chapter": "made", "kind": "unit", "ref": "u1", "within": None}])
    assert with_why_here(body, fixture_ground()) is body
    assert with_why_here({**stored_body(), "shell": "<section>x</section>"}, fixture_ground())["specs"] == {}
    assert with_why_here(body, None) is body


def test_the_tag_of_a_stored_document_changes_with_its_ground() -> None:
    ground = fixture_ground()
    folded = f"{'a' * 64}:{ground.model_dump_json(by_alias=True)}"
    assert ground_hash("a" * 64, ground) == hashlib.sha256(folded.encode("utf-8")).hexdigest()
    assert ground_hash("a" * 64, None) == "a" * 64
