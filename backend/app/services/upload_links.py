from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import token_matches_user
from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.core.security import TOKEN_VERSION_CLAIM
from app.models import Craft, ImageContribution, UploadLink, User
from app.research.image_contributions import ImageDeclaration
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.upload_links import (
    LINK_PREFIX,
    OPEN,
    OPEN_LINKS_MAX,
    SLOT_PREFIX,
    UPLOAD_LINK_LIFETIME,
    USED,
    SlotCraft,
    SlotDeclaration,
    SlotFact,
    SlotMaterial,
    SlotStage,
    UploadLinkView,
    UploadSlot,
    declared,
    link_state,
)

from . import image_contributions as images, knowledge_view
from .image_contributions_checks import checked_craft, checked_target, material_name, stage_name
from .image_screens import Screened, ScreenTools, screened
from .oauth_tokens import new_secret, stored_secret
from .object_store import ObjectStore

__all__ = [
    "IssuedLink",
    "LinkGone",
    "LinkRefused",
    "Picture",
    "UnknownLink",
    "fill_by_link",
    "fill_slot",
    "link_view",
    "renew_link",
    "start_upload",
]

NEEDS_PROPOSER = "Giving pictures needs an account of Researcher or above."
TOO_MANY = f"This account holds {OPEN_LINKS_MAX} open upload links. Use one, or wait for them to expire."
USED_DETAIL = "This upload link was used already. Ask for a new one."
EXPIRED_DETAIL = "This upload link has expired. Ask for a new one."
STILL_OPEN = "This upload link still works. Use it."
ACCOUNT_CHANGED = "This upload link no longer works: its account signed out or changed. Ask for a new one."
NO_FACT = "No shown fact has the id {claim_id}"


class UnknownLink(Exception):
    pass


class LinkGone(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class LinkRefused(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class IssuedLink:
    link_token: str
    slot_token: str | None
    expires_at: datetime
    craft: SlotCraft
    stage: SlotStage | None
    facts: list[SlotFact]
    material: SlotMaterial | None = None
    slot: str | None = None
    task_key: str | None = None


@dataclass(frozen=True)
class Picture:
    declaration: SlotDeclaration
    data: bytes


@dataclass(frozen=True)
class Filling:
    objects: ObjectStore
    tools: ScreenTools
    now: datetime


async def start_upload(
    session: AsyncSession,
    user: User,
    slot: UploadSlot,
    declaration: SlotDeclaration | None,
    *,
    now: datetime,
) -> IssuedLink:
    if not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    if declaration is not None:
        _checked(slot, declaration)
    await _refuse_too_many(session, user.id, now)
    craft = await checked_craft(session, slot.craft_slug)
    aimed = await checked_target(session, craft, slot)
    facts = await _facts(session, aimed.claim_ids)
    link = new_secret(LINK_PREFIX)
    slot_token = None if declaration is None else new_secret(SLOT_PREFIX)
    row = UploadLink(
        userId=user.id,
        userTokenVersion=int(user.tokenVersion or 0),
        craftId=craft.id,
        stageId=aimed.stage_id,
        materialId=aimed.material_id,
        slot=aimed.slot,
        taskKey=aimed.task_key,
        claimIds=list(aimed.claim_ids),
        linkHash=_digest(link, LINK_PREFIX),
        slotHash=None if slot_token is None else _digest(slot_token, SLOT_PREFIX),
        declaration=None if declaration is None else declaration.model_dump(mode="json", by_alias=True),
        expiresAt=now + UPLOAD_LINK_LIFETIME,
        createdAt=now,
    )
    session.add(row)
    await session.flush()
    return await _issued(session, row, craft, (link, slot_token), facts)


async def link_view(session: AsyncSession, user: User, token: str, *, now: datetime) -> UploadLinkView:
    row = await _own_link(session, user, token, lock=False)
    craft = await session.get(Craft, row.craftId)
    if craft is None:
        raise UnknownLink(token)
    return UploadLinkView(
        state=link_state(used_at=row.usedAt, expires_at=row.expiresAt, now=now),
        craft=SlotCraft(slug=craft.slug, name=craft.name),
        stage=await _stage(session, row),
        material=await _material(session, row),
        slot=row.slot,
        task_key=row.taskKey,
        facts=await _shown_facts(session, list(row.claimIds)),
        expires_at=row.expiresAt,
        contribution_id=row.contributionId,
    )


async def renew_link(session: AsyncSession, user: User, token: str, *, now: datetime) -> IssuedLink:
    row = await _own_link(session, user, token, lock=True)
    if link_state(used_at=row.usedAt, expires_at=row.expiresAt, now=now) == OPEN:
        raise LinkRefused(STILL_OPEN)
    return await start_upload(session, user, await _slot_of(session, row, token), None, now=now)


async def fill_by_link(
    session: AsyncSession, user: User, token: str, picture: Picture, *, filling: Filling
) -> ImageContribution:
    row = await _own_link(session, user, token, lock=False)
    _require_open(row, filling.now)
    slot = await _slot_of(session, row, token)
    declaration = _checked(slot, picture.declaration)
    screen = await screened(session, picture.data, origin=declaration.origin, user=user, tools=filling.tools)
    locked = await _own_link(session, user, token, lock=True)
    return await _fill(session, locked, user, (declaration, screen), filling=filling)


async def fill_slot(session: AsyncSession, token: str, data: bytes, *, filling: Filling) -> ImageContribution:
    digest = stored_secret(token, SLOT_PREFIX)
    if digest is None:
        raise UnknownLink(token)
    user, declaration = await _slot_owner(
        session, await _by_slot(session, digest, lock=False), token, filling.now
    )
    screen = await screened(session, data, origin=declaration.origin, user=user, tools=filling.tools)
    locked = await _by_slot(session, digest, lock=True)
    if locked is None:
        raise UnknownLink(token)
    return await _fill(session, locked, user, (declaration, screen), filling=filling)


async def _slot_owner(
    session: AsyncSession, row: UploadLink | None, token: str, now: datetime
) -> tuple[User, ImageDeclaration]:
    if row is None or row.declaration is None:
        raise UnknownLink(token)
    _require_open(row, now)
    user = await session.get(User, row.userId)
    if user is None or not _owner_live(row, user) or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise LinkGone(ACCOUNT_CHANGED)
    slot = await _slot_of(session, row, token)
    return user, _checked(slot, SlotDeclaration.model_validate(row.declaration))


async def _fill(
    session: AsyncSession,
    row: UploadLink,
    user: User,
    given: tuple[ImageDeclaration, Screened],
    *,
    filling: Filling,
) -> ImageContribution:
    declaration, screen = given
    _require_open(row, filling.now)
    contribution = await images.declare(session, user, declaration, now=filling.now)
    received = await images.store_screened(
        session, contribution.id, user, screen, objects=filling.objects, now=filling.now
    )
    row.usedAt, row.contributionId = filling.now, received.id
    await session.flush()
    return received


async def _issued(
    session: AsyncSession,
    row: UploadLink,
    craft: Craft,
    tokens: tuple[str, str | None],
    facts: list[SlotFact],
) -> IssuedLink:
    link, slot_token = tokens
    return IssuedLink(
        link_token=link,
        slot_token=slot_token,
        expires_at=row.expiresAt,
        craft=SlotCraft(slug=craft.slug, name=craft.name),
        stage=await _stage(session, row),
        facts=facts,
        material=await _material(session, row),
        slot=row.slot,
        task_key=row.taskKey,
    )


async def _slot_of(session: AsyncSession, row: UploadLink, token: str) -> UploadSlot:
    craft = await session.get(Craft, row.craftId)
    if craft is None:
        raise UnknownLink(token)
    return UploadSlot(
        craft_slug=craft.slug,
        stage_id=row.stageId,
        material_id=row.materialId,
        slot=row.slot,
        task_key=row.taskKey,
        claim_ids=list(row.claimIds),
    )


def _checked(slot: UploadSlot, declaration: SlotDeclaration) -> ImageDeclaration:
    try:
        return declared(slot, declaration)
    except ValidationError as refused:
        raise InvalidInput("; ".join(str(problem["msg"]) for problem in refused.errors())) from None


def _require_open(row: UploadLink, now: datetime) -> None:
    state = link_state(used_at=row.usedAt, expires_at=row.expiresAt, now=now)
    if state == USED:
        raise LinkGone(USED_DETAIL)
    if state != OPEN:
        raise LinkGone(EXPIRED_DETAIL)


def _owner_live(row: UploadLink, user: User) -> bool:
    claims = {TOKEN_VERSION_CLAIM: row.userTokenVersion, "iat": row.createdAt.timestamp()}
    return token_matches_user(claims, user)


async def _own_link(session: AsyncSession, user: User, token: str, *, lock: bool) -> UploadLink:
    digest = stored_secret(token, LINK_PREFIX)
    row = None if digest is None else await _found(session, UploadLink.linkHash == digest, lock=lock)
    if row is None or row.userId != user.id:
        raise UnknownLink(token)
    return row


async def _by_slot(session: AsyncSession, digest: str, *, lock: bool) -> UploadLink | None:
    return await _found(session, UploadLink.slotHash == digest, lock=lock)


async def _found(session: AsyncSession, condition: ColumnElement[bool], *, lock: bool) -> UploadLink | None:
    query = select(UploadLink).where(condition)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


async def _refuse_too_many(session: AsyncSession, user_id: uuid.UUID, now: datetime) -> None:
    held = await session.scalar(
        select(func.count())
        .select_from(UploadLink)
        .where(UploadLink.userId == user_id, UploadLink.usedAt.is_(None), UploadLink.expiresAt > now)
    )
    if int(held or 0) >= OPEN_LINKS_MAX:
        raise InvalidInput(TOO_MANY)


async def _stage(session: AsyncSession, row: UploadLink) -> SlotStage | None:
    if row.stageId is None:
        return None
    name = await stage_name(session, row.craftId, row.stageId)
    return None if name is None else SlotStage(id=row.stageId, name=name)


async def _material(session: AsyncSession, row: UploadLink) -> SlotMaterial | None:
    if row.materialId is None:
        return None
    name = await material_name(session, row.craftId, row.materialId)
    return None if name is None else SlotMaterial(id=row.materialId, name=name)


async def _facts(session: AsyncSession, claim_ids: list[uuid.UUID]) -> list[SlotFact]:
    shown = await _shown_facts(session, claim_ids)
    found = {fact.id for fact in shown}
    missing = [claim_id for claim_id in claim_ids if claim_id not in found]
    if missing:
        raise InvalidInput(NO_FACT.format(claim_id=missing[0]))
    return shown


async def _shown_facts(session: AsyncSession, claim_ids: list[uuid.UUID]) -> list[SlotFact]:
    shown, _ = await knowledge_view.claims_by_id(session, claim_ids, acls=OPEN_CHUNK_ACLS)
    return [SlotFact(id=claim_id, text=shown[claim_id].text) for claim_id in claim_ids if claim_id in shown]


def _digest(token: str, prefix: str) -> str:
    digest = stored_secret(token, prefix)
    if digest is None:
        raise ValueError(f"a new secret starts with {prefix}")
    return digest
