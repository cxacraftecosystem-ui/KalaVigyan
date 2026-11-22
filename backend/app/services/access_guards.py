from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.roles import Capability, can, is_master_admin, may_manage_target, role_rank
from app.models import AccessRoster, User

from .access_roster import ACTIVE, BARRED, PENDING, normalise_email, role_of, status_of

__all__ = [
    "ABOVE_ACCOUNT_DETAIL",
    "ABOVE_ROLE_DETAIL",
    "MASTER_BARRED_DETAIL",
    "MASTER_CHANGED_DETAIL",
    "RESTORE_ADMINS_ONLY_DETAIL",
    "Guard",
    "accounts_at",
    "bar_refusal",
    "change_refusal",
    "entry_offers",
    "reinstate_refusal",
]

MASTER_BARRED_DETAIL = "The master admin's access can't be withdrawn."
MASTER_CHANGED_DETAIL = "The master admin's access can't be changed."
ABOVE_ACCOUNT_DETAIL = "You can't change access for an account at or above your role."
ABOVE_ROLE_DETAIL = "You can't change access for this role."
RESTORE_ADMINS_ONLY_DETAIL = "Only admins can restore access that was suspended or refused."

Guard = Callable[[Any, AccessRoster, User | None], str | None]


def bar_refusal(actor: Any, row: AccessRoster, account: User | None) -> str | None:
    if _is_master_entry(row):
        return MASTER_BARRED_DETAIL
    return _rank_refusal(actor, row, account)


def change_refusal(actor: Any, row: AccessRoster, account: User | None) -> str | None:
    if is_master_admin(actor):
        return None
    if _is_master_entry(row):
        return MASTER_CHANGED_DETAIL
    return _rank_refusal(actor, row, account)


def reinstate_refusal(actor: Any, row: AccessRoster, account: User | None) -> str | None:
    if status_of(row) not in BARRED:
        return change_refusal(actor, row, account)
    if not can(actor, Capability.DISABLE_USERS):
        return RESTORE_ADMINS_ONLY_DETAIL
    return bar_refusal(actor, row, account)


def entry_offers(actor: Any, row: AccessRoster, account: User | None) -> dict[str, bool]:
    standing = status_of(row)
    return {
        "update": change_refusal(actor, row, account) is None,
        "suspend": standing == ACTIVE and bar_refusal(actor, row, account) is None,
        "admit": standing != ACTIVE and reinstate_refusal(actor, row, account) is None,
        "refuse": standing == PENDING and bar_refusal(actor, row, account) is None,
    }


async def accounts_at(session: AsyncSession, rows: Sequence[AccessRoster]) -> dict[str, User]:
    addresses = {normalise_email(row.email) for row in rows}
    if not addresses:
        return {}
    found = await session.execute(select(User).where(func.lower(User.email).in_(sorted(addresses))))
    return {normalise_email(user.email): user for user in found.scalars().all()}


def _is_master_entry(row: AccessRoster) -> bool:
    return normalise_email(row.email) == normalise_email(get_settings().master_admin_email)


def _rank_refusal(actor: Any, row: AccessRoster, account: User | None) -> str | None:
    if account is not None and not may_manage_target(actor, account):
        return ABOVE_ACCOUNT_DETAIL
    entry_role = role_of(row)
    if entry_role and not is_master_admin(actor) and role_rank(entry_role) >= role_rank(actor):
        return ABOVE_ROLE_DETAIL
    return None
