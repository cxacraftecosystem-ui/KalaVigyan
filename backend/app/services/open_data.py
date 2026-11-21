from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import ColumnElement, Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer

from app.core.errors import InvalidInput
from app.models import OpenDataRelease

from .open_data_changes import ReleaseChanges, release_changes, row_digests
from .open_data_files import ReleaseFiles, release_files
from .open_data_release import ReleaseStamp, checked_doi, checked_target, released_on
from .open_data_rows import read_tables

__all__ = [
    "DRAFT",
    "PUBLISHED",
    "BuiltRelease",
    "Publication",
    "build_release",
    "latest_release",
    "published_releases",
    "record_release",
]

DRAFT = "DRAFT"
PUBLISHED = "PUBLISHED"
ALREADY_PUBLISHED = (
    "Version {version} is published on {target} already; give the next version, such as {version}.2."
)
NOT_BUILT = "No release {version} was built for {target}; build it before recording it."
OTHER_DOI = "Release {version} was built with the DOI {built}, not {given}."
PUBLISHED_ELSEWHERE = "Release {version} was recorded already at {url}."


@dataclass(frozen=True)
class BuiltRelease:
    stamp: ReleaseStamp
    files: ReleaseFiles
    counts: dict[str, int]
    changes: ReleaseChanges

    def summary(self) -> dict[str, Any]:
        return {
            "target": self.stamp.target,
            "version": self.stamp.version,
            "doi": self.stamp.doi,
            "conceptDoi": self.stamp.concept_doi,
            "previous": self.changes.previous,
            "counts": self.counts,
            "changes": self.changes.counts(),
            "files": self.files.facts(),
            "totalBytes": self.files.total_bytes(),
        }


@dataclass(frozen=True)
class Publication:
    target: str
    version: str
    doi: str
    record_url: str
    published_at: datetime

    def __post_init__(self) -> None:
        checked_target(self.target)
        released_on(self.version)
        checked_doi(self.doi)
        if not self.record_url.startswith("https://"):
            raise InvalidInput("A Zenodo record address starts with https://.")
        if self.published_at.tzinfo is None:
            raise InvalidInput("The publication time names its time zone, as 2026-11-21T10:00:00+00:00.")


async def build_release(session: AsyncSession, stamp: ReleaseStamp, *, site: str) -> BuiltRelease:
    existing = await _release(session, stamp.target, stamp.version)
    if existing is not None and existing.state == PUBLISHED:
        raise InvalidInput(ALREADY_PUBLISHED.format(version=stamp.version, target=stamp.target))
    tables = await read_tables(session, site=site)
    digests = row_digests(tables)
    previous = await _previous(session, stamp)
    changes = release_changes(
        digests,
        previous.rowDigests if previous is not None else None,
        previous.version if previous is not None else None,
    )
    files = release_files(tables, stamp, changes, site=site)
    row = existing or OpenDataRelease(target=stamp.target, version=stamp.version, state=DRAFT)
    row.releasedOn = stamp.released
    row.doi, row.conceptDoi = stamp.doi, stamp.concept_doi
    row.recordId, row.conceptRecordId = stamp.record_id, stamp.concept_record_id
    row.files, row.counts, row.changes, row.rowDigests = (
        files.facts(),
        tables.counts(),
        changes.counts(),
        digests,
    )
    row.totalBytes, row.manifestSha256 = files.total_bytes(), files.manifest_sha256()
    if existing is None:
        session.add(row)
    await session.flush()
    return BuiltRelease(stamp=stamp, files=files, counts=tables.counts(), changes=changes)


async def record_release(session: AsyncSession, publication: Publication) -> OpenDataRelease:
    release = await _release(session, publication.target, publication.version)
    if release is None:
        raise InvalidInput(NOT_BUILT.format(version=publication.version, target=publication.target))
    if release.doi != publication.doi:
        raise InvalidInput(
            OTHER_DOI.format(version=publication.version, built=release.doi, given=publication.doi)
        )
    if release.state == PUBLISHED:
        if release.recordUrl != publication.record_url:
            raise InvalidInput(PUBLISHED_ELSEWHERE.format(version=release.version, url=release.recordUrl))
        return release
    release.state = PUBLISHED
    release.recordUrl = publication.record_url
    release.publishedAt = publication.published_at
    await session.flush()
    return release


async def latest_release(session: AsyncSession, target: str) -> OpenDataRelease | None:
    releases = await published_releases(session, checked_target(target))
    return releases[0] if releases else None


async def published_releases(session: AsyncSession, target: str) -> list[OpenDataRelease]:
    rows = await session.scalars(
        _newest_first(OpenDataRelease.target == target).options(defer(OpenDataRelease.rowDigests))
    )
    return list(rows.all())


async def _release(session: AsyncSession, target: str, version: str) -> OpenDataRelease | None:
    return await session.scalar(
        select(OpenDataRelease).where(OpenDataRelease.target == target, OpenDataRelease.version == version)
    )


async def _previous(session: AsyncSession, stamp: ReleaseStamp) -> OpenDataRelease | None:
    return await session.scalar(
        _newest_first(OpenDataRelease.target == stamp.target, OpenDataRelease.version != stamp.version).limit(
            1
        )
    )


def _newest_first(*conditions: ColumnElement[bool]) -> Select[tuple[OpenDataRelease]]:
    return (
        select(OpenDataRelease)
        .where(*conditions, OpenDataRelease.state == PUBLISHED)
        .order_by(OpenDataRelease.publishedAt.desc(), OpenDataRelease.version.desc())
    )
