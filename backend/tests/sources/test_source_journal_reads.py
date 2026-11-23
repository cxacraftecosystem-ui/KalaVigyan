import uuid

from app.core.errors import ExternalFailure
from app.services.source_journals import JournalRead, StoredDoi, journal_reads
from app.sources.scholarly.crossref import CrossrefAdapter

from .recorded import CONTACT, Reply
from .test_scholarly_adapters import adapter_for

IJSREM = "INTERNATIONAL JOURNAL OF SCIENTIFIC RESEARCH IN ENGINEERING AND MANAGEMENT"
FOUND = StoredDoi(uuid.UUID(int=1), "10.55041/ijsrem46137")
MISSING = StoredDoi(uuid.UUID(int=2), "10.9999/missing")


async def test_crossref_reads_a_stored_doi_s_journal_from_its_work_record() -> None:
    adapter, recorder = adapter_for(
        CrossrefAdapter,
        {
            "api.crossref.org/works/10.55041/ijsrem46137": Reply("crossref_work.json"),
            "api.crossref.org/works/10.9999/missing": Reply("crossref_missing.txt", status=404),
        },
        contact_email=CONTACT,
    )
    reads = await journal_reads([FOUND, MISSING], adapter.container_title)
    assert reads[0] == JournalRead(FOUND.id, FOUND.doi, IJSREM)
    assert (reads[1].journal, reads[1].problem is not None) == (None, True)
    assert recorder.requests[0].url.params["mailto"] == CONTACT


async def test_a_failed_lookup_is_reported_and_the_next_is_still_read() -> None:
    async def lookup(doi: str) -> str | None:
        if doi == MISSING.doi:
            raise ExternalFailure("crossref answered 404", kind="not_found", service="crossref")
        return "Dyes and Pigments"

    reads = await journal_reads([MISSING, FOUND], lookup)
    assert [(read.journal, read.problem) for read in reads] == [
        (None, "crossref answered 404"),
        ("Dyes and Pigments", None),
    ]
