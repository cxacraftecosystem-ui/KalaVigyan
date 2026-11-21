from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any
from urllib.parse import quote

import httpx

from app.core.errors import ExternalFailure, NotConfigured

from .open_data_release import SANDBOX, ZENODO, checked_doi, checked_target
from .open_data_text import CODE_URL, CREATOR, DATASET_TITLE, KEYWORDS, SUMMARY, data_page, zenodo_description

__all__ = [
    "DEPOSITIONS",
    "ZENODO_HOSTS",
    "ZENODO_LICENCE",
    "Draft",
    "Published",
    "ZenodoDeposit",
    "deposit_metadata",
]

ZENODO_HOSTS: Mapping[str, str] = {SANDBOX: "https://sandbox.zenodo.org", ZENODO: "https://zenodo.org"}
DEPOSITIONS = "/api/deposit/depositions"
ZENODO_LICENCE = "cc-by-4.0"
SERVICE = "zenodo"
NO_TOKEN = (
    "Set ZENODO_TOKEN to a Zenodo personal access token with the deposit:write and deposit:actions scopes."
)
REFUSED = "Zenodo answered {status} to {method} {path}: {detail}"
UNREACHABLE = "Zenodo could not be reached for {method} {path}: {kind}"
NO_DRAFT = "Zenodo opened no draft of a new version of record {record}."
NO_DOI = "Zenodo reserved no DOI for draft {record}."
OTHER_DOI = "Zenodo published {published}, not the reserved DOI {reserved} the files name."


@dataclass(frozen=True)
class Draft:
    record_id: int
    concept_record_id: int
    doi: str
    concept_doi: str
    bucket: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Published:
    doi: str
    concept_doi: str
    record_url: str


class ZenodoDeposit:
    def __init__(self, client: httpx.Client, *, target: str, token: str) -> None:
        if not token:
            raise NotConfigured(SERVICE, NO_TOKEN)
        self._client = client
        self._base = ZENODO_HOSTS[checked_target(target)]
        self._headers = {"Authorization": f"Bearer {token}"}

    def open_draft(self, latest_record: int | None, metadata: Mapping[str, Any]) -> Draft:
        opened = (
            self._call("POST", DEPOSITIONS, json={})
            if latest_record is None
            else self._new_version(latest_record)
        )
        for found in opened.get("files") or []:
            self._call("DELETE", f"{DEPOSITIONS}/{opened['id']}/files/{found['id']}")
        described = self._call("PUT", f"{DEPOSITIONS}/{opened['id']}", json={"metadata": dict(metadata)})
        return _draft({**opened, "metadata": described.get("metadata") or {}})

    def draft(self, record_id: int) -> Draft:
        return _draft(self._call("GET", f"{DEPOSITIONS}/{record_id}"))

    def upload(self, draft: Draft, files: Mapping[str, bytes]) -> None:
        for name, body in sorted(files.items()):
            self._call(
                "PUT",
                f"{draft.bucket}/{quote(name)}",
                content=body,
                headers={"Content-Type": "application/octet-stream"},
            )

    def describe(self, draft: Draft, metadata: Mapping[str, Any]) -> None:
        self._call("PUT", f"{DEPOSITIONS}/{draft.record_id}", json={"metadata": dict(metadata)})

    def publish(self, draft: Draft) -> Published:
        body = self._call("POST", f"{DEPOSITIONS}/{draft.record_id}/actions/publish")
        published = str(body.get("doi") or "")
        if published != draft.doi:
            raise ExternalFailure(OTHER_DOI.format(published=published, reserved=draft.doi), service=SERVICE)
        links = body.get("links") or {}
        return Published(
            doi=published,
            concept_doi=str(body.get("conceptdoi") or draft.concept_doi),
            record_url=str(links.get("html") or f"{self._base}/records/{draft.record_id}"),
        )

    def _new_version(self, record_id: int) -> dict[str, Any]:
        path = f"{DEPOSITIONS}/{record_id}"
        try:
            body = self._call("POST", f"{path}/actions/newversion")
        except ExternalFailure as refused:
            if refused.status not in (400, 409):
                raise
            body = self._call("GET", path)
        draft = (body.get("links") or {}).get("latest_draft")
        if not draft or str(draft).rstrip("/").endswith(f"/{record_id}"):
            raise ExternalFailure(NO_DRAFT.format(record=record_id), service=SERVICE)
        return self._call("GET", str(draft))

    def _call(self, method: str, path: str, **sent: Any) -> dict[str, Any]:
        url = path if path.startswith("https://") else f"{self._base}{path}"
        headers = {**self._headers, **sent.pop("headers", {})}
        shown = url.removeprefix(self._base)
        try:
            response = self._client.request(method, url, headers=headers, **sent)
        except httpx.HTTPError as failed:
            raise ExternalFailure(
                UNREACHABLE.format(method=method, path=shown, kind=type(failed).__name__),
                kind="unavailable",
                retryable=True,
                service=SERVICE,
            ) from failed
        if response.status_code >= 400:
            raise ExternalFailure(
                REFUSED.format(
                    method=method, path=shown, status=response.status_code, detail=response.text[:300]
                ),
                status=response.status_code,
                service=SERVICE,
            )
        return response.json() if response.content else {}


def deposit_metadata(*, version: str, released: date, counts: Mapping[str, int], site: str) -> dict[str, Any]:
    return {
        "upload_type": "dataset",
        "title": DATASET_TITLE,
        "publication_date": released.isoformat(),
        "version": version,
        "creators": [{"name": CREATOR}],
        "description": zenodo_description(counts) if counts else f"<p>{SUMMARY}</p>",
        "keywords": list(KEYWORDS),
        "license": ZENODO_LICENCE,
        "access_right": "open",
        "language": "eng",
        "prereserve_doi": True,
        "related_identifiers": [
            {"identifier": data_page(site), "relation": "isDocumentedBy", "resource_type": "other"},
            {"identifier": CODE_URL, "relation": "isSupplementedBy", "resource_type": "software"},
        ],
    }


def _draft(body: Mapping[str, Any]) -> Draft:
    record = int(body["id"])
    reserved = ((body.get("metadata") or {}).get("prereserve_doi") or {}).get("doi")
    if not reserved:
        raise ExternalFailure(NO_DOI.format(record=record), service=SERVICE)
    doi = checked_doi(str(reserved))
    concept = int(body.get("conceptrecid") or record)
    prefix = doi.split("/", 1)[0]
    bucket = str((body.get("links") or {}).get("bucket") or "")
    if not bucket.startswith("https://"):
        raise ExternalFailure(f"Zenodo gave draft {record} no file bucket.", service=SERVICE)
    return Draft(
        record_id=record,
        concept_record_id=concept,
        doi=doi,
        concept_doi=f"{prefix}/zenodo.{concept}",
        bucket=bucket,
    )
