from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CraftGiRecord, CraftPrice, CraftWorkforce

__all__ = ["GiFacts", "MarketFacts", "PriceFact", "WorkforceFact", "market_facts", "market_from_rows"]

Row = Mapping[str, Any]


@dataclass(frozen=True)
class GiFacts:
    application_number: str | None
    certificate_number: str | None
    filed_on: str | None
    registered_on: str | None
    journal_issue: str | None
    proprietors: tuple[str, ...]
    authorised_user_count: int | None
    claim_ids: tuple[uuid.UUID, ...]
    imitation_claim_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class PriceFact:
    claim_id: uuid.UUID
    priced_on: str
    place_name: str


@dataclass(frozen=True)
class WorkforceFact:
    claim_id: uuid.UUID
    year: int


@dataclass(frozen=True)
class MarketFacts:
    gi: GiFacts | None = None
    prices: tuple[PriceFact, ...] = ()
    workforce: tuple[WorkforceFact, ...] = ()


def market_from_rows(gi: Iterable[Row], prices: Iterable[Row], workforce: Iterable[Row]) -> MarketFacts:
    records = [_gi(row) for row in gi]
    if len(records) > 1:
        raise ValueError("a craft has one GI record at most")
    return MarketFacts(
        gi=records[0] if records else None,
        prices=tuple(
            sorted(
                (PriceFact(row["claimId"], row["pricedOn"], row["placeName"]) for row in prices),
                key=lambda price: (price.priced_on, price.place_name, str(price.claim_id)),
            )
        ),
        workforce=tuple(
            sorted(
                (WorkforceFact(row["claimId"], row["year"]) for row in workforce),
                key=lambda entry: (entry.year, str(entry.claim_id)),
            )
        ),
    )


async def market_facts(session: AsyncSession, craft_id: uuid.UUID) -> MarketFacts:
    tables = (CraftGiRecord, CraftPrice, CraftWorkforce)
    found = [
        (await session.execute(select(table.__table__).where(table.craftId == craft_id))).mappings().all()
        for table in tables
    ]
    return market_from_rows(*found)


def _gi(row: Row) -> GiFacts:
    return GiFacts(
        application_number=row["applicationNumber"],
        certificate_number=row["certificateNumber"],
        filed_on=row["filedOn"],
        registered_on=row["registeredOn"],
        journal_issue=row["journalIssue"],
        proprietors=tuple(row["proprietors"]),
        authorised_user_count=row["authorisedUserCount"],
        claim_ids=tuple(row["claimIds"]),
        imitation_claim_ids=tuple(row.get("imitationClaimIds") or ()),
    )
