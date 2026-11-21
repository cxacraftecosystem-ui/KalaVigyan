from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status

from app.api.public_deps import cached_read, public_reader, reading_acls
from app.core.db import sessionmaker
from app.core.errors import Refused
from app.core.rate_limit import retry_after_value, term_attempt
from app.core.roles import is_uncapped
from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.subject_keys import TERM_KEY_MAX_CHARS
from app.research.vocabulary import CANONICAL_LANGUAGE, AnswerLanguage
from app.services.ai_providers import AiTask
from app.services.term_summaries import NEEDS_LOOKUP_REASON, TermReader
from app.services.term_wiring import build_term_lookup, stored_term_lookup

router = APIRouter(tags=["terms"])

THROTTLED_DETAIL = "You have opened a lot of terms in the last few minutes. Wait a little and try again."
REFUSAL_STATUS = {NEEDS_LOOKUP_REASON: status.HTTP_401_UNAUTHORIZED}


async def term_lookup(request: Request, reader: User | None = Depends(public_reader)) -> TermReader:
    if reader is None:
        return stored_term_lookup(sessionmaker(), acls=reading_acls(reader))
    principal = Principal(user_id=reader.id, role=reader.role)
    return await build_term_lookup(
        sessions=sessionmaker(),
        live=request.app.state.live_sources,
        summarise_model=router_structured_model(AiTask.SUMMARISE, principal),
        translate_model=router_structured_model(AiTask.TRANSLATE, principal),
        acls=reading_acls(reader),
        embed=router_embedder(principal),
    )


def throttle(reader: User | None = Depends(public_reader)) -> None:
    if reader is None or is_uncapped(reader):
        return
    allowed, retry = term_attempt(str(reader.id))
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, THROTTLED_DETAIL, {"Retry-After": retry_after_value(retry)}
        )


@router.get("/terms/{key}", dependencies=[Depends(throttle)])
async def term_summary(
    request: Request,
    response: Response,
    key: str = Path(min_length=1, max_length=TERM_KEY_MAX_CHARS),
    language: AnswerLanguage = CANONICAL_LANGUAGE,
    *,
    reader: User | None = Depends(public_reader),
    lookup: TermReader = Depends(term_lookup),
) -> Any:
    try:
        summary = await lookup.summary(key, language)
    except Refused as refusal:
        code = REFUSAL_STATUS.get(refusal.reason, status.HTTP_404_NOT_FOUND)
        raise HTTPException(code, refusal.message) from None
    return cached_read(request, response, reader, summary.model_dump(mode="json", by_alias=True))
