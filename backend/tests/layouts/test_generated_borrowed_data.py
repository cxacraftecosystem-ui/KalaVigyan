import dataclasses
import json
from pathlib import Path

from app.services.document_components_data import borrowed_data, merged_data
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings

from .generated_parts import component, fragment_monograph, generated

MOLECULES = "shared/chemistry/alizarin-purpurin-3d"
MAP = "shared/climate/kachchh-district-climate-map"
ALIZARIN = {"atoms": [["O", 0.1, 0.2, 0.3]]}
PURPURIN = {"atoms": [["O", 0.4, 0.5, 0.6]]}
INDICAN = {"atoms": [["N", 0.7, 0.8, 0.9]]}
REGION = {"views": {"india": [1, 2, 3, 4]}, "layers": {"rain": {"unit": "mm a year"}}}
DATA = {
    "mol-data": {"6293": ALIZARIN, "6683": PURPURIN, "441564": INDICAN},
    "rs-data": REGION,
    "kv-data": {"quiz": []},
}


def _monograph(tmp_path: Path) -> Path:
    root = fragment_monograph(tmp_path)
    folder = root / "Kutch-Ajrakh"
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    (folder / "content.json").write_text(json.dumps({**content, "data": DATA}), encoding="utf-8")
    molecules = {"molecules": [{"cid": 6293}, {"cid": 6683}], "head": None}
    (folder / "specs" / "shared__chemistry__alizarin-purpurin-3d.json").write_text(
        json.dumps(molecules), encoding="utf-8"
    )
    (folder / "specs" / "shared__climate__kachchh-district-climate-map.json").write_text(
        json.dumps({"setting": "explorer"}), encoding="utf-8"
    )
    return root


def test_a_borrowed_molecule_and_map_bring_the_kit_data_their_views_read(tmp_path: Path) -> None:
    borrowed = (
        dataclasses.replace(component(MOLECULES), kind="molecule_3d"),
        dataclasses.replace(component(MAP), kind="map_layer"),
    )
    built = assembled_document(generated(components=borrowed), Drawings(root=_monograph(tmp_path)))
    assert built is not None
    assert built.content.data["mol-data"] == {"6293": ALIZARIN, "6683": PURPURIN}
    assert built.content.data["rs-data"] == REGION
    assert "kv-data" not in built.content.data


def test_a_page_borrowing_nothing_that_reads_kit_data_carries_none(tmp_path: Path) -> None:
    built = assembled_document(generated(), Drawings(root=_monograph(tmp_path)))
    assert built is not None
    assert not {"mol-data", "rs-data", "kv-data"} & set(built.content.data)


def test_molecules_borrowed_from_two_figures_are_carried_together() -> None:
    held: dict[str, object] = {}
    merged_data(held, borrowed_data(DATA, "molecule_3d", {"molecules": [{"cid": 6293}]}))
    merged_data(held, borrowed_data(DATA, "molecule_3d", {"molecules": [{"cid": 441564}]}))
    merged_data(held, borrowed_data(DATA, "reaction_player", {"steps": []}))
    assert held == {"mol-data": {"6293": ALIZARIN, "441564": INDICAN}}
