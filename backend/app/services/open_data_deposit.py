from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.errors import InvalidInput

from .open_data_descriptor import PACKAGE_FILE, jsonl_file
from .open_data_files import manifest_text
from .open_data_readme import MANIFEST_FILE
from .open_data_release import released_on
from .open_data_tables import TABLES
from .open_data_zenodo import ZenodoDeposit, deposit_metadata

__all__ = ["ReleaseFolder", "deposit_files", "read_release_folder", "release_folder"]

DOI_PREFIX = "https://doi.org/"
NO_MANIFEST = "The release folder holds no {name}; build the release again."
BAD_MANIFEST = "The release files do not match {name}; build the release again and copy every file."
MISSING_FILE = "The release folder lacks {name}; build the release again and copy every file."
OTHER_DRAFT = "The release files name the DOI {built}, but draft {record} reserved {reserved}."


@dataclass(frozen=True)
class ReleaseFolder:
    files: Mapping[str, bytes]
    version: str
    doi: str
    counts: dict[str, int]


def read_release_folder(folder: Path) -> ReleaseFolder:
    return release_folder(
        {path.name: path.read_bytes() for path in sorted(folder.iterdir()) if path.is_file()}
    )


def release_folder(files: Mapping[str, bytes]) -> ReleaseFolder:
    if MANIFEST_FILE not in files:
        raise InvalidInput(NO_MANIFEST.format(name=MANIFEST_FILE))
    if manifest_text(files) != files[MANIFEST_FILE].decode("utf-8"):
        raise InvalidInput(BAD_MANIFEST.format(name=MANIFEST_FILE))
    wanted = [PACKAGE_FILE, *(jsonl_file(table) for table in TABLES)]
    missing = [name for name in wanted if name not in files]
    if missing:
        raise InvalidInput(MISSING_FILE.format(name=", ".join(missing)))
    descriptor = json.loads(files[PACKAGE_FILE])
    version = str(descriptor["version"])
    released_on(version)
    return ReleaseFolder(
        files=dict(files),
        version=version,
        doi=str(descriptor["id"]).removeprefix(DOI_PREFIX),
        counts={table.name: files[jsonl_file(table)].count(b"\n") for table in TABLES},
    )


def deposit_files(
    zenodo: ZenodoDeposit, folder: ReleaseFolder, *, record_id: int, publish: bool, site: str
) -> dict[str, Any]:
    draft = zenodo.draft(record_id)
    if draft.doi != folder.doi:
        raise InvalidInput(OTHER_DRAFT.format(built=folder.doi, record=record_id, reserved=draft.doi))
    zenodo.upload(draft, folder.files)
    zenodo.describe(
        draft,
        deposit_metadata(
            version=folder.version, released=released_on(folder.version), counts=folder.counts, site=site
        ),
    )
    result: dict[str, Any] = {"recordId": draft.record_id, "doi": draft.doi, "conceptDoi": draft.concept_doi}
    if not publish:
        return {**result, "published": False}
    published = zenodo.publish(draft)
    return {
        **result,
        "published": True,
        "conceptDoi": published.concept_doi,
        "recordUrl": published.record_url,
        "publishedAt": datetime.now(UTC).isoformat(),
    }
