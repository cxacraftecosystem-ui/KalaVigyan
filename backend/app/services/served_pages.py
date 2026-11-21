from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable, Collection, Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.models import (
    ArticleSection,
    Craft,
    CraftCategory,
    CraftPageSnapshot,
    MonographDocument as DocumentRow,
)
from app.research.page_revalidation import PageOwners

from .craft_page_snapshots import OPEN
from .monograph_document import CRAFT_SUBJECT, document_hash, latest_document_row
from .monograph_generated import generated_document
from .open_work_subjects import CATEGORY, WorkSubject, craft_subjects, subject_by_key
from .page_revalidation import BatchedRefresh

__all__ = [
    "BUILD_READ_SECONDS",
    "SERVED_RECORD_SCHEMA_VERSION",
    "ServedPages",
    "ServedRecord",
    "changed_owners",
    "document_digest",
    "document_subjects",
    "kept_digests",
    "measure_served",
    "page_digests",
    "parsed_record",
    "record_text",
    "refresh_report",
]

logger = logging.getLogger(__name__)

SERVED_RECORD_SCHEMA_VERSION = 1
BUILD_READ_SECONDS = 30
PUBLISHED = "PUBLISHED"
CRAFT_OWNER, CATEGORY_OWNER = "craft", "category"
PAGE, DOCUMENT = "page", "document"
SEPARATOR = ":"
DIGEST_KEY = re.compile(r"^(?:page:craft|document:craft|document:category):[^:\s]+$")
Clock = Callable[[], float]


class ServedRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(default=SERVED_RECORD_SCHEMA_VERSION, alias="schemaVersion")
    digests: dict[str, str] = Field(default_factory=dict)

    @field_validator("digests")
    @classmethod
    def _keys_name_a_page(cls, digests: dict[str, str]) -> dict[str, str]:
        wrong = sorted(key for key in digests if DIGEST_KEY.match(key) is None)
        if wrong:
            raise ValueError(
                f"a served digest is keyed page:craft:<slug> or document:<craft|category>:<slug>, not {wrong[0]!r}"
            )
        return digests


@dataclass
class ServedPages:
    digests: dict[str, str] = field(default_factory=dict)
    unmeasured: set[str] = field(default_factory=set)
    failed: list[str] = field(default_factory=list)
    measured: dict[str, float] = field(default_factory=dict)

    def slowest(self) -> tuple[str, float] | None:
        if not self.measured:
            return None
        owner = max(self.measured, key=lambda key: (self.measured[key], key))
        return owner, self.measured[owner]

    def slower_than(self, seconds: float) -> list[str]:
        return sorted(owner for owner, took in self.measured.items() if took > seconds)


async def measure_served(
    session: AsyncSession, served: ServedPages, *, clock: Clock = time.perf_counter
) -> None:
    served.digests.update(await page_digests(session))
    subjects = await document_subjects(session)
    served.unmeasured.update(_owner_key(subject) for subject in subjects)
    for subject in subjects:
        await _measure(session, subject, served, clock)


async def page_digests(session: AsyncSession) -> dict[str, str]:
    rows = await session.execute(
        select(Craft.slug, CraftPageSnapshot.etag)
        .join(CraftPageSnapshot, CraftPageSnapshot.craftId == Craft.id)
        .where(CraftPageSnapshot.variant == OPEN)
    )
    return {_key(PAGE, CRAFT_OWNER, slug): etag for slug, etag in rows.all()}


async def document_subjects(session: AsyncSession) -> list[WorkSubject]:
    stored = select(DocumentRow.subjectSlug).where(DocumentRow.subjectKind == CRAFT_SUBJECT)
    sectioned = select(ArticleSection.craftId).where(
        ArticleSection.craftId.is_not(None), ArticleSection.status == PUBLISHED
    )
    crafts = await session.scalars(
        select(Craft.slug).where(or_(Craft.slug.in_(stored), Craft.id.in_(sectioned)))
    )
    shared = select(ArticleSection.categoryId).where(ArticleSection.status == PUBLISHED)
    categories = await session.scalars(select(CraftCategory.slug).where(CraftCategory.id.in_(shared)))
    found = [
        *await craft_subjects(session, sorted(crafts.all())),
        *[await subject_by_key(session, CATEGORY, slug) for slug in sorted(categories.all())],
    ]
    return sorted(found, key=lambda subject: (not subject.curated, subject.kind == CATEGORY, subject.slug))


async def document_digest(session: AsyncSession, subject: WorkSubject) -> str | None:
    if subject.kind != CATEGORY:
        row = await latest_document_row(session, CRAFT_SUBJECT, subject.slug)
        if row is not None:
            return f"v{row.version}-{row.contentHash}"
    generated = await generated_document(session, subject.kind, subject.slug)
    return None if generated is None else f"v{generated.version}-{document_hash(generated)}"


def changed_owners(
    before: Mapping[str, str], now: Mapping[str, str], unmeasured: Collection[str] = ()
) -> PageOwners:
    moved = {_owner_of(key) for key in before.keys() | now.keys() if before.get(key) != now.get(key)}
    owners = moved | set(unmeasured)
    return PageOwners(crafts=_slugs(owners, CRAFT_OWNER), categories=_slugs(owners, CATEGORY_OWNER))


def kept_digests(
    before: Mapping[str, str], now: Mapping[str, str], *, unsettled: PageOwners
) -> dict[str, str]:
    held = {_owner(CRAFT_OWNER, slug) for slug in unsettled.crafts}
    held |= {_owner(CATEGORY_OWNER, slug) for slug in unsettled.categories}
    kept = {key: digest for key, digest in now.items() if _owner_of(key) not in held}
    kept |= {key: digest for key, digest in before.items() if _owner_of(key) in held}
    return dict(sorted(kept.items()))


def parsed_record(text: str) -> dict[str, str]:
    return ServedRecord.model_validate_json(text).digests


def record_text(digests: Mapping[str, str]) -> str:
    record = ServedRecord(digests=dict(sorted(digests.items())))
    return record.model_dump_json(by_alias=True, indent=1) + "\n"


def refresh_report(served: ServedPages, changed: PageOwners, sent: BatchedRefresh) -> dict[str, Any]:
    slowest = served.slowest()
    return {
        "pages": sum(1 for key in served.digests if key.startswith(f"{PAGE}{SEPARATOR}")),
        "documents": len(served.measured),
        "unmeasured": sorted(served.unmeasured),
        "documentsFailed": served.failed,
        "slowestDocument": None if slowest is None else {"page": slowest[0], "seconds": round(slowest[1], 2)},
        "slowerThanBuildReads": served.slower_than(BUILD_READ_SECONDS),
        "changed": {"crafts": len(changed.crafts), "categories": len(changed.categories)},
        "refreshed": {"crafts": len(sent.refreshed.crafts), "categories": len(sent.refreshed.categories)},
        "notRefreshed": {
            "crafts": len(sent.unrefreshed.crafts),
            "categories": len(sent.unrefreshed.categories),
        },
        "batches": sent.batches,
        "batchesSent": sent.tried,
    }


async def _measure(session: AsyncSession, subject: WorkSubject, served: ServedPages, clock: Clock) -> None:
    owner = _owner_key(subject)
    started = clock()
    try:
        digest = await document_digest(session, subject)
    except (AppError, ValidationError) as error:
        logger.error("the document of %s could not be read: %s", owner, error)
        served.failed.append(owner)
        return
    served.measured[owner] = clock() - started
    served.unmeasured.discard(owner)
    if digest is not None:
        served.digests[f"{DOCUMENT}{SEPARATOR}{owner}"] = digest


def _owner_key(subject: WorkSubject) -> str:
    return _owner(CATEGORY_OWNER if subject.kind == CATEGORY else CRAFT_OWNER, subject.slug)


def _owner(kind: str, slug: str) -> str:
    return f"{kind}{SEPARATOR}{slug}"


def _key(part: str, kind: str, slug: str) -> str:
    return f"{part}{SEPARATOR}{_owner(kind, slug)}"


def _owner_of(key: str) -> str:
    return key.split(SEPARATOR, 1)[1]


def _slugs(owners: Collection[str], kind: str) -> tuple[str, ...]:
    prefix = f"{kind}{SEPARATOR}"
    return tuple(sorted(owner.removeprefix(prefix) for owner in owners if owner.startswith(prefix)))
