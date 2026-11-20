import json
from pathlib import Path

import pytest

from app.core.errors import InvalidInput
from app.services.monograph_generated_drawings import Drawings, fragment_file_name
from app.services.monograph_generated_units import SourceBook

from .generated_parts import VAT_DIP, fragment_monograph


def rewritten(root: Path, markup: str) -> None:
    folder = root / "Kutch-Ajrakh"
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    content["data"] = {"rs-data": {"steps": ["vat", "air"]}}
    (folder / "content.json").write_text(json.dumps(content), encoding="utf-8")
    (folder / "fragments" / fragment_file_name(VAT_DIP)).write_text(markup, encoding="utf-8")


def test_a_fragment_file_is_named_like_its_spec_file() -> None:
    assert fragment_file_name("shared/chemistry/indigo-vat-dip") == "shared__chemistry__indigo-vat-dip.html"


def test_a_fragments_data_slot_is_filled_from_its_monograph(tmp_path: Path) -> None:
    root = fragment_monograph(tmp_path)
    rewritten(
        root, '<script type="application/json" id="rs-data"><kv-slot data="rs-data"></kv-slot></script>'
    )
    filled = Drawings(root=root).fragment("Kutch-Ajrakh", VAT_DIP, SourceBook())
    assert filled.markup == '<script type="application/json" id="rs-data">{"steps": ["vat", "air"]}</script>'
    assert (filled.citations, filled.citation_claims) == ({}, {})


def test_a_fragment_slot_for_a_unit_its_monograph_lacks_is_refused(tmp_path: Path) -> None:
    root = fragment_monograph(tmp_path)
    rewritten(root, '<p><kv-slot unit="u404"></kv-slot></p>')
    with pytest.raises(InvalidInput, match=r"lacks: \['u404'\]"):
        Drawings(root=root).fragment("Kutch-Ajrakh", VAT_DIP, SourceBook())


def test_a_monograph_name_that_is_not_a_folder_slug_is_refused(tmp_path: Path) -> None:
    with pytest.raises(InvalidInput, match="No monograph folder"):
        Drawings(root=tmp_path).spec("../Kutch-Ajrakh", VAT_DIP)
    assert Drawings(root=tmp_path).spec("Kutch-Ajrakh", VAT_DIP) is None
    assert Drawings(root=tmp_path).has_fragment("Kutch-Ajrakh", VAT_DIP) is False


def test_a_specs_units_are_the_strings_that_name_its_monographs_units(tmp_path: Path) -> None:
    root = fragment_monograph(tmp_path)
    named = Drawings(root=root).spec_units(
        "Kutch-Ajrakh", {"a": ["u9", "u404"], "b": {"c": "u9"}, "n": 9}, SourceBook()
    )
    assert list(named.units) == ["u9"]
    cite = named.units["u9"].nodes[0]["c"][1]
    assert cite["key"] == "kutch-ajrakh:chem:q6"
    assert list(named.citations) == ["kutch-ajrakh:chem:q6"]
    assert named.citation_claims == {"kutch-ajrakh:chem:q6": ["C086"]}
    assert Drawings(root=root).spec_units("Kutch-Ajrakh", {"steps": [1, 2]}, SourceBook()).units == {}
    assert (
        Drawings(root=tmp_path / "none").spec_units("Kutch-Ajrakh", {"steps": ["vat"]}, SourceBook()).units
        == {}
    )
