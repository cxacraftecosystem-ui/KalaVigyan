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
    assert golden_json(GOLDEN)["craftReleases"][0]["craft"] == "Kutch-Ajrakh"


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


def _craft_release() -> OpenDataRelease:
    return OpenDataRelease(
        target="ZENODO",
        scope="Kutch-Ajrakh",
        version="2026.11.22",
        releasedOn=date(2026, 11, 22),
        state="PUBLISHED",
        doi="10.5281/zenodo.400",
        conceptDoi="10.5281/zenodo.399",
        recordId=400,
        conceptRecordId=399,
        recordUrl="https://zenodo.org/records/400",
        files=[{"path": "claims.jsonl", "bytes": 40960, "sha256": "c" * 64}],
        counts={"claims": 3},
        changes={},
        rowDigests={},
        totalBytes=40960,
        manifestSha256="d" * 64,
        publishedAt=datetime(2026, 11, 22, 10, tzinfo=UTC),
    )


def test_a_craft_release_is_listed_apart_by_its_craft_with_both_dois_and_its_own_citation() -> None:
    listing = listing_of(
        [_published()], site=SITE, crafts=[_craft_release()], names={"Kutch-Ajrakh": "Kutch Ajrakh"}
    )
    assert [release.version for release in listing.releases] == ["2026.11.21"]
    assert listing.concept_doi == "10.5281/zenodo.299"
    (craft,) = listing.craft_releases
    assert (craft.craft, craft.craft_name, craft.title) == (
        "Kutch-Ajrakh",
        "Kutch Ajrakh",
        "Kutch Ajrakh: KalaVigyan open knowledge",
    )
    assert (craft.doi_url, craft.concept_doi_url) == (
        "https://doi.org/10.5281/zenodo.400",
        "https://doi.org/10.5281/zenodo.399",
    )
    assert craft.citation == (
        f"{CREATOR}. (2026). Kutch Ajrakh: KalaVigyan open knowledge (Version 2026.11.22) [Data set]. Zenodo. "
        "https://doi.org/10.5281/zenodo.400"
    )
    assert craft.bibtex.startswith("@misc{kalavigyan_kutch_ajrakh_2026_11_22,\n")
    assert craft.files[0].download_url == "https://zenodo.org/records/400/files/claims.jsonl?download=1"
    dumped = listing.model_dump(mode="json", by_alias=True)
    assert dumped["schemaVersion"] == 1 and dumped["craftReleases"][0]["craftName"] == "Kutch Ajrakh"


def test_a_craft_release_whose_name_is_unknown_is_named_by_its_slug() -> None:
    (craft,) = listing_of([], site=SITE, crafts=[_craft_release()]).craft_releases
    assert (craft.craft_name, craft.title) == ("Kutch-Ajrakh", "Kutch-Ajrakh: KalaVigyan open knowledge")


def test_before_the_first_release_the_listing_cites_the_dataset_page() -> None:
    listing = listing_of([], site=f"{SITE}/")
    assert (listing.latest, listing.concept_doi, listing.releases, listing.craft_releases) == (
        None,
        None,
        [],
        [],
    )
    assert listing.page_url == f"{SITE}/data"
    assert listing.citation == f"{CREATOR}. KalaVigyan open knowledge [Data set]. {SITE}/data"
    assert listing.bibtex.startswith("@misc{kalavigyan_open_knowledge,\n")
