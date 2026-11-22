import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import READER_VARY, cached_read, public_reader, reader_cache, reading_acls
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.http_cache import PRIVATE_NO_CACHE
from app.models import Craft, User
from app.models.enums import DISCIPLINES
from app.research.blocks_learning import COMPARE_CRAFTS_MAX, COMPARE_CRAFTS_MIN
from app.research.crafts import SLUG_MAX_CHARS
from app.research.subject_keys import TERM_KEY, TERM_KEY_MAX_CHARS
from app.research.vocabulary import Discipline
from app.services import knowledge_view
from app.services.answer_quiz import owned_explainer, shown_explainer, shown_quiz
from app.services.answering import NOT_FOUND_DETAIL
from app.services.craft_compare import craft_comparison
from app.services.shared_concepts import craft_shared_science, shared_concept_of

router = APIRouter(tags=["learning"])

CRAFTS_DETAIL = f"Choose {COMPARE_CRAFTS_MIN} to {COMPARE_CRAFTS_MAX} different crafts."
SECTIONS_DETAIL = "Choose sections of this explainer, each once."

Slugs = Annotated[list[str], Query(min_length=1)]
Facets = Annotated[list[Discipline] | None, Query()]
SectionIds = Annotated[list[str] | None, Query()]


@router.get("/crafts/{slug}/shared-science")
async def get_craft_shared_science(
    slug: str,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    craft = await _known_craft(session, slug)
    body = await craft_shared_science(session, craft, acls=reading_acls(reader))
    return cached_read(request, response, reader, body.model_dump(mode="json", by_alias=True))


@router.get("/shared-science/{term_key}")
async def get_shared_concept(
    request: Request,
    response: Response,
    term_key: str = Path(max_length=TERM_KEY_MAX_CHARS, pattern=TERM_KEY.pattern),
    craft: str | None = Query(default=None, min_length=1, max_length=SLUG_MAX_CHARS),
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    focus = await _known_craft(session, craft) if craft is not None else None
    body = await shared_concept_of(session, term_key, focus, acls=reading_acls(reader))
    if body is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    return cached_read(request, response, reader, body.model_dump(mode="json", by_alias=True))


@router.get("/compare")
async def get_comparison(
    request: Request,
    response: Response,
    crafts: Slugs,
    facets: Facets = None,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    if not COMPARE_CRAFTS_MIN <= len(crafts) <= COMPARE_CRAFTS_MAX or any(
        len(s) > SLUG_MAX_CHARS for s in crafts
    ):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, CRAFTS_DETAIL)
    rows = [await _known_craft(session, slug) for slug in crafts]
    if len({row.id for row in rows}) != len(rows):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, CRAFTS_DETAIL)
    chosen = list(dict.fromkeys(facets or DISCIPLINES))
    body = await craft_comparison(session, rows, chosen, acls=reading_acls(reader))
    if body is None:
        return Response(
            status_code=status.HTTP_204_NO_CONTENT,
            headers={"Cache-Control": reader_cache(reader), "Vary": READER_VARY},
        )
    return cached_read(request, response, reader, body.model_dump(mode="json", by_alias=True))


@router.get("/answers/{answer_id}/quiz")
async def get_answer_quiz(
    answer_id: uuid.UUID,
    response: Response,
    sections: SectionIds = None,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Any:
    explainer = await owned_explainer(session, answer_id, user.id)
    if explainer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    chosen = list(sections or [])
    if len(set(chosen)) != len(chosen) or not set(chosen) <= {section.id for section in explainer.sections}:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, SECTIONS_DETAIL)
    shown = await shown_explainer(session, explainer)
    if shown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    quiz = await shown_quiz(session, shown, chosen)
    if quiz is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"Cache-Control": PRIVATE_NO_CACHE})
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return quiz.model_dump(mode="json", by_alias=True)


async def _known_craft(session: AsyncSession, slug: str) -> Craft:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    return craft
