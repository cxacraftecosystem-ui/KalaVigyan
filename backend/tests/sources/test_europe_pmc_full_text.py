import pytest

from app.core.errors import ExternalFailure
from app.services.live_source_store import chunk_acl
from app.sources.scholarly.europe_pmc import EuropePmcAdapter

from .recorded import Recorder, Reply, fixed_clock, source_http

SEARCH = "www.ebi.ac.uk/europepmc/webservices/rest/search"
FULL_TEXT = "www.ebi.ac.uk/europepmc/webservices/rest/PMC12834052/fullTextXML"
OPEN_RECORD = "europe_pmc:MED:41602741"
FIRST_PARAGRAPH = (
    "Tyrian purple, a reddish-purple dye, has been used for millennia to create vibrant, purple-colored "
    "textiles [1]. This coveted dye was produced in small quantities using large numbers of sea snails found "
    "in the eastern Mediterranean Sea. The relative rarity and expense of the dye resulted in purple clothing "
    "being associated with wealth and power [1–2]. More modern analysis indicates that Tyrian purple is "
    "composed of several different indigoids, with the predominant being 6,6’-dibromoindigo (1) [3–4]."
)
LAST_PARAGRAPHS = [
    "Experimental procedures, characterization data and copies of spectra.",
    "Data Availability Statement",
    "Data generated and analyzed during this study is available from the corresponding author upon "
    "reasonable request.",
]


def adapter(routes: dict) -> tuple[EuropePmcAdapter, Recorder]:
    recorder = Recorder(routes)
    return EuropePmcAdapter(source_http(recorder, "europe_pmc"), clock=fixed_clock()), recorder


def open_record(full_text: Reply) -> tuple[EuropePmcAdapter, Recorder]:
    return adapter({SEARCH: Reply("europe_pmc_open_record.json"), FULL_TEXT: full_text})


async def test_an_open_access_record_is_read_in_full_after_its_abstract() -> None:
    reader, recorder = open_record(Reply("europe_pmc_full_text.xml"))
    document = await reader.fetch(OPEN_RECORD)
    paragraphs = document.text.split("\n\n")
    assert document.content == "FULL_TEXT"
    assert paragraphs[0].startswith("6,6'-Dibromoindigo is the major component of a historic pigment")
    assert "in four steps from p-bromotoluene in 14.5% overall yield" in paragraphs[0]
    assert paragraphs[1:3] == ["Introduction", FIRST_PARAGRAPH]
    assert paragraphs[-3:] == LAST_PARAGRAPHS
    assert "pKa Values and λmax values for sulfonated indigo and 6,6’-dibromoindigo species." in paragraphs
    assert "ε (M−1cm−1)" not in document.text
    assert "Cooksey C. Sci Prog. 2013" not in document.text
    assert recorder.requests[1].url.path == "/europepmc/webservices/rest/PMC12834052/fullTextXML"


async def test_full_text_under_cc_by_is_public() -> None:
    reader, _ = open_record(Reply("europe_pmc_full_text.xml"))
    document = await reader.fetch(OPEN_RECORD)
    assert document.item.licence == "cc by"
    assert chunk_acl(document) == "PUBLIC"


@pytest.mark.parametrize("status", [404, 500])
async def test_an_open_access_record_whose_full_text_is_not_served_is_read_by_its_abstract(
    status: int,
) -> None:
    reader, _ = open_record(Reply("europe_pmc_full_text_missing.json", status=status))
    document = await reader.fetch(OPEN_RECORD)
    assert document.content == "ABSTRACT"
    assert document.text.endswith("producing water-soluble derivatives of this historically relevant dye.")


async def test_any_other_full_text_failure_is_not_hidden() -> None:
    reader, _ = open_record(Reply("europe_pmc_full_text_missing.json", status=503))
    with pytest.raises(ExternalFailure) as failed:
        await reader.fetch(OPEN_RECORD)
    assert failed.value.kind == "unavailable"


async def test_a_record_that_is_not_open_access_is_never_asked_for_full_text() -> None:
    reader, recorder = adapter({SEARCH: Reply("europe_pmc_closed_record.json")})
    document = await reader.fetch("europe_pmc:MED:41889078")
    assert document.content == "ABSTRACT"
    assert document.text.startswith("Phosphorus (P) deficiency in aquacultured fish has become increasingly")
    assert document.text.endswith(
        "may serve as a sensitive diagnostic indicator of P deficiency in farmed fish."
    )
    assert len(recorder.requests) == 1
