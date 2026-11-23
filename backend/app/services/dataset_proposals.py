from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import token_matches_user
from app.core.errors import ExternalFailure, InvalidInput
from app.core.roles import Capability, can
from app.core.security import TOKEN_VERSION_CLAIM
from app.models import DatasetTable, DatasetUpload, EnvDataset, MapLayerProposal, User
from app.research.dataset_proposals import (
    DATASET_UPLOAD_LIFETIME,
    SLOT_PREFIX,
    DatasetProposal,
    ParsedTable,
    TableRefused,
    parsed_table,
    record_problems,
)
from app.research.fetcher import Fetcher, FetchRefused, FetchRequest
from app.research.map_layer_geojson import LayerRefused, ParsedLayer, parsed_layer

from .dataset_registry import CONTRIBUTED, dataset_registry
from .oauth_tokens import new_secret, stored_secret

__all__ = [
    "IssuedSlot",
    "SlotGone",
    "StoredDataset",
    "UnknownSlot",
    "fill_dataset_slot",
    "issue_dataset_slot",
    "proposal_problems",
]

NEEDS_PROPOSER = "Proposing a dataset needs an account of Researcher or above."
TAKEN = "the code {code} names a dataset the site already holds; give a code of its own"
UNREACHABLE = "the landing page {url} could not be read: give the dataset's own public page"
USED = "This upload slot was used already. Call propose_dataset again for a new one."
EXPIRED = "This upload slot has expired. Call propose_dataset again for a new one."
ACCOUNT_CHANGED = "This upload slot no longer works: its account signed out or changed."
WRONG_FILE = "the file's SHA-256 is {found}, not the {declared} the proposal declared"
PENDING_LAYER = "PENDING"


class UnknownSlot(Exception):
    pass


class SlotGone(Exception):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class IssuedSlot:
    token: str
    expires_at: datetime


@dataclass(frozen=True)
class StoredDataset:
    dataset: EnvDataset
    table: ParsedTable | None = None
    layer: ParsedLayer | None = None


async def proposal_problems(session: AsyncSession, fetcher: Fetcher, proposal: DatasetProposal) -> list[str]:
    problems = record_problems(proposal)
    held = await session.scalar(select(EnvDataset.id).where(EnvDataset.code == proposal.code))
    if held is not None or proposal.code in dataset_registry():
        problems.append(TAKEN.format(code=proposal.code))
    try:
        await fetcher.fetch(FetchRequest(url=proposal.landing_url))
    except FetchRefused, ExternalFailure:
        problems.append(UNREACHABLE.format(url=proposal.landing_url))
    return problems


async def issue_dataset_slot(
    session: AsyncSession, user: User, proposal: DatasetProposal, *, now: datetime
) -> IssuedSlot:
    if not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    token = new_secret(SLOT_PREFIX)
    digest = stored_secret(token, SLOT_PREFIX)
    if digest is None:
        raise InvalidInput("The upload slot could not be issued")
    expires_at = now + DATASET_UPLOAD_LIFETIME
    session.add(
        DatasetUpload(
            userId=user.id,
            userTokenVersion=int(user.tokenVersion or 0),
            slotHash=digest,
            record=proposal.model_dump(mode="json", by_alias=True),
            sha256=proposal.sha256,
            expiresAt=expires_at,
        )
    )
    await session.flush()
    return IssuedSlot(token=token, expires_at=expires_at)


async def fill_dataset_slot(
    session: AsyncSession, token: str, data: bytes, *, now: datetime
) -> StoredDataset:
    digest = stored_secret(token, SLOT_PREFIX)
    row = None if digest is None else await _slot(session, digest)
    if row is None:
        raise UnknownSlot(token)
    user = await _live_owner(session, row, now)
    found = hashlib.sha256(data).hexdigest()
    if found != row.sha256:
        raise InvalidInput(WRONG_FILE.format(found=found, declared=row.sha256))
    proposal = DatasetProposal.model_validate(row.record)
    parsed = _parsed(data, proposal)
    if await session.scalar(select(EnvDataset.id).where(EnvDataset.code == proposal.code)) is not None:
        raise InvalidInput(TAKEN.format(code=proposal.code))
    dataset = _dataset_row(proposal, user, now)
    session.add(dataset)
    await session.flush()
    stored = _with_file(session, dataset, proposal, (parsed, data))
    row.usedAt = now
    row.datasetId = dataset.id
    await session.flush()
    return stored


def _with_file(
    session: AsyncSession,
    dataset: EnvDataset,
    proposal: DatasetProposal,
    read: tuple[ParsedTable | ParsedLayer, bytes],
) -> StoredDataset:
    parsed, data = read
    if isinstance(parsed, ParsedLayer):
        session.add(_layer_row(dataset, proposal, parsed, data))
        return StoredDataset(dataset=dataset, layer=parsed)
    session.add(_table_row(dataset, parsed, data))
    return StoredDataset(dataset=dataset, table=parsed)


def _parsed(data: bytes, proposal: DatasetProposal) -> ParsedTable | ParsedLayer:
    try:
        return parsed_table(data) if proposal.layer is None else parsed_layer(data, proposal.layer)
    except (TableRefused, LayerRefused) as refused:
        what = "table" if proposal.layer is None else "layer"
        raise InvalidInput(f"The {what} was not stored: {refused}") from None


async def _slot(session: AsyncSession, digest: str) -> DatasetUpload | None:
    query = select(DatasetUpload).where(DatasetUpload.slotHash == digest).with_for_update()
    return await session.scalar(query)


async def _live_owner(session: AsyncSession, row: DatasetUpload, now: datetime) -> User:
    if row.usedAt is not None:
        raise SlotGone(USED)
    if row.expiresAt <= now:
        raise SlotGone(EXPIRED)
    user = await session.get(User, row.userId)
    claims = {TOKEN_VERSION_CLAIM: row.userTokenVersion, "iat": row.createdAt.timestamp()}
    if user is None or not token_matches_user(claims, user) or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise SlotGone(ACCOUNT_CHANGED)
    return user


def _dataset_row(proposal: DatasetProposal, user: User, now: datetime) -> EnvDataset:
    return EnvDataset(
        code=proposal.code,
        title=proposal.title,
        publisher=proposal.publisher,
        edition=proposal.edition,
        version=proposal.version,
        period=proposal.period,
        nativeResolution=proposal.native_resolution,
        crs=proposal.crs,
        licence=proposal.licence,
        licenceUrl=proposal.licence_url,
        attribution=proposal.attribution,
        redistributable=proposal.redistributable,
        citation=proposal.citation,
        doi=proposal.doi,
        landingUrl=proposal.landing_url,
        url=proposal.url,
        retrievedAt=now,
        sha256=proposal.sha256,
        origin=CONTRIBUTED,
        proposedById=user.id,
    )


def _table_row(dataset: EnvDataset, table: ParsedTable, data: bytes) -> DatasetTable:
    return DatasetTable(
        datasetId=dataset.id,
        columns=list(table.columns),
        rows=[list(row) for row in table.rows],
        rowCount=len(table.rows),
        byteSize=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
    )


def _layer_row(
    dataset: EnvDataset, proposal: DatasetProposal, layer: ParsedLayer, data: bytes
) -> MapLayerProposal:
    plan = proposal.layer.model_dump(mode="json", by_alias=True) if proposal.layer is not None else {}
    return MapLayerProposal(
        datasetId=dataset.id,
        proposerId=dataset.proposedById,
        plan=plan,
        layer=layer.layer,
        featureCount=layer.features,
        byteSize=len(data),
        sha256=hashlib.sha256(data).hexdigest(),
        status=PENDING_LAYER,
    )
