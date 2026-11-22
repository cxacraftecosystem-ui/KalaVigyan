import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.research.evidence import EvidenceItem
from app.services.live_source_store import chunk_acl
from app.sources.scholarly.elsevier import ElsevierFullText
from app.sources.scholarly.open_copies import OpenCopyLocator
from app.sources.scholarly.publishers import PublisherFullText
from app.sources.scholarly.registry import ScholarlyKeys, scholarly_sources
from app.sources.scholarly.springer_nature import SpringerNatureFullText
from app.sources.scholarly.unpaywall import UnpaywallLocator

from .recorded import CONTACT, RETRIEVED, Recorder, Reply, fixed_clock, source_http

ELSEVIER_DOI = "10.1016/j.dyepig.2026.114301"
SPRINGER_DOI = "10.1007/s00000-026-00001-1"
OPEN_DOI = "10.1038/s41598-022-27110-0"
UNPAYWALL = "api.unpaywall.org/v2/"
ELSEVIER_ARTICLE = f"api.elsevier.com/content/article/doi/{ELSEVIER_DOI}"
SPRINGER_JATS = "api.springernature.com/xmldata/jats"
ELSEVIER_TEXT = (
    "A synthetic abstract standing in for a recorded Elsevier response.\n\n"
    "Introduction\n\n"
    "Synthetic Elsevier paragraph one, with a cross reference [1].\n\n"
    "Synthetic Elsevier paragraph two."
)
SPRINGER_TEXT = (
    "Abstract\n\n"
    "A synthetic Springer Nature abstract.\n\n"
    "Background\n\n"
    "Synthetic Springer Nature paragraph one.\n\n"
    "A synthetic figure caption."
)


def paper(doi: str | None) -> EvidenceItem:
    return EvidenceItem(
        id=f"crossref:{doi or 'none'}",
        adapter="crossref",
        tier="T3",
        source_type="PAPER",
        url=f"https://doi.org/{doi or '10.1000/none'}",
        title="A synthetic paper",
        retrieved_at=RETRIEVED,
        doi=doi,
        trust="A",
        external_ids={"crossref": doi or "none"},
    )


def publisher(routes: dict) -> tuple[PublisherFullText, Recorder]:
    recorder = Recorder(routes)
    unpaywall = UnpaywallLocator(
        source_http(recorder, "unpaywall"), contact_email=CONTACT, clock=fixed_clock()
    )
    readers = [
        ElsevierFullText(source_http(recorder, "elsevier"), api_key="els-key", insttoken="els-token"),
        SpringerNatureFullText(source_http(recorder, "springer_nature"), api_key="sn-key"),
    ]
    return PublisherFullText(unpaywall, readers), recorder


async def test_elsevier_full_text_of_a_closed_doi_is_read_with_key_and_institution_token() -> None:
    reader, recorder = publisher(
        {
            f"{UNPAYWALL}{ELSEVIER_DOI}": Reply("unpaywall_closed.json"),
            ELSEVIER_ARTICLE: Reply("elsevier_article.synthetic.xml"),
        }
    )
    document = await reader.read(paper(ELSEVIER_DOI))
    assert (document.content, document.text) == ("FULL_TEXT", ELSEVIER_TEXT)
    assert document.item.id == f"crossref:{ELSEVIER_DOI}"
    assert document.item.licence == "https://www.elsevier.com/tdm/userlicense/1.0/"
    assert document.item.external_ids["full_text_from"] == "elsevier"
    sent = recorder.requests[1]
    assert sent.url.path == f"/content/article/doi/{ELSEVIER_DOI}"
    assert sent.url.params["view"] == "FULL"
    assert (sent.headers["X-ELS-APIKey"], sent.headers["X-ELS-Insttoken"]) == ("els-key", "els-token")
    assert sent.headers["Accept"] == "text/xml"


async def test_publisher_full_text_under_a_text_mining_licence_is_kept_for_researchers() -> None:
    reader, _ = publisher(
        {
            f"{UNPAYWALL}{ELSEVIER_DOI}": Reply("unpaywall_closed.json"),
            ELSEVIER_ARTICLE: Reply("elsevier_article.synthetic.xml"),
        }
    )
    assert chunk_acl(await reader.read(paper(ELSEVIER_DOI))) == "RESEARCHER"


async def test_springer_nature_jats_full_text_of_a_closed_doi_is_read() -> None:
    reader, recorder = publisher(
        {
            f"{UNPAYWALL}{SPRINGER_DOI}": Reply("unpaywall_closed.json"),
            SPRINGER_JATS: Reply("springer_nature_jats.synthetic.xml"),
        }
    )
    document = await reader.read(paper(SPRINGER_DOI))
    assert (document.content, document.text) == ("FULL_TEXT", SPRINGER_TEXT)
    assert document.item.licence == "https://www.springernature.com/gp/researchers/text-and-data-mining"
    assert document.item.external_ids["full_text_from"] == "springer_nature"
    assert chunk_acl(document) == "RESEARCHER"
    sent = recorder.requests[1].url.params
    assert (sent["q"], sent["p"], sent["api_key"]) == (f"doi:{SPRINGER_DOI}", "1", "sn-key")


async def test_a_doi_unpaywall_reports_open_is_never_asked_of_a_publisher() -> None:
    reader, recorder = publisher({f"{UNPAYWALL}{OPEN_DOI}": Reply("unpaywall_open.json")})
    with pytest.raises(ExternalFailure, match="open copy") as refused:
        await reader.read(paper(OPEN_DOI))
    assert refused.value.kind == "not_found"
    assert [request.url.host for request in recorder.requests] == ["api.unpaywall.org"]


async def test_a_doi_no_configured_publisher_holds_asks_nothing() -> None:
    reader, recorder = publisher({})
    assert [reader.holds(doi) for doi in (ELSEVIER_DOI, "10.1038/X", "10.1111/cote.12288")] == [
        True,
        True,
        False,
    ]
    with pytest.raises(ExternalFailure, match="no publisher") as missing:
        await reader.read(paper("10.1111/cote.12288"))
    assert missing.value.kind == "not_found"
    assert recorder.requests == []
    with pytest.raises(InvalidInput):
        await reader.read(paper(None))


async def test_a_publisher_answer_without_full_text_is_not_found() -> None:
    reader, _ = publisher(
        {
            f"{UNPAYWALL}10.1007/s00000-026-00002-2": Reply("unpaywall_closed.json"),
            SPRINGER_JATS: Reply("springer_nature_jats_none.synthetic.xml"),
        }
    )
    with pytest.raises(ExternalFailure) as missing:
        await reader.read(paper("10.1007/s00000-026-00002-2"))
    assert missing.value.kind == "not_found"


async def test_an_elsevier_refusal_without_entitlement_is_an_auth_failure() -> None:
    reader, _ = publisher(
        {
            f"{UNPAYWALL}{ELSEVIER_DOI}": Reply("unpaywall_closed.json"),
            ELSEVIER_ARTICLE: Reply("elsevier_view_refused.json", status=403),
        }
    )
    with pytest.raises(ExternalFailure) as refused:
        await reader.read(paper(ELSEVIER_DOI))
    assert refused.value.kind == "auth"


def test_publisher_readers_need_their_keys() -> None:
    http = source_http(Recorder({}), "elsevier")
    with pytest.raises(ValueError, match="ELSEVIER_INSTTOKEN"):
        ElsevierFullText(http, api_key="els-key", insttoken="")
    with pytest.raises(ValueError, match="SPRINGER_NATURE_API_KEY"):
        SpringerNatureFullText(http, api_key="")
    with pytest.raises(ValueError):
        PublisherFullText(UnpaywallLocator(http, contact_email=CONTACT), [])


@pytest.mark.parametrize(
    ("keys", "publishers"),
    [
        ({}, None),
        ({"elsevier_api_key": "e", "springer_nature_api_key": "s"}, ("springer_nature",)),
        ({"elsevier_api_key": "e", "elsevier_insttoken": "t"}, ("elsevier",)),
        (
            {"elsevier_api_key": "e", "elsevier_insttoken": "t", "springer_nature_api_key": "s"},
            ("elsevier", "springer_nature"),
        ),
    ],
)
def test_publisher_full_text_is_built_only_for_the_keys_that_are_set(
    keys: dict[str, str], publishers: tuple[str, ...] | None
) -> None:
    sources = scholarly_sources(ScholarlyKeys(contact_email=CONTACT, **keys), Recorder({}).client())
    assert isinstance(sources.locator, OpenCopyLocator)
    found = None if sources.publisher is None else sources.publisher.publishers
    assert found == publishers
