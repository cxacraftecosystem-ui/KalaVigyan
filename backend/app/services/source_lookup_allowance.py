from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from math import ceil

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.allowances import ALLOWANCE_UNREAD
from app.core.errors import InvalidInput
from app.core.rate_limit import (
    ANONYMOUS_HOLDER,
    ANONYMOUS_LOOKUP_LIMITS,
    LOOKUP_LIMITS,
    lookup_attempt,
)
from app.core.roles import PROFESSOR, Capability, can, has_rank
from app.models import User
from app.research.trust_tiers import PROVEN

from . import trust_tiers

__all__ = [
    "LookupCaller",
    "TierOf",
    "account_tier",
    "anonymous_caller",
    "contributor_caller",
    "lookup_caller",
    "spend",
    "spent_wait",
    "wait_words",
]

SPENT = (
    "This account made {limit} {noun} this hour, the most its trust tier ({tier}) allows. "
    "Try again in {wait}."
)
SPENT_SIGNED_OUT = (
    "Signed-out callers made {limit} {noun} together this hour, the most KalaVigyan allows them. "
    "Sign in, or try again in {wait}."
)
NOT_A_CONTRIBUTOR = (
    "{tool} needs a signed-in account of Researcher or above, the accounts that contribute to KalaVigyan."
)
MINUTE = 60

TierOf = Callable[[AsyncSession, User], Awaitable[str]]


@dataclass(frozen=True)
class LookupCaller:
    holder: str
    tier: str | None = None

    def limit(self, kind: str) -> int:
        if self.tier is None:
            return ANONYMOUS_LOOKUP_LIMITS[kind]
        return LOOKUP_LIMITS[kind][self.tier]


async def account_tier(session: AsyncSession, user: User) -> str:
    if has_rank(user.role, PROFESSOR):
        return PROVEN
    return (await trust_tiers.account_standing(session, user.id)).tier


def anonymous_caller() -> LookupCaller:
    return LookupCaller(holder=ANONYMOUS_HOLDER)


async def lookup_caller(session: AsyncSession, user: User | None, tier_of: TierOf) -> LookupCaller:
    if user is None:
        return anonymous_caller()
    return LookupCaller(holder=str(user.id), tier=await tier_of(session, user))


async def contributor_caller(
    session: AsyncSession, user: User | None, tool: str, tier_of: TierOf
) -> LookupCaller:
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NOT_A_CONTRIBUTOR.format(tool=tool))
    return await lookup_caller(session, user, tier_of)


async def spent_wait(kind: str, caller: LookupCaller) -> float | None:
    taken = await lookup_attempt(kind, caller.holder, caller.limit(kind))
    return None if taken.granted else taken.wait_seconds


async def spend(kind: str, caller: LookupCaller, *, now: datetime | None = None) -> None:
    taken = await lookup_attempt(kind, caller.holder, caller.limit(kind), now=now)
    if taken.granted:
        return
    if taken.unread:
        raise InvalidInput(ALLOWANCE_UNREAD)
    words = SPENT if caller.tier is not None else SPENT_SIGNED_OUT
    tier = (caller.tier or "").lower()
    wait = wait_words(taken.wait_seconds)
    raise InvalidInput(words.format(limit=caller.limit(kind), noun=kind, tier=tier, wait=wait))


def wait_words(seconds: float) -> str:
    minutes = max(1, ceil(seconds / MINUTE))
    return "1 minute" if minutes == 1 else f"{minutes} minutes"
