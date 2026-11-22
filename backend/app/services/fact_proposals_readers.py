from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import InvalidInput
from app.models import ArticleSection
from app.research.category_page import category_path
from app.research.coverage_chapters import field_chapter
from app.research.knowledge_writes import ReaderPlace
from app.research.review_switch import Placement

from . import open_work_subjects
from .candidate_store import CATEGORY, CRAFT, FactSubject
from .coverage_reads import subject_field_work
from .reader_facts import UNEXPLAINED, hidden_reasons, shown_to_readers
from .stored_document_stamp import section_claims

__all__ = ["SECTION_TASK", "reader_place", "subject_page_url"]

SECTION_TASK = frozenset({"SECTION"})
CRAFT_PATH = "/crafts/"


async def reader_place(
    session: AsyncSession, claim_id: uuid.UUID, subject: FactSubject, field: str, placed: Placement
) -> ReaderPlace:
    page_url = subject_page_url(subject)
    where = {"page_url": page_url, "field": field, "chapter": field_chapter(field)}
    if not placed.live:
        return ReaderPlace(shown=False, reason=placed.outcome, **where)
    await session.flush()
    if claim_id not in await shown_to_readers(session, [claim_id]):
        reason = (await hidden_reasons(session, [claim_id])).get(claim_id, UNEXPLAINED)
        return ReaderPlace(shown=False, reason=reason, **where)
    if await _in_prose(session, claim_id, subject):
        return ReaderPlace(shown=True, in_prose=True, **where)
    return ReaderPlace(shown=True, write_task=await _section_task(session, subject, field), **where)


def subject_page_url(subject: FactSubject) -> str | None:
    site = get_settings().public_web_url.rstrip("/")
    if subject.slug is None:
        return None
    path = category_path(subject.slug) if subject.kind == CATEGORY else f"{CRAFT_PATH}{subject.slug}"
    return f"{site}{path}"


async def _in_prose(session: AsyncSession, claim_id: uuid.UUID, subject: FactSubject) -> bool:
    if subject.kind == CRAFT and subject.craft_id is not None:
        owned = ArticleSection.craftId == subject.craft_id
    elif subject.kind == CATEGORY and subject.category_id is not None:
        owned = ArticleSection.categoryId == subject.category_id
    else:
        return False
    return claim_id in set(await session.scalars(section_claims(owned)))


async def _section_task(session: AsyncSession, subject: FactSubject, field: str) -> str | None:
    if subject.slug is None or subject.kind not in (CRAFT, CATEGORY):
        return None
    try:
        work = (
            await open_work_subjects.craft_subject(session, subject.slug)
            if subject.kind == CRAFT
            else await open_work_subjects.subject_by_key(session, CATEGORY, subject.slug)
        )
    except InvalidInput:
        return None
    site = get_settings().public_web_url.rstrip("/")
    tasks = await subject_field_work(session, work, site=site, kinds=SECTION_TASK, field=field)
    return tasks[0].key if tasks else None
