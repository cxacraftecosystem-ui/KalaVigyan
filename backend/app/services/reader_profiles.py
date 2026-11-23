from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import guardian_hold
from app.core.roles import ARTISAN, STUDENT, Capability, can, role_value
from app.models import (
    AdminDistrict,
    AdminState,
    ArtisanContribution,
    ArtisanCraft,
    ArtisanProfile,
    ConsentRecord,
    Craft,
    StudentProfile,
    User,
)
from app.research.testimony import RECORDING_NOTICE_VERSION, held_back_terms

from .share_owners import withdraw_lesson_shares
from .shared_files import FileDeleter

__all__ = [
    "ARTISAN_RECORDING",
    "SHOWN_OR_WAITING",
    "ArtisanCraftRow",
    "DistrictNames",
    "apply_role_change",
    "artisan_crafts",
    "artisan_profile",
    "district_names",
    "guardian_confirmed",
    "guardian_consent_required",
    "held_back_name_terms",
    "profile_required",
    "recording_consent",
    "student_profile",
]

ARTISAN_RECORDING = "ARTISAN_RECORDING"
SHOWN_OR_WAITING = ("PENDING", "APPROVED")
ROLE_CHANGED = "users.role_changed"


@dataclass(frozen=True, kw_only=True)
class ArtisanCraftRow:
    craft_id: uuid.UUID
    slug: str
    name: str
    position: int
    extra: dict[str, Any] | None


@dataclass(frozen=True, kw_only=True)
class DistrictNames:
    lgd: int
    name: str
    state_lgd: int
    state_name: str


async def student_profile(session: AsyncSession, user_id: uuid.UUID) -> StudentProfile | None:
    return await session.get(StudentProfile, user_id)


async def artisan_profile(session: AsyncSession, user_id: uuid.UUID) -> ArtisanProfile | None:
    return await session.get(ArtisanProfile, user_id)


async def artisan_crafts(session: AsyncSession, user_id: uuid.UUID) -> list[ArtisanCraftRow]:
    rows = await session.execute(
        select(ArtisanCraft.position, Craft.id, Craft.slug, Craft.name, Craft.extraMetadata)
        .join(Craft, Craft.id == ArtisanCraft.craftId)
        .where(ArtisanCraft.userId == user_id)
        .order_by(ArtisanCraft.position)
    )
    return [
        ArtisanCraftRow(craft_id=craft_id, slug=slug, name=name, position=position, extra=extra)
        for position, craft_id, slug, name, extra in rows
    ]


async def district_names(session: AsyncSession, lgd: int) -> DistrictNames | None:
    row = (
        await session.execute(
            select(AdminDistrict.lgd, AdminDistrict.name, AdminState.lgd, AdminState.name)
            .join(AdminState, AdminState.lgd == AdminDistrict.stateLgd)
            .where(AdminDistrict.lgd == lgd)
        )
    ).first()
    if row is None:
        return None
    return DistrictNames(lgd=row[0], name=row[1], state_lgd=row[2], state_name=row[3])


async def recording_consent(session: AsyncSession, user_id: uuid.UUID) -> ConsentRecord | None:
    query = (
        select(ConsentRecord)
        .where(
            ConsentRecord.userId == user_id,
            ConsentRecord.kind == ARTISAN_RECORDING,
            ConsentRecord.noticeVersion == RECORDING_NOTICE_VERSION,
            ConsentRecord.withdrawnAt.is_(None),
        )
        .order_by(ConsentRecord.acceptedAt.desc())
        .limit(1)
    )
    return (await session.execute(query)).scalar_one_or_none()


async def guardian_confirmed(session: AsyncSession, user_id: uuid.UUID) -> bool:
    return await guardian_hold.guardian_confirmed(session, user_id)


async def guardian_consent_required(session: AsyncSession, user: Any) -> bool:
    return await guardian_hold.guardian_hold_owed(session, user)


async def held_back_name_terms(session: AsyncSession, user_id: uuid.UUID) -> frozenset[str]:
    account = await session.get(User, user_id)
    profile = await artisan_profile(session, user_id)
    if account is None or profile is None:
        return frozenset()
    return held_back_terms(
        account_name=account.name,
        mode=profile.creditMode,
        credit_name=profile.creditName,
        short_name=profile.creditShortName,
    )


async def profile_required(session: AsyncSession, user: Any) -> bool:
    role = role_value(user)
    if role == STUDENT:
        return await student_profile(session, user.id) is None
    if role == ARTISAN:
        if await artisan_profile(session, user.id) is None:
            return True
        count = await session.scalar(select(func.count()).where(ArtisanCraft.userId == user.id))
        return not count
    return False


async def apply_role_change(
    session: AsyncSession, user: Any, new_role: str, *, objects: FileDeleter | None
) -> None:
    old_role = role_value(user)
    if old_role == new_role:
        return
    if old_role == STUDENT:
        await session.execute(delete(StudentProfile).where(StudentProfile.userId == user.id))
    if old_role == ARTISAN and not await _words_shown_or_waiting(session, user.id):
        await session.execute(delete(ArtisanCraft).where(ArtisanCraft.userId == user.id))
        await session.execute(delete(ArtisanProfile).where(ArtisanProfile.userId == user.id))
    if can(old_role, Capability.BUILD_LESSONS) and not can(new_role, Capability.BUILD_LESSONS):
        await withdraw_lesson_shares(session, user.id, actor=None, cause=ROLE_CHANGED, objects=objects)


async def _words_shown_or_waiting(session: AsyncSession, user_id: uuid.UUID) -> bool:
    found = await session.scalar(
        select(ArtisanContribution.id)
        .where(ArtisanContribution.userId == user_id, ArtisanContribution.status.in_(SHOWN_OR_WAITING))
        .limit(1)
    )
    return found is not None
