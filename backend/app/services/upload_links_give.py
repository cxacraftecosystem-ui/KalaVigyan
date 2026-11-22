from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Craft, ImageContribution, PictureDeclaration, User
from app.research.image_contributions import BatchPicture, ImageDeclaration, SharedDeclaration, shown_label
from app.research.image_contributions_give import GivenPicture, GivenPictures, given_next_step
from app.research.image_intake_pixels import fingerprint_distance
from app.research.image_screens import NEAR_IDENTICAL_BITS, ScreenTools
from app.research.upload_links import SlotCraft

from . import image_contributions as images
from .image_contributions_checks import check_claims, checked_craft, checked_target
from .image_contributions_errors import ContributionRefused
from .image_screens import Screened, screened
from .object_store import ObjectStore

__all__ = ["MCP_CHANNEL", "GivenFile", "Giving", "Handing", "give_pictures"]

MCP_CHANNEL = "MCP"
REPEATED = "The same picture is given twice in this call"


@dataclass(frozen=True)
class GivenFile:
    position: int
    picture: BatchPicture
    data: bytes | None
    refused: str | None = None


@dataclass(frozen=True)
class Giving:
    craft_slug: str
    shared: SharedDeclaration
    confirmation: str
    files: list[GivenFile]


@dataclass(frozen=True)
class Handing:
    objects: ObjectStore
    tools: ScreenTools
    now: datetime


@dataclass(frozen=True)
class _Accepted:
    given: GivenFile
    declaration: ImageDeclaration
    screen: Screened


@dataclass
class _Batch:
    user: User
    craft: Craft
    giving: Giving
    accepted: list[_Accepted] = field(default_factory=list)


async def give_pictures(
    session: AsyncSession, user: User, giving: Giving, *, handing: Handing
) -> GivenPictures:
    batch = _Batch(user, await checked_craft(session, giving.craft_slug), giving)
    craft = batch.craft
    outcomes: dict[int, GivenPicture] = {}
    for given in giving.files:
        try:
            batch.accepted.append(await _screened_file(session, batch, given, handing.tools))
        except (InvalidInput, ContributionRefused) as refused:
            outcomes[given.position] = GivenPicture(position=given.position, refused=_detail(refused))
    record = await _filed(session, batch, handing)
    for item, row in record:
        outcomes[item.given.position] = _outcome(item, row)
    pictures = [outcomes[position] for position in sorted(outcomes)]
    approved = sum(picture.status == "APPROVED" for picture in pictures)
    return GivenPictures(
        craft=SlotCraft(slug=craft.slug, name=craft.name),
        declaration_id=record[0][1].declarationId if record else None,
        given=len(record),
        refused=len(pictures) - len(record),
        pictures=pictures,
        next_step=given_next_step(len(record), approved),
    )


async def _screened_file(
    session: AsyncSession, batch: _Batch, given: GivenFile, tools: ScreenTools
) -> _Accepted:
    if given.refused is not None or given.data is None:
        raise InvalidInput(given.refused or "The picture did not arrive")
    declaration = _declared(batch.craft, batch.giving.shared, given.picture)
    aimed = await checked_target(session, batch.craft, declaration)
    await check_claims(session, aimed.claim_ids)
    screen = await screened(session, given.data, origin=aimed.origin, user=batch.user, tools=tools)
    if any(_same(screen, earlier.screen) for earlier in batch.accepted):
        raise ContributionRefused(REPEATED)
    return _Accepted(given, aimed, screen)


async def _filed(
    session: AsyncSession, batch: _Batch, handing: Handing
) -> list[tuple[_Accepted, ImageContribution]]:
    user, giving, accepted = batch.user, batch.giving, batch.accepted
    if not accepted:
        return []
    record = PictureDeclaration(
        contributorId=user.id,
        craftId=batch.craft.id,
        channel=MCP_CHANNEL,
        origin=giving.shared.origin,
        generator=giving.shared.generator,
        termsVersion=giving.shared.terms_version,
        rightsConfirmedAt=handing.now,
        confirmation=giving.confirmation,
        pictures=len(accepted),
    )
    session.add(record)
    await session.flush()
    filed = []
    for item in accepted:
        row = await images.declare(session, user, item.declaration, now=handing.now, declaration_id=record.id)
        stored = await images.store_screened(
            session, row.id, user, item.screen, objects=handing.objects, now=handing.now
        )
        filed.append((item, stored))
    return filed


def _declared(craft: Craft, shared: SharedDeclaration, picture: BatchPicture) -> ImageDeclaration:
    try:
        return picture.declared(craft.slug, shared)
    except ValidationError as refused:
        raise InvalidInput("; ".join(str(problem["msg"]) for problem in refused.errors())) from None


def _same(screen: Screened, earlier: Screened) -> bool:
    if screen.digest == earlier.digest:
        return True
    if screen.fingerprint is None or earlier.fingerprint is None:
        return False
    return fingerprint_distance(screen.fingerprint, earlier.fingerprint) <= NEAR_IDENTICAL_BITS


def _outcome(item: _Accepted, row: ImageContribution) -> GivenPicture:
    image = item.screen.image
    return GivenPicture(
        position=item.given.position,
        contribution_id=row.id,
        status=row.status,
        label=shown_label(row.origin, row.generator),
        received=image.received,
        mime=image.mime,
        width=image.width,
        height=image.height,
        screen=item.screen.summary(),
    )


def _detail(refused: InvalidInput | ContributionRefused) -> str:
    return refused.detail if isinstance(refused, ContributionRefused) else str(refused)
