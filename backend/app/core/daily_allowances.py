from __future__ import annotations

import time
from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import Decimal
from types import MappingProxyType
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import ALLOWANCE_RESOURCES, ROLE_RANK, STUDENT, is_uncapped, role_value
from app.models import QuotaPolicy

__all__ = [
    "CACHE_TTL_SECONDS",
    "AllowanceCache",
    "DailyAllowances",
    "daily_allowance",
    "invalidate",
    "load_daily_allowances",
    "refresh_if_stale",
    "save_daily_allowances",
]


CACHE_TTL_SECONDS = 30.0

Table = Mapping[str, Mapping[str, int | None]]


@dataclass(frozen=True)
class DailyAllowances:
    per_role: Table = field(default_factory=lambda: MappingProxyType({}))

    def of(self, user_or_role: Any, resource: str) -> int | None:
        role = role_value(user_or_role)
        known = role if role in ROLE_RANK else STUDENT
        return self.per_role.get(known, {}).get(resource)

    def view(self) -> dict[str, dict[str, int | None]]:
        return {
            role: {resource: self.of(role, resource) for resource in ALLOWANCE_RESOURCES}
            for role in ROLE_RANK
        }


class AllowanceCache:
    def __init__(self, *, ttl_seconds: float = CACHE_TTL_SECONDS) -> None:
        self._ttl = ttl_seconds
        self._held = DailyAllowances()
        self._loaded_at = 0.0

    def invalidate(self) -> None:
        self._loaded_at = 0.0

    def fresh(self) -> bool:
        return self._loaded_at > 0.0 and (time.monotonic() - self._loaded_at) < self._ttl

    def hold(self, allowances: DailyAllowances) -> None:
        self._held = allowances
        self._loaded_at = time.monotonic()

    async def refresh_if_stale(self, session: AsyncSession) -> None:
        if not self.fresh():
            self.hold(await load_daily_allowances(session))

    def of(self, user_or_role: Any, resource: str) -> int | None:
        return self._held.of(user_or_role, resource)


allowances = AllowanceCache()


async def load_daily_allowances(session: AsyncSession) -> DailyAllowances:
    rows = await session.execute(
        select(QuotaPolicy.role, QuotaPolicy.resource, QuotaPolicy.perDay).where(
            QuotaPolicy.resource.in_(ALLOWANCE_RESOURCES)
        )
    )
    table: dict[str, dict[str, int | None]] = {}
    for role, resource, per_day in rows:
        table.setdefault(str(role), {})[str(resource)] = _whole(per_day)
    return DailyAllowances(MappingProxyType(table))


async def save_daily_allowances(session: AsyncSession, changes: Table) -> None:
    _check(changes)
    for role, resources in changes.items():
        for resource, per_day in resources.items():
            await session.execute(
                insert(QuotaPolicy)
                .values(role=role, resource=resource, perDay=per_day)
                .on_conflict_do_update(
                    index_elements=[QuotaPolicy.role, QuotaPolicy.resource], set_={"perDay": per_day}
                )
            )


def invalidate() -> None:
    allowances.invalidate()


async def refresh_if_stale(session: AsyncSession) -> None:
    await allowances.refresh_if_stale(session)


def daily_allowance(user_or_role: Any, resource: str) -> int | None:
    return allowances.of(user_or_role, resource)


def _whole(per_day: Decimal | None) -> int | None:
    return None if per_day is None else int(per_day)


def _check(changes: Table) -> None:
    unknown_roles = set(changes) - set(ROLE_RANK)
    if unknown_roles:
        raise InvalidInput(f"Unknown roles: {', '.join(sorted(unknown_roles))}")
    for role, resources in changes.items():
        unknown = set(resources) - set(ALLOWANCE_RESOURCES)
        if unknown:
            raise InvalidInput(f"Unknown allowances: {', '.join(sorted(unknown))}")
        if is_uncapped(role) and any(value is not None for value in resources.values()):
            raise InvalidInput("Master Admins have no caps.")
        if any(value is not None and value < 0 for value in resources.values()):
            raise InvalidInput("A daily allowance is zero or more.")
