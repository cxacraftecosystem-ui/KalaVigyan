import dataclasses
import json
from pathlib import Path

from app.services.document_components_data import borrowed_data, merged_data, reader_data
from app.services.monograph_generated_assembly import assembled_document
from app.services.monograph_generated_drawings import Drawings
from app.services.monograph_generated_units import SourceBook

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


HINDI = "shared/chemistry/alizarin-purpurin-structures-hindi"
PURPURIN_SENTENCE = "f3.purp"
QUOTES = [{"q": "bright green", "l": "p. 8"}]
READER = {
    "sents": {
        PURPURIN_SENTENCE: [{"n": 1, "qs": QUOTES}],
        "lede.1": [{"n": 1, "qs": QUOTES}, {"n": 2, "qs": QUOTES}],
    },
    "sources": {"1": {"n": 1, "k": "gi", "t": "GI Journal"}, "2": {"n": 2, "k": "other", "t": "Other"}},
    "quiz": [{"pre": "Madder needs "}],
    "listen": {"wpm": 150, "total": 12},
}
PURPURIN_UNIT = {
    "chapter": "reading",
    "tag": "p",
    "field": "CHEMISTRY",
    "nodes": [
        {
            "m": "s",
            "sid": PURPURIN_SENTENCE,
            "c": ["Madder holds purpurin ", {"m": "cite", "key": "rm:f3.purp", "g": ["g1"], "c": ["too."]}],
        }
    ],
    "claimIds": ["C096"],
}


def _reader_monograph(tmp_path: Path) -> Path:
    root = fragment_monograph(tmp_path)
    folder = root / "Kutch-Ajrakh"
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    content["units"]["u20"] = PURPURIN_UNIT
    content["citations"]["rm:f3.purp"] = [{"source": "g1", "locator": "p. 8", "quote": "bright green"}]
    content["citationClaims"]["rm:f3.purp"] = ["C096"]
    (folder / "content.json").write_text(
        json.dumps({**content, "data": {"kv-data": READER}}), encoding="utf-8"
    )
    spec = {"id": "fig3-hi", "head": {"dek": "u20"}}
    (folder / "specs" / "shared__chemistry__alizarin-purpurin-structures-hindi.json").write_text(
        json.dumps(spec), encoding="utf-8"
    )
    return root


def test_a_borrowed_reader_figure_brings_only_the_sentences_it_holds_numbered_as_the_page_numbers_them(
    tmp_path: Path,
) -> None:
    borrowed = (dataclasses.replace(component(HINDI), kind="structure_diagram"),)
    built = assembled_document(generated(components=borrowed), Drawings(root=_reader_monograph(tmp_path)))
    assert built is not None
    [number] = [source.number for source in built.content.sources.values() if source.title == "GI Journal"]
    assert built.content.data["kv-data"] == {
        "sents": {PURPURIN_SENTENCE: [{"n": number, "qs": QUOTES}]},
        "sources": {str(number): {"n": number, "k": "gi", "t": "GI Journal"}},
    }


def test_reader_data_of_two_borrowed_figures_is_carried_together() -> None:
    held: dict[str, object] = {}
    merged_data(held, reader_data({"kv-data": READER}, {PURPURIN_SENTENCE}, {1: 4}))
    merged_data(held, reader_data({"kv-data": READER}, {"lede.1"}, {1: 4, 2: 7}))
    assert held == {
        "kv-data": {
            "sents": {
                PURPURIN_SENTENCE: [{"n": 4, "qs": QUOTES}],
                "lede.1": [{"n": 4, "qs": QUOTES}, {"n": 7, "qs": QUOTES}],
            },
            "sources": {
                "4": {"n": 4, "k": "gi", "t": "GI Journal"},
                "7": {"n": 7, "k": "other", "t": "Other"},
            },
        }
    }


def test_a_sentence_whose_source_is_not_on_the_page_keeps_only_the_sources_that_are() -> None:
    found = reader_data({"kv-data": READER}, {"lede.1", "no.such"}, {2: 3})
    assert found == {
        "kv-data": {
            "sents": {"lede.1": [{"n": 3, "qs": QUOTES}]},
            "sources": {"3": {"n": 3, "k": "other", "t": "Other"}},
        }
    }
    assert reader_data({"mol-data": {}}, {"lede.1"}, {2: 3}) == {}


HELD_KEY = "pt:C046"
HELD_CITE = {
    "m": "cite",
    "key": HELD_KEY,
    "g": ["g1"],
    "shown": [{"number": 1, "title": "GI Journal"}],
    "c": ["Barmer."],
}


def _cited_map(tmp_path: Path) -> Path:
    root = fragment_monograph(tmp_path)
    folder = root / "Kutch-Ajrakh"
    content = json.loads((folder / "content.json").read_text(encoding="utf-8"))
    content["citations"][HELD_KEY] = [{"source": "g1", "locator": "p. 9", "quote": "Barmer"}]
    content["citationClaims"][HELD_KEY] = ["C046"]
    (folder / "content.json").write_text(json.dumps(content), encoding="utf-8")
    side = [{"text": [{"m": "s", "c": ["Rain over ", HELD_CITE]}]}]
    (folder / "specs" / "shared__climate__kachchh-district-climate-map.json").write_text(
        json.dumps({"setting": "explorer", "explorer": {"side": side}}), encoding="utf-8"
    )
    return root


def test_a_citation_a_borrowed_spec_holds_names_the_source_by_the_page_s_own_number(tmp_path: Path) -> None:
    borrowed = (dataclasses.replace(component(MAP), kind="map_layer"),)
    built = assembled_document(generated(components=borrowed), Drawings(root=_cited_map(tmp_path)))
    assert built is not None
    sources = built.content.sources.items()
    [(key, gi)] = [(key, found) for key, found in sources if found.title == "GI Journal"]
    cite = built.specs[MAP]["explorer"]["side"][0]["text"][0]["c"][1]
    held = f"kutch-ajrakh:{HELD_KEY}"
    assert cite == {
        "m": "cite",
        "key": held,
        "g": [key],
        "shown": [{"number": gi.number, "title": "GI Journal"}],
        "c": ["Barmer."],
    }
    assert [quote.source for quote in built.content.citations[held]] == [key]
    assert built.content.citation_claims[held] == ["C046"]


def test_a_borrowed_spec_holding_no_citation_is_kept_as_it_is_without_reading_its_monograph(
    tmp_path: Path,
) -> None:
    spec = {"steps": [1, 2], "note": {"m": "s", "c": ["Plain."]}}
    filled = Drawings(root=tmp_path).spec_cites("No-Such-Monograph", spec, SourceBook())
    assert (filled.spec, filled.citations, filled.citation_claims) == (spec, {}, {})
