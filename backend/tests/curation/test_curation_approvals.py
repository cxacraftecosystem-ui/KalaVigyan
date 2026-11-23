from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from app.services.curation_approvals import ApprovedStructure, HeldClaim, missing_approvals

DAY = date(2026, 11, 20)
NAME = HeldClaim(
    uuid.UUID(int=161), "C161", "Printers in the delta call the cloth ajrak, after their word for blue."
)
FIRST = HeldClaim(uuid.UUID(int=12), "C012", "A natural indigo vat ferments for ten days.")
SECOND = HeldClaim(uuid.UUID(int=14), "C014", "A natural indigo vat ferments for a month.")
NATIVE = ApprovedStructure("NATIVE_NAME", DAY, (NAME,))
CONFLICT = ApprovedStructure("CONFLICT", DAY, (FIRST, SECOND))


def planned(claim: HeldClaim, *, text: str | None = None, differ: bool = False) -> dict[str, Any]:
    return {"id": claim.id, "text": text or claim.text, "sourcesDiffer": differ}


def test_a_file_holding_every_approved_fact_and_conflict_as_stored_is_not_behind() -> None:
    rows = [planned(NAME), planned(FIRST, differ=True), planned(SECOND, differ=True)]
    assert missing_approvals([NATIVE, CONFLICT], rows) == ()


def test_a_file_without_an_approved_fact_names_its_key_kind_and_day() -> None:
    assert missing_approvals([NATIVE], [planned(FIRST)]) == (
        "C161 (native name, approved 2026-11-20) is held by the database and not by this file",
    )


def test_a_file_wording_an_approved_fact_otherwise_is_behind() -> None:
    rows = [planned(NAME, text="Printers call the cloth ajrak.")]
    assert missing_approvals([NATIVE], rows) == (
        "C161 (native name, approved 2026-11-20) is worded otherwise in this file than the database holds it",
    )


def test_a_file_that_does_not_mark_an_approved_conflict_names_its_facts() -> None:
    rows = [planned(FIRST, differ=True), planned(SECOND)]
    assert missing_approvals([CONFLICT], rows) == (
        "the conflict between C012 and C014 (approved 2026-11-20) is held by the database and not by this file",
    )
