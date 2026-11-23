import dataclasses
import uuid
from pathlib import Path

from app.research.component_specs import checked_spec
from app.research.craft_page_context import PageRelative
from app.research.crafts import CraftRef
from app.research.kin_crafts import KinCraftsSpec
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_kin import KinRead, KinShown, kin_label, kin_placed

from .generated_parts import RECORD, generated, source, view

KIN_CLAIM = uuid.UUID("9a1e0000-0000-4000-8000-0000000000e1")
KIN_PAPER = uuid.UUID("9a1e0000-0000-4000-8000-000000000503")
TEXT_KIN = "Bagru printers resist the cloth with dabu, a paste of black clay."
LABEL = "bagh-print/kin/related-crafts"


def bagru() -> PageRelative:
    return PageRelative(
        craft=CraftRef(
            slug="Bagru-Hand-Block-Print",
            name="Bagru Hand Block Print",
            path="/crafts/Bagru-Hand-Block-Print",
        ),
        display_name="Bagru Hand Block Print",
        gi_status="GI",
        state_of_practice=["Rajasthan"],
        basis="CURATED",
        coverage="FULL",
        claims=40,
        hero=None,
        lede=None,
    )


def kin_read() -> KinRead:
    shown = KinShown(relative=bagru(), shares=("Alum", "Harda"), text=TEXT_KIN, claim_ids=(KIN_CLAIM,))
    return KinRead(
        crafts=(shown,),
        family=RECORD.kicker,
        visible={KIN_CLAIM: view(KIN_CLAIM, TEXT_KIN, KIN_PAPER)},
        sources={str(KIN_PAPER): source("Bagru survey", "https://example.org/bagru")},
    )


def test_each_kin_craft_carries_its_family_its_shared_materials_and_one_held_cited_sentence() -> None:
    placed = kin_placed(kin_read(), "Bagh-Print")
    assert placed is not None
    assert placed.label == kin_label("Bagh-Print") == LABEL
    spec = checked_spec("related_crafts", placed.spec)
    assert isinstance(spec, KinCraftsSpec)
    assert placed.spec["head"] == {
        "title": "Crafts of the same family",
        "family": "Textiles · Hand block printing",
    }
    assert placed.spec["crafts"] == [
        {
            "name": "Bagru Hand Block Print",
            "path": "/crafts/Bagru-Hand-Block-Print",
            "place": "Rajasthan",
            "gi": True,
            "monograph": True,
            "shares": ["Alum", "Harda"],
            "sentence": "kin-1",
        }
    ]
    assert [(draft.unit_id, draft.chapter, draft.text, draft.claim_ids) for draft in placed.drafts] == [
        ("kin-1", "kin", TEXT_KIN, (KIN_CLAIM,))
    ]
    assert (placed.entry.kind, placed.entry.chapter) == ("related_crafts", "kin")


def test_the_generated_document_draws_the_kin_crafts_in_the_kin_chapter_with_the_sentence_cited(
    tmp_path: Path,
) -> None:
    base = generated()
    read = kin_read()
    parts = dataclasses.replace(
        base,
        pictures=(),
        kin=read,
        visible={**read.visible, **base.visible},
        sources={**read.sources, **base.sources},
    )
    built = assembled_document(parts, Drawings(root=tmp_path))
    assert built is not None
    kin = [(entry.kind, entry.ref, entry.within) for entry in built.content.layout if entry.chapter == "kin"]
    assert kin == [("unit", "chapter-kin", None), ("component", LABEL, None), ("unit", "kin-1", LABEL)]
    assert built.specs[LABEL]["crafts"][0]["sentence"] == "kin-1"
    assert "Bagru survey" in [cited.title for cited in built.content.sources.values()]
    assert built.content.citation_claims["kin-1"] == [str(KIN_CLAIM)]


def test_a_page_with_no_kin_sentence_draws_no_kin_crafts(tmp_path: Path) -> None:
    assert kin_placed(KinRead(), "Bagh-Print") is None
    built = assembled_document(dataclasses.replace(generated(), pictures=()), Drawings(root=tmp_path))
    assert built is not None
    assert LABEL not in built.specs
    assert not any(entry.chapter == "kin" for entry in built.content.layout)
