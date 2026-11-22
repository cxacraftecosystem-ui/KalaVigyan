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
from .open_data_release import ReleaseStamp, checked_craft, checked_doi, checked_target, released_on
from .open_data_rows import read_tables
from .open_data_scope import WHOLE, ReleaseScope
from .open_data_slice import craft_slice

__all__ = [
    "DRAFT",
    "PUBLISHED",
    "BuiltRelease",
    "Publication",
    "build_release",
    "craft_releases",
    "latest_release",
    "published_releases",
    "record_release",
]

DRAFT = "DRAFT"
PUBLISHED = "PUBLISHED"
ALREADY_PUBLISHED = (
    "Version {version}{of} is published on {target} already; give the next version, such as {version}.2."
)
NOT_BUILT = "No release {version}{of} was built for {target}; build it before recording it."
OTHER_DOI = "Release {version} was built with the DOI {built}, not {given}."
PUBLISHED_ELSEWHERE = "Release {version} was recorded already at {url}."


@dataclass(frozen=True)
class BuiltRelease:
    stamp: ReleaseStamp
    scope: ReleaseScope
    files: ReleaseFiles
    counts: dict[str, int]
    changes: ReleaseChanges

    def summary(self) -> dict[str, Any]:
        return {
            "target": self.stamp.target,
            "craft": self.scope.craft,
            "title": self.scope.title,
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
    craft: str | None = None

    def __post_init__(self) -> None:
        checked_target(self.target)
        released_on(self.version)
        checked_doi(self.doi)
        checked_craft(self.craft)
        if not self.record_url.startswith("https://"):
            raise InvalidInput("A Zenodo record address starts with https://.")
        if self.published_at.tzinfo is None:
            raise InvalidInput("The publication time names its time zone, as 2026-11-21T10:00:00+00:00.")


async def build_release(session: AsyncSession, stamp: ReleaseStamp, *, site: str) -> BuiltRelease:
    existing = await _release(session, stamp.target, stamp.version, stamp.craft)
    if existing is not None and existing.state == PUBLISHED:
        raise InvalidInput(
            ALREADY_PUBLISHED.format(version=stamp.version, of=_of(stamp.craft), target=stamp.target)
        )
    piece = await craft_slice(session, stamp.craft) if stamp.craft is not None else None
    scope = piece.scope if piece is not None else WHOLE
    tables = await read_tables(session, site=site, craft=piece)
    digests = row_digests(tables)
    previous = await _previous(session, stamp)
    changes = release_changes(
        digests,
        previous.rowDigests if previous is not None else None,
        previous.version if previous is not None else None,
    )
    files = release_files(tables, stamp, changes, site=site, scope=scope)
    built = BuiltRelease(stamp=stamp, scope=scope, files=files, counts=tables.counts(), changes=changes)
    row = existing or OpenDataRelease(
        target=stamp.target, scope=stamp.craft, version=stamp.version, state=DRAFT
    )
    _keep(row, built, digests)
    if existing is None:
        session.add(row)
    await session.flush()
    return built


async def record_release(session: AsyncSession, publication: Publication) -> OpenDataRelease:
    release = await _release(session, publication.target, publication.version, publication.craft)
    if release is None:
        raise InvalidInput(
            NOT_BUILT.format(
                version=publication.version, of=_of(publication.craft), target=publication.target
            )
        )
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


async def latest_release(
    session: AsyncSession, target: str, *, craft: str | None = None
) -> OpenDataRelease | None:
    releases = await published_releases(session, checked_target(target), craft=craft)
    return releases[0] if releases else None


async def published_releases(
    session: AsyncSession, target: str, *, craft: str | None = None
) -> list[OpenDataRelease]:
    found = _newest_first(OpenDataRelease.target == target, _scoped(craft))
    rows = await session.scalars(found.options(defer(OpenDataRelease.rowDigests)))
    return list(rows.all())


async def craft_releases(session: AsyncSession, target: str) -> list[OpenDataRelease]:
    found = (
        select(OpenDataRelease)
        .where(
            OpenDataRelease.target == target,
            OpenDataRelease.scope.is_not(None),
            OpenDataRelease.state == PUBLISHED,
        )
        .order_by(OpenDataRelease.scope, OpenDataRelease.publishedAt.desc(), OpenDataRelease.version.desc())
    )
    rows = await session.scalars(found.options(defer(OpenDataRelease.rowDigests)))
    return list(rows.all())


def _keep(row: OpenDataRelease, built: BuiltRelease, digests: dict[str, dict[str, str]]) -> None:
    stamp, files = built.stamp, built.files
    row.releasedOn = stamp.released
    row.doi, row.conceptDoi = stamp.doi, stamp.concept_doi
    row.recordId, row.conceptRecordId = stamp.record_id, stamp.concept_record_id
    row.files, row.counts, row.changes, row.rowDigests = (
        files.facts(),
        built.counts,
        built.changes.counts(),
        digests,
    )
    row.totalBytes, row.manifestSha256 = files.total_bytes(), files.manifest_sha256()


def _of(craft: str | None) -> str:
    return "" if craft is None else f" of {craft}"


def _scoped(craft: str | None) -> ColumnElement[bool]:
    return OpenDataRelease.scope.is_(None) if craft is None else OpenDataRelease.scope == craft


async def _release(
    session: AsyncSession, target: str, version: str, craft: str | None
) -> OpenDataRelease | None:
    return await session.scalar(
        select(OpenDataRelease).where(
            OpenDataRelease.target == target, OpenDataRelease.version == version, _scoped(craft)
        )
    )


async def _previous(session: AsyncSession, stamp: ReleaseStamp) -> OpenDataRelease | None:
    return await session.scalar(
        _newest_first(
            OpenDataRelease.target == stamp.target,
            _scoped(stamp.craft),
            OpenDataRelease.version != stamp.version,
        ).limit(1)
    )


def _newest_first(*conditions: ColumnElement[bool]) -> Select[tuple[OpenDataRelease]]:
    return (
        select(OpenDataRelease)
        .where(*conditions, OpenDataRelease.state == PUBLISHED)
        .order_by(OpenDataRelease.publishedAt.desc(), OpenDataRelease.version.desc())
    )
