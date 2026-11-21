from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim
from app.research.candidate_gates import Candidate
from app.research.write_back import ClaimWriteBack
from app.services.candidate_gates import GateRun
from app.services.claim_writer import SqlClaimWriter
from app.services.write_back_gates import record_write_back_runs

from ..composer.fixtures import ABSTRACT_ITEM
from .write_back_seed import ZELVAR, seeded_session

pytestmark = pytest.mark.db

SECTION_FIELD = "CHEMISTRY"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


def chemistry_claim() -> ClaimWriteBack:
    return ClaimWriteBack.model_validate(
        {
            "craftSlug": ZELVAR.slug,
            "subject": {"conceptType": "MATERIAL", "conceptName": "Alum"},
            "field": SECTION_FIELD,
            "predicate": "states",
            "text": "Alum binds the red dye to the Zelvar cloth.",
            "label": "INFERRED",
            "levelReason": "test",
            "citations": [
                {"evidence": ABSTRACT_ITEM, "quote": None, "quoteCheck": "NA", "relation": "CONTEXTUAL"}
            ],
            "foundBy": "BACKGROUND",
        }
    )


async def test_a_written_back_claim_carries_its_section_s_field_from_its_one_insert(
    session: AsyncSession,
) -> None:
    claim = chemistry_claim()
    (result,) = await SqlClaimWriter(session).write([claim])
    assert result.created
    stored = await session.get(Claim, result.claim_id)
    assert stored is not None and (stored.field, stored.fields) == (SECTION_FIELD, [])
    run = GateRun(Candidate(ref=claim.dedupe_key, statement=claim.text, field="BOTANY"), ())
    vectored = await record_write_back_runs(
        session, [result], {claim.dedupe_key: run}, live=False, checked_at=datetime.now(UTC)
    )
    await session.refresh(stored)
    assert (vectored, stored.field) == (0, SECTION_FIELD)
