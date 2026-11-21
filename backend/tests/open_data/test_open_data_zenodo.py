import json
from dataclasses import replace
from datetime import date
from typing import Any

import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput, NotConfigured
from app.services.open_data_changes import release_changes
from app.services.open_data_deposit import ReleaseFolder, deposit_files, release_folder
from app.services.open_data_files import release_files
from app.services.open_data_zenodo import ZenodoDeposit, deposit_metadata

from .release_fixtures import SITE, STAMP, empty_tables

SANDBOX = "https://sandbox.zenodo.org"
BUCKET = f"{SANDBOX}/api/files/bucket-200"
METADATA = deposit_metadata(version="2026.11.21", released=date(2026, 11, 21), counts={}, site=SITE)


class FakeZenodo:
    def __init__(self, *, published_doi: str = "10.5072/zenodo.200", previous_files: int = 0) -> None:
        self.calls: list[tuple[str, str]] = []
        self.uploaded: dict[str, bytes] = {}
        self.described: list[dict[str, Any]] = []
        self.published_doi = published_doi
        self.previous_files = previous_files

    def __call__(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        self.calls.append((request.method, path))
        assert request.headers["Authorization"] == "Bearer sandbox-token"
        if request.method == "PUT" and path.startswith("/api/files/"):
            self.uploaded[path.rsplit("/", 1)[1]] = request.content
            return httpx.Response(201, json={})
        status, body = self._answer(request.method, path, request)
        return httpx.Response(status) if body is None else httpx.Response(status, json=body)

    def _answer(self, method: str, path: str, request: httpx.Request) -> tuple[int, Any]:
        if (method, path) == ("POST", "/api/deposit/depositions"):
            return 201, self._draft()
        if (method, path) == ("POST", "/api/deposit/depositions/150/actions/newversion"):
            return 201, {"id": 150, "links": {"latest_draft": f"{SANDBOX}/api/deposit/depositions/200"}}
        if (method, path) == ("GET", "/api/deposit/depositions/200"):
            return 200, self._draft(reserved=True)
        if method == "DELETE" and path.startswith("/api/deposit/depositions/200/files/"):
            return 204, None
        if (method, path) == ("PUT", "/api/deposit/depositions/200"):
            self.described.append(json.loads(request.content)["metadata"])
            return 200, self._draft(reserved=True)
        if (method, path) == ("POST", "/api/deposit/depositions/200/actions/publish"):
            links = {"html": f"{SANDBOX}/records/200"}
            return 202, {
                "id": 200,
                "doi": self.published_doi,
                "conceptdoi": "10.5072/zenodo.199",
                "links": links,
            }
        return 404, {"message": "not here"}

    def _draft(self, *, reserved: bool = False) -> dict[str, Any]:
        files = [{"id": f"f{n}", "filename": f"old{n}.csv"} for n in range(self.previous_files)]
        metadata = {"prereserve_doi": {"doi": "10.5072/zenodo.200", "recid": 200}} if reserved else {}
        return {
            "id": 200,
            "conceptrecid": "199",
            "files": files,
            "metadata": metadata,
            "links": {"bucket": BUCKET},
        }


def _zenodo(fake: FakeZenodo) -> ZenodoDeposit:
    return ZenodoDeposit(
        httpx.Client(transport=httpx.MockTransport(fake)), target="SANDBOX", token="sandbox-token"
    )


def test_a_first_release_opens_a_draft_and_takes_its_reserved_doi_and_concept() -> None:
    fake = FakeZenodo()
    draft = _zenodo(fake).open_draft(None, METADATA)
    assert (draft.record_id, draft.concept_record_id) == (200, 199)
    assert (draft.doi, draft.concept_doi, draft.bucket) == (
        "10.5072/zenodo.200",
        "10.5072/zenodo.199",
        BUCKET,
    )
    assert fake.calls == [("POST", "/api/deposit/depositions"), ("PUT", "/api/deposit/depositions/200")]
    assert fake.described[0]["prereserve_doi"] is True


def test_a_later_release_is_a_new_version_that_drops_the_files_it_inherits() -> None:
    fake = FakeZenodo(previous_files=2)
    draft = _zenodo(fake).open_draft(150, METADATA)
    assert draft.record_id == 200
    assert fake.calls[:4] == [
        ("POST", "/api/deposit/depositions/150/actions/newversion"),
        ("GET", "/api/deposit/depositions/200"),
        ("DELETE", "/api/deposit/depositions/200/files/f0"),
        ("DELETE", "/api/deposit/depositions/200/files/f1"),
    ]


def test_the_metadata_names_the_centre_the_licence_the_site_and_the_code() -> None:
    assert METADATA["creators"] == [
        {
            "name": "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur"
        }
    ]
    assert (METADATA["upload_type"], METADATA["license"], METADATA["version"]) == (
        "dataset",
        "cc-by-4.0",
        "2026.11.21",
    )
    related = {item["identifier"]: item["relation"] for item in METADATA["related_identifiers"]}
    assert related == {
        "https://kalavigyan.example/data": "isDocumentedBy",
        "https://github.com/cxacraftecosystem-ui/KalaVigyan": "isSupplementedBy",
    }


def _folder() -> ReleaseFolder:
    return release_folder(
        release_files(empty_tables(), STAMP, release_changes({}, None, None), site=SITE).files
    )


def test_a_deposit_uploads_every_file_describes_the_record_and_publishes_only_when_asked() -> None:
    fake = FakeZenodo()
    held = deposit_files(_zenodo(fake), _folder(), record_id=200, publish=False, site=SITE)
    assert held == {
        "recordId": 200,
        "doi": "10.5072/zenodo.200",
        "conceptDoi": "10.5072/zenodo.199",
        "published": False,
    }
    assert set(fake.uploaded) == set(_folder().files)
    assert ("POST", "/api/deposit/depositions/200/actions/publish") not in fake.calls
    assert "<li>Facts (claims): 0</li>" in fake.described[-1]["description"]
    published = deposit_files(_zenodo(fake), _folder(), record_id=200, publish=True, site=SITE)
    assert published["published"] is True
    assert published["recordUrl"] == f"{SANDBOX}/records/200"


def test_a_deposit_refuses_files_built_for_another_draft_or_a_doi_zenodo_did_not_keep() -> None:
    elsewhere = replace(_folder(), doi="10.5072/zenodo.9")
    with pytest.raises(InvalidInput, match="reserved"):
        deposit_files(_zenodo(FakeZenodo()), elsewhere, record_id=200, publish=False, site=SITE)
    moved = FakeZenodo(published_doi="10.5072/zenodo.201")
    with pytest.raises(ExternalFailure, match="not the reserved DOI"):
        deposit_files(_zenodo(moved), _folder(), record_id=200, publish=True, site=SITE)


def test_no_token_means_nothing_is_sent() -> None:
    with pytest.raises(NotConfigured, match="ZENODO_TOKEN"):
        ZenodoDeposit(httpx.Client(), target="ZENODO", token="")


def test_a_refusal_names_the_status_and_never_the_token() -> None:
    fake = FakeZenodo()
    with pytest.raises(ExternalFailure) as refused:
        _zenodo(fake).draft(999)
    assert refused.value.status == 404
    assert "sandbox-token" not in str(refused.value)
