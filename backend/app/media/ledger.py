from __future__ import annotations

from app.providers.quota import LedgerEntry

from .records import JobRecord

__all__ = ["LEDGER_REF_TYPE", "refund_entry", "unit_entry"]

LEDGER_REF_TYPE = "MediaJob"


def unit_entry(job: JobRecord) -> LedgerEntry:
    return LedgerEntry(
        user_id=job.requested_by,
        resource=job.kind,
        units=1,
        key=f"media:{job.id}",
        ref_type=LEDGER_REF_TYPE,
        ref_id=str(job.id),
    )


def refund_entry(job: JobRecord) -> LedgerEntry:
    return LedgerEntry(
        user_id=job.requested_by,
        resource=job.kind,
        units=-1,
        key=f"media-refund:{job.id}",
        ref_type=LEDGER_REF_TYPE,
        ref_id=str(job.id),
        counted_at=job.created_at,
    )
