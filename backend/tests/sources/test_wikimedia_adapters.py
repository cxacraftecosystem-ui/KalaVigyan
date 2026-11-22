import hashlib

import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import SearchQuery
from app.sources.reference.commons import WikimediaCommonsAdapter
from app.sources.reference.wikipedia import WikipediaAdapter, wiki_language

from .recorded import RETRIEVED, Recorder, Reply, fixed_clock, source_http

EN_API = "en.wikipedia.org/w/api.php"
HI_API = "hi.wikipedia.org/w/api.php"
FR_API = "fr.wikipedia.org/w/api.php"
YUE_API = "zh-yue.wikipedia.org/w/api.php"
COMMONS_API = "commons.wikimedia.org/w/api.php"
CC_BY_SA_4 = "Creative Commons Attribution-Share Alike 4.0"


def adapter_for(cls, routes: dict):
    recorder = Recorder(routes)
    return cls(source_http(recorder, cls.name), clock=fixed_clock()), recorder


async def test_wikipedia_search_normalises_articles_in_search_order() -> None:
    adapter, recorder = adapter_for(WikipediaAdapter, {EN_API: Reply("wikipedia_search.json")})
    items = await adapter.search(SearchQuery(text="ajrakh block printing"), 3)
    assert [item.id for item in items] == [
        "wikipedia:en:8807398",
        "wikipedia:en:33536457",
        "wikipedia:en:73948903",
    ]
    ajrak = items[0]
    assert ajrak.title == "Ajrak"
    assert ajrak.url == "https://en.wikipedia.org/wiki/Ajrak"
    assert ajrak.published == "2026-11-12"
    assert (ajrak.source_type, ajrak.trust, ajrak.tier) == ("ENCYCLOPEDIA", "B", "T3")
    assert ajrak.licence == CC_BY_SA_4
    assert ajrak.attribution == 'Wikipedia contributors, "Ajrak", en Wikipedia, revision 1385329287'
    assert ajrak.publisher == "Wikimedia Foundation"
    assert ajrak.external_ids == {
        "wikipedia": "en:8807398",
        "revision": "1385329287",
        "wikidata": "Q104218192",
    }
    assert ajrak.quotes == []
    assert ajrak.retrieved_at == RETRIEVED
    sent = recorder.requests[0].url.params
    assert (sent["generator"], sent["gsrsearch"], sent["gsrlimit"], sent["errorformat"]) == (
        "search",
        "ajrakh block printing",
        "3",
        "plaintext",
    )


async def test_wikipedia_searches_the_wiki_of_the_query_language() -> None:
    adapter, recorder = adapter_for(WikipediaAdapter, {HI_API: Reply("wikipedia_search_hi.json")})
    items = await adapter.search(SearchQuery(text="मधुबनी चित्रकला", language="hi-IN"), 2)
    assert recorder.requests[0].url.host == "hi.wikipedia.org"
    assert [item.id for item in items] == ["wikipedia:hi:1741", "wikipedia:hi:1738"]
    assert items[0].title == "मधुबनी चित्रकला"
    assert items[0].external_ids["wikidata"] == "Q2547125"
    assert items[0].published == "2024-07-20"


def test_a_language_searches_its_own_wikipedia_edition_wherever_one_exists() -> None:
    assert wiki_language("en") == "en"
    assert wiki_language("ta-IN") == "ta"
    assert wiki_language("fr-FR") == "fr"
    assert wiki_language("bho") == "bh"
    assert wiki_language("yue-HK") == "zh-yue"
    assert wiki_language("nb-NO") == "no"
    with pytest.raises(InvalidInput, match="No Wikipedia"):
        wiki_language("xx")
    with pytest.raises(InvalidInput):
        wiki_language("evil.example.com/")


async def test_a_wikipedia_id_in_another_language_is_read_from_that_edition() -> None:
    adapter, recorder = adapter_for(
        WikipediaAdapter,
        {FR_API: Reply("wikipedia_missing.json"), YUE_API: Reply("wikipedia_missing.json")},
    )
    for native in ("wikipedia:fr:1", "wikipedia:zh-yue:1"):
        with pytest.raises(ExternalFailure, match="no article"):
            await adapter.fetch(native)
    assert [request.url.host for request in recorder.requests] == ["fr.wikipedia.org", "zh-yue.wikipedia.org"]


async def test_wikipedia_no_hits_is_an_empty_list() -> None:
    adapter, _ = adapter_for(WikipediaAdapter, {EN_API: Reply("wikipedia_no_hits.json")})
    assert await adapter.search(SearchQuery(text="zzqxjkvbnmwqplk"), 3) == []


async def test_wikipedia_fetch_returns_the_article_as_plain_text() -> None:
    adapter, recorder = adapter_for(WikipediaAdapter, {EN_API: Reply("wikipedia_page.json")})
    document = await adapter.fetch("wikipedia:en:8807398")
    assert document.content == "FULL_TEXT"
    assert document.text.startswith(
        "Ajrak (Sindhi: اجرڪ; Saraiki: اجرک) is a unique form of textile block-printing"
    )
    assert document.text.endswith("Ajrak Cloth from the Soil of Sindh by Noorjehan Bilgrami")
    assert len(document.text) == 4880
    assert document.text_sha256 == hashlib.sha256(document.text.encode("utf-8")).hexdigest()
    assert document.item.licence == CC_BY_SA_4
    assert document.item.external_ids["revision"] == "1385329287"
    sent = recorder.requests[0].url.params
    assert (sent["pageids"], sent["explaintext"]) == ("8807398", "1")
    assert "extracts" in sent["prop"].split("|")


async def test_wikipedia_unknown_page_is_not_found() -> None:
    adapter, _ = adapter_for(WikipediaAdapter, {EN_API: Reply("wikipedia_missing.json")})
    with pytest.raises(ExternalFailure, match="no article") as failure:
        await adapter.fetch("wikipedia:en:1")
    assert failure.value.kind == "not_found"


async def test_wikipedia_ids_name_a_supported_wiki_and_a_page() -> None:
    adapter, _ = adapter_for(WikipediaAdapter, {})
    for bad in (
        "wikipedia:Ajrak",
        "wikipedia:xx:12",
        "wikipedia:EN:12",
        "wikipedia:fr-:12",
        "wikipedia:en:0",
        "wikipedia:en:12/../1",
    ):
        with pytest.raises(InvalidInput):
            await adapter.fetch(bad)


async def test_api_errors_inside_a_200_are_failures() -> None:
    adapter, _ = adapter_for(WikipediaAdapter, {EN_API: Reply("wikidata_entity_missing.json")})
    with pytest.raises(ExternalFailure, match="no-such-entity") as failure:
        await adapter.search(SearchQuery(text="ajrak"), 2)
    assert failure.value.kind == "not_found"


async def test_commons_search_keeps_licence_and_attribution() -> None:
    adapter, recorder = adapter_for(WikimediaCommonsAdapter, {COMMONS_API: Reply("commons_search.json")})
    items = await adapter.search(SearchQuery(text="ajrak"), 3)
    assert [item.id for item in items] == [
        "wikimedia_commons:15565262",
        "wikimedia_commons:67760143",
        "wikimedia_commons:49875448",
    ]
    ajrak = items[0]
    assert ajrak.title == "Ajrak"
    assert ajrak.url == "https://commons.wikimedia.org/wiki/File:Ajrak.jpg"
    assert ajrak.licence == "CC BY-SA 3.0"
    assert ajrak.attribution == (
        "Ahub1988, CC BY-SA 3.0 (https://creativecommons.org/licenses/by-sa/3.0), via Wikimedia Commons"
    )
    assert ajrak.authors == ["Ahub1988"]
    assert ajrak.published == "2010-05-31"
    assert (ajrak.source_type, ajrak.trust) == ("MEDIA", "C")
    assert ajrak.external_ids == {
        "commons_file": "File:Ajrak.jpg",
        "commons_media": "M15565262",
        "revision": "1272783994",
    }
    sent = recorder.requests[0].url.params
    assert (sent["gsrnamespace"], sent["iiextmetadatalanguage"]) == ("6", "en")


async def test_commons_fetch_drops_hidden_markup_and_unparseable_dates() -> None:
    adapter, _ = adapter_for(WikimediaCommonsAdapter, {COMMONS_API: Reply("commons_file.json")})
    document = await adapter.fetch("wikimedia_commons:60897367")
    assert document.content == "EXCERPT"
    assert document.text.split("\n") == [
        "Kalamkari Rumal",
        "Cover; Textiles-Painted and/or Printed",
        "Date: circa 1640–50",
        "Credit: This file was donated to Wikimedia Commons as part of a project by the Metropolitan Museum "
        "of Art. See the Image and Data Resources Open Access Policy",
        "Licence: CC0",
    ]
    item = document.item
    assert item.published is None
    assert item.licence == "CC0"
    assert item.attribution == "CC0, via Wikimedia Commons"
    assert item.authors == []
    assert item.source_type == "MEDIA"


async def test_a_scanned_document_on_commons_is_not_a_media_file() -> None:
    adapter, _ = adapter_for(WikimediaCommonsAdapter, {COMMONS_API: Reply("commons_document.json")})
    document = await adapter.fetch("wikimedia_commons:92241461")
    item = document.item
    assert (item.source_type, item.licence) == ("OTHER", "Public domain")
    assert item.title == "Journal of the Bombay Natural History Society"
    assert item.attribution == "Bombay Natural History Society, Public domain, via Wikimedia Commons"


async def test_commons_page_that_is_not_a_file_is_not_found() -> None:
    adapter, _ = adapter_for(WikimediaCommonsAdapter, {COMMONS_API: Reply("commons_not_a_file.json")})
    with pytest.raises(ExternalFailure, match="no file") as failure:
        await adapter.fetch("wikimedia_commons:5")
    assert failure.value.kind == "not_found"
