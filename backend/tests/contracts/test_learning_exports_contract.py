import copy
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.citation_export import CitationExport
from app.research.datasets import BOUNDARY_CAPTION
from app.schemas.district_crafts import DistrictCrafts

from .golden import golden_json, reproduces
from .learning_golden import (
    CITATIONS,
    DISTRICT_CRAFTS,
    SHARED_SCIENCE,
    VERSIONS,
    SharedScienceFixture,
    learning,
)
from .phase_d_golden import phase_d_blocks

KV4_BIBTEX = (
    "@misc{kv4,\n"
    "  author = {{Azera Parveen Rahman}},\n"
    "  title = {{Water woes: Kutch's age-old Ajrakh craft faces its nemesis, once again}},\n"
    "  howpublished = {Mongabay India},\n"
    "  year = {2019},\n"
    "  url = {https://india.mongabay.com/2019/10/water-woes-kutchs-age-old-ajrakh-craft-faces-its-nemesis-once-again/},\n"
    "}\n"
)
KV4_RIS = (
    "TY  - ELEC\r\n"
    "AU  - Azera Parveen Rahman\r\n"
    "TI  - Water woes: Kutch's age-old Ajrakh craft faces its nemesis, once again\r\n"
    "PY  - 2019\r\n"
    "PB  - Mongabay India\r\n"
    "UR  - https://india.mongabay.com/2019/10/water-woes-kutchs-age-old-ajrakh-craft-faces-its-nemesis-once-again/\r\n"
    "ID  - kv4\r\n"
    "ER  - \r\n"
)
KV4_APA = (
    "Azera Parveen Rahman. (2019). Water woes: Kutch's age-old Ajrakh craft faces its nemesis, once again. "
    "Mongabay India. https://india.mongabay.com/2019/10/water-woes-kutchs-age-old-ajrakh-craft-faces-its-"
    "nemesis-once-again/"
)
CSL_OF = {"GI_JOURNAL": "document", "WEB_PAGE": "webpage"}


def export() -> CitationExport:
    return CitationExport.model_validate(learning(CITATIONS))


@pytest.mark.parametrize(
    ("fixture", "name"),
    [(CitationExport, CITATIONS), (SharedScienceFixture, SHARED_SCIENCE), (DistrictCrafts, DISTRICT_CRAFTS)],
)
def test_the_export_and_map_fixtures_are_reproduced_byte_for_byte(fixture: Any, name: str) -> None:
    assert reproduces(fixture, name)


def test_citations_are_the_latest_version_s_sources_numbered_as_shown() -> None:
    latest = learning(VERSIONS)["latest"]
    body = export()
    assert (str(body.explainer_id), body.version) == (
        latest["mark"]["explainerId"],
        latest["mark"]["version"],
    )
    assert [entry.source_id for entry in body.entries] == [s["id"] for s in latest["explainer"]["sources"]]


def test_each_csl_item_carries_the_stored_source_as_written() -> None:
    sources = {s["id"]: s for s in learning(VERSIONS)["latest"]["explainer"]["sources"]}
    for entry in export().entries:
        source = sources[entry.source_id]
        item = entry.csl
        assert (item.id, item.type, item.title) == (
            f"kv{entry.number}",
            CSL_OF[source["kind"]],
            source["title"],
        )
        assert [name.literal for name in item.author] == source["authors"]
        issued = None if source["year"] is None else [[source["year"]]]
        assert (item.issued.date_parts if item.issued else None) == issued
        assert (item.publisher, item.doi, item.url) == (source["publisher"], source["doi"], source["url"])


def test_bibtex_ris_and_apa_follow_the_contract_rules() -> None:
    entry = export().entries[3]
    assert (entry.bibtex, entry.ris, entry.apa) == (KV4_BIBTEX, KV4_RIS, KV4_APA)
    undated = export().entries[4]
    assert "(n.d.)" in undated.apa and "PY  - " not in undated.ris and "year = " not in undated.bibtex
    assert "Designs \\& Trade Marks" in export().entries[0].bibtex


def test_a_citation_names_one_thing_under_one_key() -> None:
    payload = copy.deepcopy(learning(CITATIONS))
    payload["entries"][0]["datasetCode"] = "CHIRPS_3_0"
    with pytest.raises(ValidationError, match="a source or a dataset row, not both"):
        CitationExport.model_validate(payload)
    payload = copy.deepcopy(learning(CITATIONS))
    payload["entries"][0]["ris"] = payload["entries"][0]["ris"].replace("\r\n", "\n")
    with pytest.raises(ValidationError, match="CRLF line ends"):
        CitationExport.model_validate(payload)


def test_shared_science_is_the_concept_graph_s_nodes_for_the_craft() -> None:
    fixture = SharedScienceFixture.model_validate(learning(SHARED_SCIENCE))
    graph = phase_d_blocks()["s2.b1"]
    assert fixture.craft.craft.slug == graph["focus"]["slug"]
    for node, expected in zip(fixture.craft.nodes, graph["nodes"], strict=True):
        shown = node.model_dump(mode="json", by_alias=True)
        assert [c["sentence"] | {"id": ""} for c in shown["crafts"]] == [
            c["sentence"] | {"id": ""} for c in expected["crafts"]
        ]
        assert [c["sentence"]["id"] for c in shown["crafts"]] == [
            f"{node.term_key}.{n}" for n in range(1, len(node.crafts) + 1)
        ]
    assert fixture.concept.node == fixture.craft.nodes[0]


def test_a_tapped_district_lists_its_cited_crafts_and_the_land_s_stored_story() -> None:
    body = DistrictCrafts.model_validate(learning(DISTRICT_CRAFTS))
    region = golden_json("region.craft.golden.json")
    place = next(p for p in region["places"] if p["key"] == "district-449")
    assert body.district.district_lgd == 449 and body.district.name == place["districtName"]
    assert [entry.craft.slug for entry in body.crafts] == ["Kutch-Ajrakh"]
    assert body.crafts[0].basis.model_dump(mode="json", by_alias=True) == place["basis"]
    story = body.land.blocks[0]
    phase_b_story = golden_json("explainer.phase-b.golden.json")["sections"][0]["blocks"][0]
    assert story.kind == "region_story" and story.reuse is not None
    assert [s.sentence.text for s in story.steps] == [s["sentence"]["text"] for s in phase_b_story["steps"]]
    assert [f.facet for f in body.land.facets] == ["SOIL", "CLIMATE", "WATER", "TERRAIN"]
    shown = {(v.dataset_code, v.variable, v.stat): v.value for f in body.land.facets for v in f.values}
    card = {
        (v["datasetCode"], v["variable"], v["stat"]): v["value"] for f in place["facets"] for v in f["values"]
    }
    assert shown.items() <= card.items()
    assert shown[("SOILGRIDS_2_0", "phh2o", "DISTRICT_MEAN")] == 7.281044
    assert [d.code for d in body.datasets] == [
        "DR_DISTRICT_SHAPES",
        "CHELSA_2_1_1981_2010",
        "CHIRPS_3_0",
        "COPERNICUS_DEM_GLO90",
        "GHCN_CAMS_T2M",
        "HYDRORIVERS_1_0",
        "SOILGRIDS_2_0",
    ]
    assert body.boundary_caption == BOUNDARY_CAPTION


def test_a_district_lists_only_located_crafts_and_stored_stories() -> None:
    payload = copy.deepcopy(learning(DISTRICT_CRAFTS))
    payload["land"]["blocks"][0]["reuse"] = None
    with pytest.raises(ValidationError, match="placed from a stored piece"):
        DistrictCrafts.model_validate(payload)
    payload = copy.deepcopy(learning(DISTRICT_CRAFTS))
    payload["crafts"][0]["basis"] = {
        "kind": "MASTER_LIST",
        "sourceId": None,
        "label": "IIT Crafts Master List, 2026-10-20",
        "level": "REVIEWED",
    }
    with pytest.raises(ValidationError, match="only by a cited location"):
        DistrictCrafts.model_validate(payload)
