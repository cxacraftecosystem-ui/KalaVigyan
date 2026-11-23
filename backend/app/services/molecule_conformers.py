from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import ExternalFailure
from app.models import Compound
from app.research.base import ContractModel
from app.sources.reference.pubchem import CONFORMER_MAX_BYTES, PubChemAdapter

from .live_sources import LiveSourcesStore
from .naming import molecule_key

__all__ = [
    "CONFORMER_LEAF",
    "CONFORMER_MISS_RECHECK_DAYS",
    "CONFORMER_SCHEMA_VERSION",
    "CONFORMER_TYPE",
    "ConformerCache",
    "ConformerObjects",
    "ConformerRecord",
    "ConformerSource",
    "live_pubchem",
    "stored_compound_cid",
]

logger = logging.getLogger(__name__)

CONFORMER_SCHEMA_VERSION = 1
CONFORMER_LEAF = "conformer.json"
CONFORMER_TYPE = "chemical/x-mdl-sdfile"
RECORD_TYPE = "application/json"
CONFORMER_MISS_RECHECK_DAYS = 90


class ConformerObjects(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...


class ConformerSource(Protocol):
    async def conformer(self, cid: int) -> str | None: ...


class ConformerRecord(ContractModel):
    schema_version: Literal[1]
    pubchem_cid: int = Field(ge=1)
    sdf: str | None = Field(min_length=1, max_length=CONFORMER_MAX_BYTES)
    checked_at: AwareDatetime


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ConformerCache:
    objects: ConformerObjects
    source: ConformerSource
    clock: Callable[[], datetime] = utc_now

    async def conformer(self, cid: int) -> str | None:
        key = molecule_key(cid, CONFORMER_LEAF)
        kept = _kept_record(cid, await self.objects.get(key))
        now = self.clock()
        if kept is not None and not _miss_to_ask_again(kept, now):
            return kept.sdf
        try:
            sdf = await self.source.conformer(cid)
        except ExternalFailure as failure:
            if kept is None:
                raise
            logger.warning(
                "PubChem could not be asked again; the kept miss of CID %s stands: %s", cid, failure
            )
            return kept.sdf
        record = ConformerRecord(
            schema_version=CONFORMER_SCHEMA_VERSION, pubchem_cid=cid, sdf=sdf, checked_at=now
        )
        await self.objects.put(key, record.model_dump_json().encode("utf-8"), content_type=RECORD_TYPE)
        return record.sdf


async def stored_compound_cid(session: AsyncSession, cid: int) -> bool:
    found = await session.scalar(select(Compound.id).where(Compound.pubchemCid == cid).limit(1))
    return found is not None


async def live_pubchem(live: LiveSourcesStore, sessions: async_sessionmaker[AsyncSession]) -> PubChemAdapter:
    return await live.reference(sessions, PubChemAdapter)


def _miss_to_ask_again(record: ConformerRecord, now: datetime) -> bool:
    return record.sdf is None and now - record.checked_at > timedelta(days=CONFORMER_MISS_RECHECK_DAYS)


def _kept_record(cid: int, raw: bytes | None) -> ConformerRecord | None:
    if raw is None:
        return None
    try:
        record = ConformerRecord.model_validate_json(raw)
    except ValidationError as error:
        logger.error("the stored conformer of CID %s is off its shape and is fetched again: %s", cid, error)
        return None
    if record.pubchem_cid != cid:
        logger.error(
            "the stored conformer of CID %s holds CID %s and is fetched again", cid, record.pubchem_cid
        )
        return None
    return record
