import json

from app.sources.records import journal_of
from app.sources.scholarly.core_works import CoreAdapter
from app.sources.scholarly.crossref import CrossrefAdapter
from app.sources.scholarly.doaj import DoajAdapter
from app.sources.scholarly.elsevier import ElsevierAdapter
from app.sources.scholarly.europe_pmc import EuropePmcAdapter
from app.sources.scholarly.openalex import OpenAlexAdapter
from app.sources.scholarly.semantic_scholar import SemanticScholarAdapter
from app.sources.scholarly.springer_nature import SpringerNatureAdapter

from .recorded import CONTACT, RETRIEVED, Reply, recorded
from .test_scholarly_adapters import QUERY, adapter_for

IJFTR = "Indian Journal of Fibre & Textile Research"


async def journals(cls, routes: dict, **options) -> list[str | None]:
    adapter, _ = adapter_for(cls, routes, **options)
    return [item.container_title for item in await adapter.search(QUERY, 2)]


def test_a_journal_is_the_first_named_title_cleaned_and_storable() -> None:
    assert journal_of(["", "  Coloration <i>Technology</i> "]) == "Coloration Technology"
    assert journal_of("Dyes and Pigments") == "Dyes and Pigments"
    assert journal_of([]) is None
    assert journal_of(None) is None
    assert journal_of("J" * 301) is None


async def test_crossref_names_the_container_title() -> None:
    routes = {"api.crossref.org/works": Reply("crossref_search.json")}
    assert await journals(CrossrefAdapter, routes, contact_email=CONTACT) == [
        None,
        "INTERNATIONAL JOURNAL OF SCIENTIFIC RESEARCH IN ENGINEERING AND MANAGEMENT",
    ]


async def test_openalex_names_the_journal_its_primary_location_is_in() -> None:
    routes = {"api.openalex.org/works": Reply("openalex_search.json")}
    assert await journals(OpenAlexAdapter, routes, contact_email=CONTACT) == [None, "Coloration Technology"]


async def test_doaj_names_the_journal_beside_its_publisher() -> None:
    routes = {"doaj.org/api/v4/search/articles/alizarin%20mordant%20cotton": Reply("doaj_search.json")}
    assert await journals(DoajAdapter, routes) == [
        "Scientific Reports",
        "Journal of Bioresources and Bioproducts",
    ]


async def test_elsevier_names_the_publication() -> None:
    routes = {"api.elsevier.com/content/search/scopus": Reply("elsevier_search.json")}
    assert await journals(ElsevierAdapter, routes, api_key="els-key") == [
        "Dyes and Pigments",
        "International Journal of Biological Macromolecules",
    ]


async def test_springer_nature_names_the_publication() -> None:
    routes = {"api.springernature.com/openaccess/json": Reply("springer_nature_search.synthetic.json")}
    assert await journals(SpringerNatureAdapter, routes, api_key="sn-key") == ["Synthetic Journal"]


async def test_europe_pmc_and_semantic_scholar_name_the_journal_as_its_title() -> None:
    pmc = {"www.ebi.ac.uk/europepmc/webservices/rest/search": Reply("europe_pmc_search.json")}
    assert await journals(EuropePmcAdapter, pmc) == ["Scientific reports", "RSC advances"]
    s2 = {"api.semanticscholar.org/graph/v1/paper/search": Reply("semantic_scholar_search.json")}
    assert await journals(SemanticScholarAdapter, s2) == ["Coloration Technology", "Materials Today Energy"]


def test_core_names_the_first_journal_it_lists() -> None:
    adapter, _ = adapter_for(CoreAdapter, {}, api_key="core-key")
    work = json.loads(recorded("core_work.json"))
    assert adapter._item(work, RETRIEVED).container_title is None
    listed = work | {"journals": [{"title": " "}, {"title": IJFTR, "identifiers": ["issn:0971-0426"]}]}
    assert adapter._item(listed, RETRIEVED).container_title == IJFTR
