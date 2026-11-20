from __future__ import annotations

import re
import uuid
from collections.abc import Mapping
from datetime import datetime
from functools import cache
from types import MappingProxyType

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.skill_library import reference_text
from app.models import SuppliedSource, User
from app.research.monograph_document import MonographDocument
from app.research.page_drafts import PageLists
from app.research.page_proposals import PageBundle, PagePreviewResult
from app.research.page_report import PageReport, ReportInput, page_report
from app.research.structure_proposals import ReactionItem
from app.research.supplied_sources import READY, cite_key

from .page_preview_links import UnknownPreview, preview_document

__all__ = ["CHECKLIST", "checklist_titles", "preview_report", "supplied_grades"]

CHECKLIST = "page-checklist"
RULE = re.compile(r"^(\d{1,2})\. \*\*(.+?)\*\*", re.MULTILINE)
PREVIEW_SEGMENT = "/preview/"


@cache
def checklist_titles() -> Mapping[int, str]:
    found = {int(number): title.rstrip(".") for number, title in RULE.findall(reference_text(CHECKLIST))}
    return MappingProxyType(found)


async def preview_report(
    session: AsyncSession,
    user: User,
    bundle: PageBundle,
    previewed: PagePreviewResult,
    *,
    lists: PageLists | None = None,
    now: datetime,
) -> PageReport | None:
    document = await _document(session, user, previewed.preview_url, now)
    if document is None:
        return None
    given = ReportInput(
        document=document,
        lists=lists,
        statements={f"fact:{n}": fact.statement for n, fact in enumerate(bundle.facts)},
        reactions=tuple(item.item for item in bundle.structure if isinstance(item.item, ReactionItem)),
        supplied=await supplied_grades(session, user.id, _cited_urls(bundle)),
    )
    return page_report(given, checklist_titles())


async def supplied_grades(session: AsyncSession, user_id: uuid.UUID, urls: list[str]) -> dict[str, str]:
    keys = sorted({cite_key(url) for url in urls})
    if not keys:
        return {}
    rows = await session.execute(
        select(SuppliedSource.citeUrl, SuppliedSource.grade).where(
            SuppliedSource.userId == user_id, SuppliedSource.citeUrl.in_(keys), SuppliedSource.state == READY
        )
    )
    return dict(rows.tuples().all())


async def _document(session: AsyncSession, user: User, url: str, now: datetime) -> MonographDocument | None:
    token = url.rsplit(PREVIEW_SEGMENT, 1)[-1]
    try:
        return MonographDocument.model_validate(await preview_document(session, user, token, now=now))
    except UnknownPreview, ValidationError:
        return None


def _cited_urls(bundle: PageBundle) -> list[str]:
    return [
        *(source.url for fact in bundle.facts for source in fact.sources),
        *(source.url for item in bundle.structure for source in item.sources),
    ]
