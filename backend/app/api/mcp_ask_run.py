from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.reading_deps import PROFILE_REQUIRED_DETAIL
from app.core.db import sessionmaker
from app.core.deps import (
    PASSWORD_CHANGE_REQUIRED_DETAIL,
    TWO_FACTOR_SETUP_REQUIRED_DETAIL,
    password_change_pending,
    refusal_for,
    two_factor_setup_pending,
)
from app.core.errors import InvalidInput
from app.core.guardian_hold import GUARDIAN_CONSENT_REQUIRED_DETAIL, guardian_hold_owed
from app.core.rate_limit import ask_attempt
from app.core.roles import STUDENT, Capability, can, is_uncapped, role_value
from app.core.shielded import ShieldedWork
from app.models import User
from app.providers.answer_routes import answer_models
from app.providers.budget import AnswerSpend
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.depth import selectable_depths
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.mcp_ask import ASK_TIMEOUT_SECONDS
from app.research.planning import withheld_name
from app.research.reading_style import ReadingStyle, reading_style_for
from app.services import reader_profiles
from app.services.answer_runs import AnswerRun, answer_to_the_end
from app.services.answer_store import build_answer_pipeline
from app.services.answering import AnswerAsk, AnswerPipeline
from app.services.craft_resolver import CraftIndexStore
from app.services.explainer_history import latest_version
from app.services.live_sources import LiveSourcesStore

__all__ = [
    "THROTTLED",
    "TIMED_OUT",
    "AskTools",
    "PipelineFor",
    "answer_pipeline_for",
    "ask_refusal",
    "asker_reading_style",
    "fresh_pipeline",
    "run_to_the_end",
    "throttle_refusal",
    "withheld_terms",
]

THROTTLED = "You have asked a lot in the last few minutes. Ask again in {seconds} seconds."
TIMED_OUT = (
    "The answer was not finished within {wait}, so nothing is returned. Ask again, or ask on the site."
)

PipelineFor = Callable[[User, str, CraftIndexStore], AbstractAsyncContextManager[AnswerPipeline]]
StoredAnswer = Callable[[AsyncSession, uuid.UUID, uuid.UUID], Awaitable[ExplainerVersionDocument]]


def answer_pipeline_for(
    user: User, depth: str, *, index: CraftIndexStore, live: LiveSourcesStore, shield: ShieldedWork
) -> AnswerPipeline:
    spend = AnswerSpend(depth=depth)
    principal = Principal(user_id=user.id, role=user.role, answer=spend)
    optional = Principal(user_id=user.id, role=user.role, answer=spend.headroom())
    return build_answer_pipeline(
        sessions=sessionmaker(),
        index=index,
        live=live,
        models=answer_models(depth, principal=principal, optional=optional),
        embed=router_embedder(principal),
        shield=shield,
    )


@asynccontextmanager
async def fresh_pipeline(user: User, depth: str, index: CraftIndexStore) -> AsyncIterator[AnswerPipeline]:
    live, shield = LiveSourcesStore(), ShieldedWork()
    try:
        yield answer_pipeline_for(user, depth, index=index, live=live, shield=shield)
    finally:
        await shield.drain()
        await live.aclose()


@dataclass(frozen=True)
class AskTools:
    pipeline: PipelineFor = fresh_pipeline
    stored: StoredAnswer = latest_version
    timeout_seconds: float = ASK_TIMEOUT_SECONDS


async def ask_refusal(session: AsyncSession, user: User, depth: str) -> str | None:
    if password_change_pending(user):
        return PASSWORD_CHANGE_REQUIRED_DETAIL
    if two_factor_setup_pending(user):
        return TWO_FACTOR_SETUP_REQUIRED_DETAIL
    if await guardian_hold_owed(session, user):
        return GUARDIAN_CONSENT_REQUIRED_DETAIL
    if not can(user, Capability.ASK_STANDARD) or depth not in selectable_depths(user):
        return refusal_for(Capability.ASK_STANDARD)
    return None


async def asker_reading_style(session: AsyncSession, user: User) -> ReadingStyle | None:
    if role_value(user) != STUDENT:
        return None
    profile = await reader_profiles.student_profile(session, user.id)
    if profile is None:
        raise InvalidInput(PROFILE_REQUIRED_DETAIL)
    return reading_style_for(user, profile)


async def throttle_refusal(user: User) -> str | None:
    if is_uncapped(user):
        return None
    allowed, retry = await ask_attempt(str(user.id))
    return None if allowed else THROTTLED.format(seconds=max(1, ceil(retry)))


def withheld_terms(user: User) -> tuple[str, ...]:
    return withheld_name(user.name)


async def run_to_the_end(ask: AnswerAsk, user: User, index: CraftIndexStore, tools: AskTools) -> AnswerRun:
    try:
        async with asyncio.timeout(tools.timeout_seconds):
            async with tools.pipeline(user, ask.depth, index) as pipeline:
                return await answer_to_the_end(ask, pipeline)
    except TimeoutError:
        raise InvalidInput(TIMED_OUT.format(wait=_duration(tools.timeout_seconds))) from None


def _duration(seconds: float) -> str:
    if seconds >= 60:
        return f"{round(seconds / 60)} minutes"
    return f"{max(1, round(seconds))} seconds"
