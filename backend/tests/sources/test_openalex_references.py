from app.research.evidence import EvidenceItem, ReferenceLister
from app.sources.scholarly.openalex import OpenAlexAdapter

from .recorded import CONTACT, Recorder, Reply, fixed_clock, source_http

WORK = "api.openalex.org/works/W2625322139"
WORKS = "api.openalex.org/works"
MOST_CITED_WITH_ABSTRACTS = [
    "openalex:W587291236",
    "openalex:W1977865695",
    "openalex:W2017409477",
    "openalex:W2061113524",
    "openalex:W2026402964",
]


def adapter(routes: dict[str, Reply]) -> tuple[OpenAlexAdapter, Recorder]:
    recorder = Recorder(routes)
    built = OpenAlexAdapter(source_http(recorder, "openalex"), contact_email=CONTACT, clock=fixed_clock())
    return built, recorder


async def test_a_work_s_reference_list_is_read_in_one_call_most_cited_first_with_abstracts() -> None:
    openalex, recorder = adapter(
        {WORK: Reply("openalex_work.json"), WORKS: Reply("openalex_references.json")}
    )
    parent = (await openalex.fetch("openalex:W2625322139")).item
    assert isinstance(openalex, ReferenceLister) and openalex.lists(parent)
    documents = await openalex.references(parent, 5)
    assert [document.item.id for document in documents] == MOST_CITED_WITH_ABSTRACTS
    assert {document.content for document in documents} == {"ABSTRACT"}
    assert documents[0].item.url == "https://openalex.org/W587291236" and documents[0].item.doi is None
    assert documents[2].item.source_key == "doi:10.1111/j.1478-4408.2004.tb00223.x"
    sent = recorder.requests[-1].url.params
    assert (sent["filter"], sent["sort"], sent["per-page"], sent["mailto"]) == (
        "cited_by:W2625322139,has_abstract:true",
        "cited_by_count:desc",
        "5",
        CONTACT,
    )
    assert "abstract_inverted_index" in sent["select"]


async def test_an_item_without_an_openalex_id_lists_nothing_and_calls_nothing() -> None:
    openalex, recorder = adapter({})
    page = (await _parent()).model_copy(update={"external_ids": {}})
    assert not openalex.lists(page)
    assert await openalex.references(page, 5) == [] and recorder.requests == []


async def _parent() -> EvidenceItem:
    openalex, _ = adapter({WORK: Reply("openalex_work.json")})
    return (await openalex.fetch("openalex:W2625322139")).item
