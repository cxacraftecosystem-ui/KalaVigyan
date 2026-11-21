import hashlib
import logging

import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import EvidenceItem, Quote, SearchQuery, SourceAdapter, SourceDocument
from app.sources.scholarly.arxiv import ArxivAdapter
from app.sources.scholarly.core_works import CoreAdapter
from app.sources.scholarly.crossref import CrossrefAdapter
from app.sources.scholarly.doaj import DoajAdapter
from app.sources.scholarly.elsevier import ElsevierAdapter
from app.sources.scholarly.europe_pmc import EuropePmcAdapter
from app.sources.scholarly.openalex import OpenAlexAdapter
from app.sources.scholarly.semantic_scholar import SemanticScholarAdapter
from app.sources.scholarly.springer_nature import SpringerNatureAdapter

from .recorded import CONTACT, RETRIEVED, Recorder, Reply, fixed_clock, source_http

QUERY = SearchQuery(text="alizarin mordant cotton")


def adapter_for(cls, routes: dict, **options):
    recorder = Recorder(routes)
    return cls(source_http(recorder, cls.name), clock=fixed_clock(), **options), recorder


async def test_openalex_search_normalises_works() -> None:
    adapter, recorder = adapter_for(
        OpenAlexAdapter,
        {"api.openalex.org/works": Reply("openalex_search.json")},
        contact_email=CONTACT,
        api_key="oa-key",
    )
    items = await adapter.search(QUERY, 2)
    assert [item.id for item in items] == ["openalex:W566549159", "openalex:W2625322139"]
    first, second = items
    assert first.url == "https://openalex.org/W566549159"
    assert first.doi is None
    assert first.published == "1993-01-01"
    assert first.authors == ["Takeshi Kako"]
    assert second.url == "https://doi.org/10.1111/cote.12288"
    assert second.source_key == "doi:10.1111/cote.12288"
    assert second.publisher == "Wiley"
    assert second.authors == ["Yi Ding", "Harold Stanley Freeman"]
    assert (second.source_type, second.trust, second.tier) == ("PAPER", "A", "T3")
    assert second.retrieved_at == RETRIEVED
    sent = recorder.requests[0].url.params
    assert (sent["search"], sent["per-page"], sent["mailto"], sent["api_key"]) == (
        "alizarin mordant cotton",
        "2",
        CONTACT,
        "oa-key",
    )


async def test_openalex_fetch_rebuilds_the_abstract() -> None:
    adapter, _ = adapter_for(
        OpenAlexAdapter,
        {"api.openalex.org/works/W2625322139": Reply("openalex_work.json")},
        contact_email=CONTACT,
    )
    document = await adapter.fetch("openalex:W2625322139")
    assert document.content == "ABSTRACT"
    assert document.text.startswith(
        "It is well known that cotton fibres can be dyed through the formation of"
    )
    assert document.text_sha256 == hashlib.sha256(document.text.encode("utf-8")).hexdigest()
    assert not document.truncated
    assert document.item.id == "openalex:W2625322139"


async def test_openalex_unknown_work_is_not_found() -> None:
    adapter, _ = adapter_for(
        OpenAlexAdapter,
        {"api.openalex.org/works/W1": Reply("openalex_missing.html", status=404)},
        contact_email=CONTACT,
    )
    with pytest.raises(ExternalFailure) as failure:
        await adapter.fetch("openalex:W1")
    assert failure.value.kind == "not_found"
    assert failure.value.tries_next


async def test_crossref_search_and_fetch() -> None:
    adapter, recorder = adapter_for(
        CrossrefAdapter,
        {
            "api.crossref.org/works": Reply("crossref_search.json"),
            "api.crossref.org/works/10.55041/ijsrem46137": Reply("crossref_work.json"),
        },
    )
    items = await adapter.search(QUERY, 5)
    assert [item.id for item in items] == [
        "crossref:10.21203/rs.3.rs-1170326/v2",
        "crossref:10.55041/ijsrem46137",
    ]
    preprint, article = items
    assert (preprint.source_type, preprint.trust) == ("PAPER", "B")
    assert preprint.licence == "https://creativecommons.org/licenses/by/4.0/"
    assert preprint.published == "2022-02-17"
    assert article.authors == ["Ms.Monika Choudhary"]
    assert article.publisher == "Edtech Publishers (OPC) Private Limited"
    assert (article.source_type, article.trust) == ("PAPER", "A")
    assert recorder.requests[0].url.params["filter"] == "has-abstract:true"
    assert "mailto" not in recorder.requests[0].url.params
    assert recorder.requests[0].headers["User-Agent"] == "KalaVigyan/1 (+https://kalavigyan.vercel.app)"
    assert CONTACT not in str(recorder.requests[0].url)
    document = await adapter.fetch("crossref:10.55041/ijsrem46137")
    assert document.text.startswith(
        "Abstract Clothing serves several essential functions, including protection, identification, and adornment."
    )
    assert "<jats:p>" not in document.text
    assert "flower & leaf" in document.text


async def test_crossref_unknown_doi_is_not_found() -> None:
    adapter, _ = adapter_for(
        CrossrefAdapter,
        {"api.crossref.org/works/10.9999/missing": Reply("crossref_missing.txt", status=404)},
    )
    with pytest.raises(ExternalFailure) as failure:
        await adapter.fetch("crossref:10.9999/missing")
    assert failure.value.kind == "not_found"


async def test_semantic_scholar_search_fetch_and_elided_abstract() -> None:
    adapter, recorder = adapter_for(
        SemanticScholarAdapter,
        {
            "api.semanticscholar.org/graph/v1/paper/search": Reply("semantic_scholar_search.json"),
            "api.semanticscholar.org/graph/v1/paper/5a75f51ed9119ee7203bc29776f55b6488b8acb2": Reply(
                "semantic_scholar_paper.json"
            ),
            "api.semanticscholar.org/graph/v1/paper/46907c3237cfd943f750bd7d3abc80f3869adab6": Reply(
                "semantic_scholar_paper_no_abstract.json"
            ),
        },
        api_key="s2-key",
    )
    items = await adapter.search(QUERY, 2)
    closed, arxiv = items
    assert closed.doi == "10.1111/COTE.12288"
    assert closed.source_key == "doi:10.1111/cote.12288"
    assert closed.publisher == "Coloration Technology"
    assert closed.authors == ["Yi Ding", "H. Freeman"]
    assert (arxiv.source_type, arxiv.trust, arxiv.licence) == ("PAPER", "A", "CCBY")
    assert arxiv.published == "2022-07-01"
    assert recorder.requests[0].headers["x-api-key"] == "s2-key"
    assert "x-api-key" not in recorder.requests[0].url.params
    document = await adapter.fetch(arxiv.id)
    assert document.text.startswith("Functionalized TiO2 nanoparticles with intense fluorescent dyes")
    with pytest.raises(ExternalFailure, match="no abstract") as failure:
        await adapter.fetch(closed.id)
    assert failure.value.kind == "not_found"


async def test_semantic_scholar_rate_limit_is_reported() -> None:
    adapter, _ = adapter_for(
        SemanticScholarAdapter,
        {"api.semanticscholar.org/graph/v1/paper/search": Reply("semantic_scholar_429.json", status=429)},
    )
    with pytest.raises(ExternalFailure) as failure:
        await adapter.search(QUERY, 2)
    assert (failure.value.kind, failure.value.retryable) == ("rate_limit", True)


async def test_core_search_and_full_text_fetch() -> None:
    adapter, recorder = adapter_for(
        CoreAdapter,
        {
            "api.core.ac.uk/v3/search/works/": Reply("core_search.json"),
            "api.core.ac.uk/v3/works/67302936": Reply("core_work.json"),
        },
        api_key="core-key",
    )
    items = await adapter.search(QUERY, 2)
    assert [item.id for item in items] == ["core:214982727", "core:67302936"]
    assert items[0].authors == ["Toshiko Amemiya", "Tadashi Nakanishi"]
    assert items[0].published == "2017-02-23"
    assert (items[0].source_type, items[0].trust) == ("PAPER", "B")
    assert recorder.requests[0].headers["Authorization"] == "Bearer core-key"
    document = await adapter.fetch("core:67302936")
    assert document.content == "FULL_TEXT"
    assert document.text.startswith("Indian Journal of Fibre & Textile Research")


def test_core_needs_its_key() -> None:
    with pytest.raises(ValueError, match="CORE_API_KEY"):
        adapter_for(CoreAdapter, {}, api_key="")


async def test_europe_pmc_search_and_fetch() -> None:
    adapter, recorder = adapter_for(
        EuropePmcAdapter, {"www.ebi.ac.uk/europepmc/webservices/rest/search": Reply("europe_pmc_search.json")}
    )
    items = await adapter.search(QUERY, 2)
    assert [item.id for item in items] == ["europe_pmc:MED:42168406", "europe_pmc:MED:42799031"]
    first = items[0]
    assert first.authors[:2] == ["Poonthong W", "Yuji T"]
    assert (first.published, first.licence, first.publisher) == (
        "2026-05-21",
        "cc by-nc-nd",
        "Scientific reports",
    )
    assert first.url == "https://doi.org/10.1038/s41598-026-52122-5"
    fetcher, fetch_recorder = adapter_for(
        EuropePmcAdapter, {"www.ebi.ac.uk/europepmc/webservices/rest/search": Reply("europe_pmc_record.json")}
    )
    document = await fetcher.fetch("europe_pmc:MED:42168406")
    assert document.text.startswith("This study presents an improved natural dyeing method for wool fabric")
    assert fetch_recorder.requests[0].url.params["query"] == "EXT_ID:42168406 AND SRC:MED"
    assert recorder.requests[0].url.params["resultType"] == "core"


async def test_arxiv_search_and_fetch() -> None:
    adapter, recorder = adapter_for(ArxivAdapter, {"export.arxiv.org/api/query": Reply("arxiv_search.xml")})
    items = await adapter.search(SearchQuery(text="alizarin dye"), 2)
    assert [item.id for item in items] == ["arxiv:2207.00830v1", "arxiv:1607.05545v1"]
    first = items[0]
    assert first.url == "https://arxiv.org/abs/2207.00830v1"
    assert first.doi == "10.1016/j.mtener.2022.101085"
    assert first.authors == ["Federico Soria", "Chiara Daldossi", "Cristiana Di Valentin"]
    assert (first.published, first.source_type, first.trust) == ("2022-07-02", "PAPER", "B")
    assert recorder.requests[0].url.params["search_query"] == "all:alizarin AND all:dye"
    fetcher, _ = adapter_for(ArxivAdapter, {"export.arxiv.org/api/query": Reply("arxiv_record.xml")})
    document = await fetcher.fetch("arxiv:2207.00830v1")
    assert document.text.startswith("Functionalized TiO2 nanoparticles with intense fluorescent dyes")


async def test_doaj_search_and_fetch() -> None:
    adapter, recorder = adapter_for(
        DoajAdapter,
        {
            "doaj.org/api/v4/search/articles/alizarin%20mordant%20cotton": Reply("doaj_search.json"),
            "doaj.org/api/v4/articles/270012ac76064f23948b99c92aed70d0": Reply("doaj_article.json"),
        },
    )
    items = await adapter.search(QUERY, 2)
    assert [item.id for item in items] == [
        "doaj:270012ac76064f23948b99c92aed70d0",
        "doaj:5f18c15ee1cb4b9eaf523df3c092ea35",
    ]
    assert items[0].doi == "10.1038/s41598-022-27110-0"
    assert (items[0].published, items[0].publisher) == ("2023-01", "Nature Portfolio")
    assert items[1].doi == "10.1016/j.jobab.2022.07.003"
    assert items[1].published == "2022-11"
    assert recorder.requests[0].url.params["pageSize"] == "2"
    document = await adapter.fetch(items[0].id)
    assert document.text.startswith("Abstract Because of its low critical temperature and pressure levels")


async def test_elsevier_search_and_a_key_without_abstract_rights() -> None:
    adapter, recorder = adapter_for(
        ElsevierAdapter,
        {
            "api.elsevier.com/content/search/scopus": Reply("elsevier_search.json"),
            "api.elsevier.com/content/abstract/scopus_id/105054490722": Reply(
                "elsevier_abstract_no_description.json"
            ),
            "api.elsevier.com/content/abstract/scopus_id/105039809304": Reply(
                "elsevier_view_refused.json", status=401
            ),
        },
        api_key="els-key",
    )
    items = await adapter.search(QUERY, 2)
    assert [item.id for item in items] == ["elsevier:105054490722", "elsevier:105039809304"]
    assert items[0].doi == "10.1016/j.dyepig.2026.114301"
    assert (items[0].authors, items[0].publisher) == (["Dai Y."], "Dyes and Pigments")
    assert recorder.requests[0].url.params["query"] == "TITLE-ABS-KEY(alizarin mordant cotton)"
    assert recorder.requests[0].headers["X-ELS-APIKey"] == "els-key"
    with pytest.raises(ExternalFailure, match="no abstract") as missing:
        await adapter.fetch(items[0].id)
    assert missing.value.kind == "not_found"
    with pytest.raises(ExternalFailure) as refused:
        await adapter.fetch(items[1].id)
    assert refused.value.kind == "auth"


async def test_springer_nature_shapes_and_refused_key() -> None:
    adapter, recorder = adapter_for(
        SpringerNatureAdapter,
        {"api.springernature.com/openaccess/json": Reply("springer_nature_search.synthetic.json")},
        api_key="sn-key",
    )
    items = await adapter.search(QUERY, 1)
    assert items[0].id == "springer_nature:10.1000/kv.synthetic.1"
    assert items[0].authors == ["Tester, Ada", "Fixture, Ben"]
    assert recorder.requests[0].url.params["api_key"] == "sn-key"
    document = await adapter.fetch(items[0].id)
    assert document.text == "A synthetic abstract standing in for a recorded Springer Nature response."
    refused, _ = adapter_for(
        SpringerNatureAdapter,
        {"api.springernature.com/openaccess/json": Reply("springer_nature_401.json", status=401)},
        api_key="wrong",
    )
    with pytest.raises(ExternalFailure) as failure:
        await refused.search(QUERY, 1)
    assert failure.value.kind == "auth"


async def test_k_and_ids_are_checked() -> None:
    adapter, _ = adapter_for(DoajAdapter, {})
    for k in (0, 51, True):
        with pytest.raises(InvalidInput):
            await adapter.search(QUERY, k)
    with pytest.raises(InvalidInput):
        await adapter.fetch("openalex:W1")


async def test_freshness_keeps_recent_dated_items_only() -> None:
    adapter, _ = adapter_for(
        OpenAlexAdapter, {"api.openalex.org/works": Reply("openalex_search.json")}, contact_email=CONTACT
    )
    items = await adapter.search(SearchQuery(text="alizarin mordant", freshness_days=3650), 2)
    assert [item.id for item in items] == ["openalex:W2625322139"]


async def test_results_beyond_k_are_dropped() -> None:
    adapter, _ = adapter_for(
        EuropePmcAdapter, {"www.ebi.ac.uk/europepmc/webservices/rest/search": Reply("europe_pmc_search.json")}
    )
    assert len(await adapter.search(QUERY, 1)) == 1


async def test_a_record_without_an_id_is_left_out_and_logged(caplog: pytest.LogCaptureFixture) -> None:
    adapter, _ = adapter_for(DoajAdapter, {})
    with caplog.at_level(logging.WARNING):
        items = adapter._usable_items([{"id": "not-an-id", "bibjson": {"title": "x"}}], RETRIEVED)
    assert items == []
    assert "doaj left out result 0: no DOAJ article id" in caplog.text


@pytest.mark.parametrize(
    "cls",
    [
        OpenAlexAdapter,
        CrossrefAdapter,
        SemanticScholarAdapter,
        CoreAdapter,
        EuropePmcAdapter,
        ArxivAdapter,
        DoajAdapter,
        ElsevierAdapter,
        SpringerNatureAdapter,
    ],
)
def test_every_adapter_meets_the_source_adapter_contract(cls) -> None:
    options = {"contact_email": CONTACT} if cls is OpenAlexAdapter else {}
    if cls in (CoreAdapter, ElsevierAdapter, SpringerNatureAdapter):
        options["api_key"] = "key"
    adapter, _ = adapter_for(cls, {}, **options)
    assert isinstance(adapter, SourceAdapter)
    assert adapter.tier == "T3"


async def test_a_quote_taken_from_a_fetched_document_passes_the_contract_check() -> None:
    adapter, _ = adapter_for(
        EuropePmcAdapter, {"www.ebi.ac.uk/europepmc/webservices/rest/search": Reply("europe_pmc_record.json")}
    )
    document = await adapter.fetch("europe_pmc:MED:42168406")
    quote = Quote(text="integrating iron mordant treatment with atmospheric-pressure")
    quoted = EvidenceItem.model_validate(document.item.model_dump() | {"quotes": [quote]})
    rebuilt = SourceDocument(
        item=quoted,
        text=document.text,
        text_sha256=document.text_sha256,
        truncated=document.truncated,
        content=document.content,
    )
    assert rebuilt.item.quotes[0].text in rebuilt.text
