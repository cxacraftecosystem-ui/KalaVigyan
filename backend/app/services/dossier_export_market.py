from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from app.core.errors import InvalidInput
from app.curation.dossier import Dossier
from app.curation.entities import Place
from app.curation.records import GiRecord, Market, Price, Workforce

from .curation_keys import curated_id
from .dossier_export_records import Row, StoredCuration, guided, id_number, keyed

__all__ = ["stored_market"]


def stored_market(
    stored: StoredCuration, keys: Mapping[uuid.UUID, str], places: Sequence[Place], previous: Dossier | None
) -> Market:
    earlier = previous.market if previous else Market()
    prices = [_price(stored.slug, row, keys, places) for row in stored.market.prices]
    workforce = [
        Workforce(claim_id=keyed([row["claimId"]], keys)[0], year=row["year"])
        for row in stored.market.workforce
    ]
    gi = stored.market.gi
    return Market(
        gi=_gi(gi, keys),
        imitation=keyed(gi["imitationClaimIds"] or [], keys) if gi is not None else [],
        prices=guided(
            prices,
            lambda item: (item.claim_id, item.date, item.place_id),
            [[(item.claim_id, item.date, item.place_id) for item in earlier.prices]],
            lambda item: (id_number(item.claim_id), item.date, item.place_id),
        ),
        workforce=guided(
            workforce,
            lambda item: (item.claim_id, item.year),
            [[(item.claim_id, item.year) for item in earlier.workforce]],
            lambda item: (id_number(item.claim_id), item.year),
        ),
    )


def _gi(row: Row | None, keys: Mapping[uuid.UUID, str]) -> GiRecord | None:
    if row is None:
        return None
    return GiRecord(
        application_number=row["applicationNumber"],
        certificate_number=row["certificateNumber"],
        filed_on=row["filedOn"],
        registered_on=row["registeredOn"],
        journal_issue=row["journalIssue"],
        proprietors=list(row["proprietors"] or []),
        authorised_user_count=row["authorisedUserCount"],
        claim_ids=keyed(row["claimIds"], keys),
    )


def _price(slug: str, row: Row, keys: Mapping[uuid.UUID, str], places: Sequence[Place]) -> Price:
    claim = keyed([row["claimId"]], keys)[0]
    date = row["pricedOn"]
    place = next(
        (
            place.id
            for place in places
            if place.name == row["placeName"]
            and curated_id(slug, "price", claim, place.id, date) == row["id"]
        ),
        None,
    )
    if place is None:
        raise InvalidInput(
            f"the price of claim {claim} names {row['placeName']}, which is not a place of {slug}"
        )
    return Price(claim_id=claim, date=date, place_id=place)
