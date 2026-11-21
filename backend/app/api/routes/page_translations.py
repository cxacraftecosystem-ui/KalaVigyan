from __future__ import annotations

import uuid
from collections.abc import Awaitable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_reader
from app.api.structure_proposal_deps import site_origin
from app.core.db import get_session, release_connection
from app.core.deps import require
from app.core.errors import InvalidInput, Refused
from app.core.roles import Capability
from app.models import PageTranslation, User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.monograph_document import SUBJECT_KINDS
from app.research.open_work_translation_keys import TranslationLanguage
from app.research.page_revalidation import PageOwners
from app.research.page_translation_views import (
    PASSAGE_STATES,
    PASSAGES_LIMIT_DEFAULT,
    PASSAGES_LIMIT_MAX,
    ReaderLanguages,
    ReviewList,
    ReviewNote,
    TranslationView,
)
from app.services.open_work_subjects import WorkSubject, subject_by_key
from app.services.page_revalidation import refresh_pages
from app.services.page_translation_review import (
    REVIEW_LIMIT_DEFAULT,
    approve_translation,
    reject_translation,
    review_list,
)
from app.services.page_translation_views import PassageWindow, page_languages, translation_view
from app.services.translation_readers import reader_languages, set_reader_languages

router = APIRouter(tags=["translations"])
reviewer = require(Capability.MARK_CLAIM_LEVEL)

NO_DOCUMENT = "That page is not drawn as a monograph yet, so it has no passages to translate."
NOTE_NEEDED = "Say why the translation is rejected, so its translator can mend it."
CATEGORY = "category"

SubjectKind = Literal[*SUBJECT_KINDS]
Slug = Annotated[str, Path(min_length=1, max_length=SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")]
PassageState = Literal[*PASSAGE_STATES]


@dataclass(frozen=True)
class PagePath:
    kind: str
    slug: str


def page_path(kind: SubjectKind, slug: Slug) -> PagePath:
    return PagePath(kind, slug)


def passage_window(
    state: Annotated[PassageState | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=PASSAGES_LIMIT_MAX)] = PASSAGES_LIMIT_DEFAULT,
) -> PassageWindow:
    return PassageWindow(offset=offset, limit=limit, state=state)


@router.get("/pages/{kind}/{slug}/languages")
async def get_page_languages(
    request: Request,
    response: Response,
    page: PagePath = Depends(page_path),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    languages = await page_languages(session, await _subject(session, page))
    return cached_read(request, response, reader, languages.model_dump(mode="json", by_alias=True))


@router.get("/pages/{kind}/{slug}/translations/{language}")
async def get_page_translation(
    language: TranslationLanguage,
    page: PagePath = Depends(page_path),
    window: PassageWindow = Depends(passage_window),
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> TranslationView:
    subject = await _subject(session, page)
    view = await translation_view(session, subject, language, window=window, site=site_origin())
    await release_connection(session)
    if view is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_DOCUMENT)
    return view


@router.get("/knowledge/translations/review")
async def get_translation_review(
    limit: Annotated[int, Query(ge=1, le=PASSAGES_LIMIT_MAX)] = REVIEW_LIMIT_DEFAULT,
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> ReviewList:
    return await review_list(session, user, limit=limit, site=site_origin())


@router.post("/knowledge/translations/{translation_id}/approve")
async def post_translation_approval(
    translation_id: uuid.UUID,
    body: ReviewNote,
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    now = datetime.now(UTC)
    return await _decided(
        session, approve_translation(session, user, translation_id, note=body.note, now=now)
    )


@router.post("/knowledge/translations/{translation_id}/reject")
async def post_translation_rejection(
    translation_id: uuid.UUID,
    body: ReviewNote,
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    if body.note is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, NOTE_NEEDED)
    now = datetime.now(UTC)
    return await _decided(session, reject_translation(session, user, translation_id, note=body.note, now=now))


@router.get("/knowledge/translations/languages")
async def get_reader_languages(
    user: User = Depends(reviewer), session: AsyncSession = Depends(get_session)
) -> ReaderLanguages:
    return ReaderLanguages(languages=list(await reader_languages(session, user.id)))


@router.put("/knowledge/translations/languages")
async def put_reader_languages(
    body: ReaderLanguages, user: User = Depends(reviewer), session: AsyncSession = Depends(get_session)
) -> ReaderLanguages:
    try:
        chosen = await set_reader_languages(session, user, body.languages)
    except Refused as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, refused.message) from refused
    await session.commit()
    return ReaderLanguages(languages=list(chosen))


async def _subject(session: AsyncSession, page: PagePath) -> WorkSubject:
    try:
        return await subject_by_key(session, page.kind, page.slug)
    except InvalidInput as unknown:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(unknown)) from unknown


async def _decided(session: AsyncSession, decision: Awaitable[PageTranslation]) -> dict[str, str]:
    try:
        row = await decision
    except InvalidInput as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(missing)) from missing
    except Refused as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, refused.message) from refused
    decided = {"id": str(row.id), "status": row.status}
    owners = _owners(row.subjectKind, row.subjectSlug)
    await session.commit()
    await refresh_pages(owners)
    return decided


def _owners(kind: str, slug: str) -> PageOwners:
    return PageOwners(categories=(slug,)) if kind == CATEGORY else PageOwners(crafts=(slug,))
