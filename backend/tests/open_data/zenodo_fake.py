import json
from typing import Any

import httpx

from app.services.open_data_zenodo import ZenodoDeposit

__all__ = ["BUCKET", "SANDBOX", "FakeZenodo", "fake_deposit"]

SANDBOX = "https://sandbox.zenodo.org"
BUCKET = f"{SANDBOX}/api/files/bucket-200"


class FakeZenodo:
    def __init__(
        self,
        *,
        published_doi: str = "10.5072/zenodo.200",
        previous_files: int = 0,
        reserved_doi: str = "10.5281/zenodo.200",
        inherited_title: str | None = None,
    ) -> None:
        self.reserved_doi = reserved_doi
        self.calls: list[tuple[str, str]] = []
        self.uploaded: dict[str, bytes] = {}
        self.described: list[dict[str, Any]] = []
        self.published_doi = published_doi
        self.previous_files = previous_files
        self.inherited_title = inherited_title

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
        metadata: dict[str, Any] = (
            {"prereserve_doi": {"doi": self.reserved_doi, "recid": 200}} if reserved else {}
        )
        if self.inherited_title is not None:
            metadata["title"] = self.inherited_title
        return {
            "id": 200,
            "conceptrecid": "199",
            "files": files,
            "metadata": metadata,
            "links": {"bucket": BUCKET},
        }


def fake_deposit(fake: FakeZenodo) -> ZenodoDeposit:
    return ZenodoDeposit(
        httpx.Client(transport=httpx.MockTransport(fake)), target="SANDBOX", token="sandbox-token"
    )
