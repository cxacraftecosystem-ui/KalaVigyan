import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import SearchQuery
from app.sources.reference.pubchem import PubChemAdapter, is_formula
from app.sources.reference.wikidata_statements import statement_lines, statements_from_bindings

from .recorded import (
    WIKIDATA_ALIZARIN,
    WIKIDATA_API,
    Recorder,
    Reply,
    fixed_clock,
    source_http,
    wikidata_adapter,
)

PUG = "pubchem.ncbi.nlm.nih.gov/rest/pug"
PROPERTIES = "property/Title,MolecularFormula,MolecularWeight,IUPACName,InChIKey,SMILES/JSON"
ALIZARIN_SMILES = "C1=CC=C2C(=C1)C(=O)C3=C(C2=O)C(=C(C=C3)O)O"


def pubchem(routes: dict):
    recorder = Recorder(routes)
    return PubChemAdapter(source_http(recorder, "pubchem"), clock=fixed_clock()), recorder


async def test_wikidata_search_returns_items_in_search_order() -> None:
    adapter, recorder = wikidata_adapter(
        {WIKIDATA_API: [Reply("wikidata_search.json"), Reply("wikidata_entities.json")]}
    )
    items = await adapter.search(SearchQuery(text="alizarin"), 3)
    assert [item.id for item in items] == ["wikidata:Q267813", "wikidata:Q4062337", "wikidata:Q3611866"]
    alizarin = items[0]
    assert alizarin.title == "alizarin"
    assert alizarin.url == "https://www.wikidata.org/wiki/Q267813"
    assert alizarin.published == "2026-09-09"
    assert (alizarin.source_type, alizarin.trust, alizarin.licence) == ("DATASET", "B", "CC0 1.0")
    assert alizarin.attribution == "Wikidata, Q267813, revision 2542539962"
    assert alizarin.external_ids == {"wikidata": "Q267813", "revision": "2542539962"}
    search, entities = (request.url.params for request in recorder.requests)
    assert (search["list"], search["srsearch"], search["srlimit"]) == ("search", "alizarin", "3")
    assert (entities["action"], entities["ids"], entities["languages"]) == (
        "wbgetentities",
        "Q267813|Q4062337|Q3611866",
        "en",
    )


async def test_wikidata_labels_fall_back_when_the_language_has_none() -> None:
    adapter, recorder = wikidata_adapter(
        {WIKIDATA_API: [Reply("wikidata_search.json"), Reply("wikidata_entities_hi.json")]}
    )
    items = await adapter.search(SearchQuery(text="alizarin", language="hi"), 3)
    assert [item.title for item in items] == [
        "alizarin",
        "sodium alizarinesulfonate",
        "Alizarin 2-beta-glucosyltransferase",
    ]
    assert recorder.requests[1].url.params["languagefallback"] == "1"


async def test_wikidata_fetch_renders_labelled_statements() -> None:
    adapter, _ = wikidata_adapter(WIKIDATA_ALIZARIN)
    document = await adapter.fetch("wikidata:Q267813")
    lines = document.text.split("\n")
    assert lines[:3] == [
        "alizarin (Q267813)",
        "chemical compound and histologic stain",
        "Also known as: Turkey Red; Alizarin Red; Alizarin B; 1,2-Anthraquinonediol; Az; Mordant Red 11; "
        "pigment red 83; C.I. 58000; 1,2-dihydroxy-9,10-anthraquinone; 1,2-dihydroxyanthra-9,10-quinone",
    ]
    assert lines[3:12] == [
        "image: Alizarin-sample.jpg",
        "instance of: type of chemical entity",
        "chemical structure: Alizarin.svg",
        f"canonical SMILES: {ALIZARIN_SMILES}",
        "chemical formula: C₁₄H₈O₄",
        "subclass of: anthraquinones",
        "part of: alizarin 2-beta-glucosyltransferase activity",
        "Commons category: Alizarin",
        "has part(s): carbon; hydrogen; oxygen",
    ]
    assert lines[-4:] == [
        "different from: Alizarine Yellow R",
        "mass: 240.042 dalton",
        "melting point: 288 degree Celsius; 289 degree Celsius",
        "boiling point: 430 degree Celsius",
    ]
    assert not any("Freebase" in line or "72-48-0" in line for line in lines)
    assert document.content == "EXCERPT"


async def test_wikidata_fetch_keeps_chemical_identifiers_and_asks_sparql_for_labels() -> None:
    adapter, recorder = wikidata_adapter(WIKIDATA_ALIZARIN)
    document = await adapter.fetch("wikidata:Q267813")
    assert document.item.external_ids == {
        "wikidata": "Q267813",
        "revision": "2542539962",
        "cas_number": "72-48-0",
        "pubchem_cid": "6293",
    }
    query = recorder.requests[1].url.params["query"]
    assert "VALUES ?item { wd:Q267813 }" in query
    assert 'wikibase:language "en,mul"' in query
    assert recorder.requests[1].headers["accept"] == "application/sparql-results+json"


async def test_wikidata_unknown_item_is_not_found_and_bad_ids_are_refused() -> None:
    adapter, _ = wikidata_adapter({WIKIDATA_API: Reply("wikidata_entity_missing.json")})
    with pytest.raises(ExternalFailure) as failure:
        await adapter.fetch("wikidata:Q999999999999")
    assert failure.value.kind == "not_found"
    for bad in ("wikidata:P31", "wikidata:Q1 } ; DROP", "wikidata:Q0"):
        with pytest.raises(InvalidInput):
            await adapter.fetch(bad)


def test_unitless_quantities_carry_no_unit() -> None:
    row = {
        "property": {"value": "http://www.wikidata.org/entity/P1117"},
        "propertyLabel": {"value": "pKa"},
        "type": {"value": "http://wikiba.se/ontology#Quantity"},
        "value": {"value": "6.77"},
        "unit": {"value": "http://www.wikidata.org/entity/Q199"},
        "unitLabel": {"value": "1"},
    }
    assert statement_lines(statements_from_bindings([row])) == ["pKa: 6.77"]


async def test_pubchem_name_search_puts_the_exact_name_first() -> None:
    adapter, recorder = pubchem(
        {
            f"{PUG}/compound/name/alizarin/cids/JSON": [
                Reply("pubchem_name_cids.json"),
                Reply("pubchem_word_cids.json"),
            ],
            f"{PUG}/compound/cid/6293,3955344,20431/{PROPERTIES}": Reply("pubchem_properties.json"),
        }
    )
    items = await adapter.search(SearchQuery(text="alizarin"), 3)
    assert [item.id for item in items] == ["pubchem:6293", "pubchem:3955344", "pubchem:20431"]
    assert [item.title for item in items] == ["Alizarin", "Sodium alizarinesulfonate", "Acid Green 25"]
    alizarin = items[0]
    assert alizarin.url == "https://pubchem.ncbi.nlm.nih.gov/compound/6293"
    assert (alizarin.source_type, alizarin.trust) == ("COMPOUND_RECORD", "A")
    assert alizarin.licence == "https://www.ncbi.nlm.nih.gov/home/about/policies/"
    assert alizarin.attribution == "PubChem, National Library of Medicine, CID 6293"
    assert alizarin.external_ids == {"pubchem_cid": "6293", "inchikey": "RGCKGOZRHPZPFP-UHFFFAOYSA-N"}
    assert "name_type" not in recorder.requests[0].url.params
    assert recorder.requests[1].url.params["name_type"] == "word"


async def test_pubchem_formula_search_uses_fast_formula() -> None:
    adapter, recorder = pubchem(
        {
            f"{PUG}/compound/fastformula/C14H8O4/cids/JSON": Reply("pubchem_formula_cids.json"),
            f"{PUG}/compound/cid/6293,2950/{PROPERTIES}": Reply("pubchem_formula_properties.json"),
        }
    )
    items = await adapter.search(SearchQuery(text="C₁₄H₈O₄"), 2)
    assert [item.title for item in items] == ["Alizarin", "1,8-Dihydroxyanthraquinone"]
    assert recorder.requests[0].url.params["MaxRecords"] == "2"


def test_formula_detection_needs_real_element_symbols() -> None:
    assert is_formula("C14H8O4")
    assert is_formula("NaCl")
    assert is_formula("Fe2O3")
    assert not is_formula("EDTA")
    assert not is_formula("Alum")
    assert not is_formula("Ca")
    assert not is_formula("indigo dye")


async def test_pubchem_no_match_is_an_empty_list() -> None:
    adapter, _ = pubchem(
        {
            f"{PUG}/compound/name/alizarin%20mordant%20cotton/cids/JSON": Reply(
                "pubchem_not_found.json", status=404
            )
        }
    )
    assert await adapter.search(SearchQuery(text="alizarin mordant cotton"), 3) == []


async def test_pubchem_fetch_lists_the_computed_properties() -> None:
    adapter, _ = pubchem({f"{PUG}/compound/cid/6293/{PROPERTIES}": Reply("pubchem_compound.json")})
    document = await adapter.fetch("pubchem:6293")
    assert document.text.split("\n") == [
        "Alizarin (PubChem CID 6293)",
        "Molecular formula: C14H8O4",
        "Molecular weight: 240.21 g/mol",
        "IUPAC name: 1,2-dihydroxyanthracene-9,10-dione",
        "InChIKey: RGCKGOZRHPZPFP-UHFFFAOYSA-N",
        f"SMILES: {ALIZARIN_SMILES}",
    ]
    assert document.content == "EXCERPT"


async def test_pubchem_hazards_carry_the_reporting_source_and_its_licence() -> None:
    adapter, recorder = pubchem(
        {"pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/6293/JSON": Reply("pubchem_ghs.json")}
    )
    document = await adapter.fetch("pubchem:6293:ghs")
    lines = document.text.split("\n")
    assert lines[:9] == [
        "Alizarin (PubChem CID 6293): GHS classification",
        "Reported by European Chemicals Agency (ECHA):",
        "Note: This chemical does not meet GHS hazard criteria for 10.8% (8 of 74) of reports.",
        "Pictogram(s): Irritant",
        "Signal: Warning",
        "GHS Hazard Statements:",
        "H302 (55.4%): Harmful if swallowed [Warning Acute toxicity, oral]",
        "H315 (25.7%): Causes skin irritation [Warning Skin corrosion/irritation]",
        "H319 (33.8%): Causes serious eye irritation [Warning Serious eye damage/eye irritation]",
    ]
    assert not any(line.startswith("Precautionary") for line in lines)
    item = document.item
    assert item.id == "pubchem:6293:ghs"
    assert item.url == "https://chem.echa.europa.eu/substance-search?searchText=200-782-5"
    assert item.licence == "https://echa.europa.eu/web/guest/legal-notice"
    assert item.attribution == (
        "Source: European Chemicals Agency (ECHA), https://chem.echa.europa.eu/substance-search?searchText=200-782-5;"
        " via PubChem CID 6293"
    )
    assert item.publisher == "European Chemicals Agency (ECHA)"
    assert recorder.requests[0].url.params["heading"] == "GHS Classification"


async def test_pubchem_without_hazard_data_is_not_found() -> None:
    adapter, _ = pubchem(
        {
            "pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/135699794/JSON": Reply(
                "pubchem_ghs_missing.json", status=404
            )
        }
    )
    with pytest.raises(ExternalFailure, match="GHS") as failure:
        await adapter.fetch("pubchem:135699794:ghs")
    assert failure.value.kind == "not_found"


async def test_pubchem_ids_are_cids() -> None:
    adapter, _ = pubchem({})
    for bad in ("pubchem:alizarin", "pubchem:0", "pubchem:6293:sds", "pubchem:6293/../1"):
        with pytest.raises(InvalidInput):
            await adapter.fetch(bad)
