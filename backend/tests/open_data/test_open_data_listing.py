from datetime import UTC, date, datetime

from app.models import OpenDataRelease
from app.services.open_data_listing import OpenDataListing, listing_of

from ..contracts.golden import golden_json, reproduces

GOLDEN = "open-data.golden.json"
SITE = "https://kalavigyan.example"
CREATOR = "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur"


def _published() -> OpenDataRelease:
    return OpenDataRelease(
        target="ZENODO",
        version="2026.11.21",
        releasedOn=date(2026, 11, 21),
        state="PUBLISHED",
        doi="10.5281/zenodo.300",
        conceptDoi="10.5281/zenodo.299",
        recordId=300,
        conceptRecordId=299,
        recordUrl="https://zenodo.org/records/300/",
        files=[{"path": "claims.jsonl", "bytes": 734003, "sha256": "a" * 64}],
        counts={"claims": 2},
        changes={"claims": {"added": 2, "removed": 0, "changed": 0}},
        rowDigests={"claims": {"x": "y"}},
        totalBytes=734003,
        manifestSha256="b" * 64,
        publishedAt=datetime(2026, 11, 21, 10, tzinfo=UTC),
    )


def test_the_golden_the_web_client_reads_is_the_listing_model_byte_for_byte() -> None:
    assert reproduces(OpenDataListing, GOLDEN)
    assert golden_json(GOLDEN)["latest"]["files"][1]["downloadUrl"].endswith("/files/claims.jsonl?download=1")


def test_a_listing_links_each_file_and_cites_the_newest_version_and_every_version() -> None:
    listing = listing_of([_published()], site=SITE)
    assert listing.latest is not None
    assert listing.concept_doi_url == "https://doi.org/10.5281/zenodo.299"
    assert (
        listing.latest.files[0].download_url == "https://zenodo.org/records/300/files/claims.jsonl?download=1"
    )
    assert listing.citation == (
        f"{CREATOR}. (2026). KalaVigyan open knowledge (Version 2026.11.21) [Data set]. Zenodo. "
        "https://doi.org/10.5281/zenodo.300"
    )
    assert len(listing.tables) == 14
    assert "rowDigests" not in listing.model_dump_json(by_alias=True)


def test_before_the_first_release_the_listing_cites_the_dataset_page() -> None:
    listing = listing_of([], site=f"{SITE}/")
    assert (listing.latest, listing.concept_doi, listing.releases) == (None, None, [])
    assert listing.page_url == f"{SITE}/data"
    assert listing.citation == f"{CREATOR}. KalaVigyan open knowledge [Data set]. {SITE}/data"
    assert listing.bibtex.startswith("@misc{kalavigyan_open_knowledge,\n")
