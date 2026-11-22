from datetime import date

import pytest

from app.core.errors import InvalidInput
from app.services.open_data_catalogue import payload_dataset_codes
from app.services.open_data_release import ReleaseStamp
from app.services.open_data_scope import WHOLE, ReleaseScope, scope_of_descriptor
from app.services.open_data_slice import sliced_rows, with_datasets

from .release_fixtures import AJRAKH, SITE

CREATOR = "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur"
CITED = (
    f"{CREATOR}. (2026). Kutch Ajrakh: KalaVigyan open knowledge (Version 2026.11.22) [Data set]. Zenodo. "
    "https://doi.org/10.5281/zenodo.400"
)
BIBTEX = f"""@misc{{kalavigyan_kutch_ajrakh_2026_11_22,
  author = {{{{{CREATOR}}}}},
  title = {{Kutch Ajrakh: KalaVigyan open knowledge}},
  year = {{2026}},
  version = {{2026.11.22}},
  publisher = {{Zenodo}},
  doi = {{10.5281/zenodo.400}},
  url = {{https://doi.org/10.5281/zenodo.400}}
}}"""
AJRAKH_ROW = {"slug": "Kutch-Ajrakh", "family": "Hand-Block-Printing", "category": "Textiles"}
BAGRU_ROW = {"slug": "Bagru-Prints", "family": "Hand-Block-Printing", "category": "Textiles"}
KANTHA_ROW = {"slug": "Kantha", "family": "Embroidery", "category": "Textiles"}


def test_a_craft_release_is_titled_and_cited_by_the_craft_s_name() -> None:
    assert AJRAKH.title == "Kutch Ajrakh: KalaVigyan open knowledge"
    assert AJRAKH.citation("2026.11.22", date(2026, 11, 22), "10.5281/zenodo.400") == CITED
    assert AJRAKH.bibtex("2026.11.22", date(2026, 11, 22), "10.5281/zenodo.400") == BIBTEX
    assert AJRAKH.summary.startswith(
        "The slice of KalaVigyan's knowledge about Kutch Ajrakh: the cited facts"
    )
    assert AJRAKH.keywords[-1] == "Kutch Ajrakh" and len(AJRAKH.keywords) == len(WHOLE.keywords) + 1
    assert AJRAKH.package_name == "kalavigyan-open-knowledge-kutch-ajrakh"
    assert AJRAKH.craft_page(f"{SITE}/") == "https://kalavigyan.example/crafts/Kutch-Ajrakh"


def test_the_whole_release_keeps_its_words_and_names_no_craft() -> None:
    assert (WHOLE.title, WHOLE.package_name, WHOLE.bibtex_key) == (
        "KalaVigyan open knowledge",
        "kalavigyan-open-knowledge",
        "kalavigyan_open_knowledge",
    )
    assert WHOLE.craft_page(SITE) is None and WHOLE.descriptor_property(SITE) == {}
    assert WHOLE.citation("2026.11.21", date(2026, 11, 21), "10.5281/zenodo.200").endswith(
        "KalaVigyan open knowledge (Version 2026.11.21) [Data set]. Zenodo. https://doi.org/10.5281/zenodo.200"
    )


def test_a_scope_names_both_its_slug_and_its_name_and_reads_back_from_its_descriptor() -> None:
    with pytest.raises(ValueError, match="names both"):
        ReleaseScope(craft="Kutch-Ajrakh")
    with pytest.raises(ValueError, match="names both"):
        ReleaseScope(craft="", name="")
    assert scope_of_descriptor(AJRAKH.descriptor_property(SITE)) == AJRAKH
    assert scope_of_descriptor({"name": "kalavigyan-open-knowledge"}) == WHOLE


def test_a_stamp_refuses_a_craft_that_is_not_a_slug() -> None:
    with pytest.raises(InvalidInput, match="slug"):
        ReleaseStamp(
            "SANDBOX", "2026.11.22", "10.5072/zenodo.2", "10.5072/zenodo.1", 2, 1, craft="Kutch Ajrakh"
        )
    assert ReleaseStamp("SANDBOX", "2026.11.22", "10.5072/zenodo.2", "10.5072/zenodo.1", 2, 1).craft is None


def _rows() -> dict[str, list[dict[str, object]]]:
    by_craft = [{"craft": "Kutch-Ajrakh", "key": "a"}, {"craft": "Bagru-Prints", "key": "b"}]
    return {
        "claims": [{"id": "c1"}, {"id": "c2"}],
        "citations": [{"id": "k1"}],
        "sources": [{"id": "s1"}],
        "crafts": [AJRAKH_ROW, BAGRU_ROW, KANTHA_ROW],
        "craft_places": list(by_craft),
        "categories": [{"slug": "Textiles"}, {"slug": "Metal"}],
        "families": [{"slug": "Hand-Block-Printing"}, {"slug": "Embroidery"}],
        "stages": list(by_craft),
        "materials": list(by_craft),
        "reactions": list(by_craft),
        "native_names": list(by_craft),
        "gi_records": list(by_craft),
        "components": [
            {"label": "kutch-ajrakh/vat", "craft": "Kutch-Ajrakh"},
            {"label": "shared/mordants", "craft": None},
            {"label": "bagru/dabu", "craft": "Bagru-Prints"},
        ],
        "datasets": [{"code": "IMD_RAIN"}, {"code": "ETOPO1"}],
    }


def test_a_craft_release_holds_its_craft_its_family_its_category_and_its_own_structure() -> None:
    kept = sliced_rows(_rows(), "Kutch-Ajrakh")
    assert kept["crafts"] == [AJRAKH_ROW]
    assert kept["families"] == [{"slug": "Hand-Block-Printing"}]
    assert kept["categories"] == [{"slug": "Textiles"}]
    for name in ("craft_places", "stages", "materials", "reactions", "native_names", "gi_records"):
        assert kept[name] == [{"craft": "Kutch-Ajrakh", "key": "a"}], name
    assert [row["label"] for row in kept["components"]] == ["kutch-ajrakh/vat", "shared/mordants"]
    assert (kept["claims"], kept["citations"], kept["sources"]) == (
        [{"id": "c1"}, {"id": "c2"}],
        [{"id": "k1"}],
        [{"id": "s1"}],
    )
    assert with_datasets(kept, {"IMD_RAIN"})["datasets"] == [{"code": "IMD_RAIN"}]


def test_a_craft_release_of_a_craft_without_a_family_holds_no_family_and_no_category() -> None:
    rows = {**_rows(), "crafts": [{"slug": "Kutch-Ajrakh", "family": None, "category": None}]}
    kept = sliced_rows(rows, "Kutch-Ajrakh")
    assert (kept["families"], kept["categories"]) == ([], [])


def test_the_datasets_a_component_uses_are_the_codes_its_payload_cites() -> None:
    delivered = {
        "delivered": {
            "spec": {
                "kind": "chart",
                "datasets": [{"code": "IMD_RAIN", "title": "Rain"}, {"code": "ETOPO1"}],
                "values": [{"key": "v1", "dataset_code": "IMD_RAIN"}],
                "layers": [{"datasets": [{"code": "LGD_DISTRICTS"}]}],
            },
            "units": [{"text": "datasets"}],
        }
    }
    assert payload_dataset_codes(delivered) == {"IMD_RAIN", "ETOPO1", "LGD_DISTRICTS"}
    assert payload_dataset_codes({"monograph": "Kutch-Ajrakh", "units": ["u1"]}) == set()
    assert payload_dataset_codes({"datasets": [{"title": "no code"}, "IMD_RAIN"]}) == set()
