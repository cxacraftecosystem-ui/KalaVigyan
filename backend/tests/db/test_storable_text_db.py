from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chunk, Source
from app.services.live_source_store import chunk_for_quote, keep_document
from app.sources.adapter import build_document

from ..research.fixtures import evidence_item
from .quote_visibility_seed import seeded_session

pytestmark = pytest.mark.db

PDF_TEXT = (
    "Calcium and sulphur distribution in red clay brick\x00 by micro X-ray uorescence mapping "
    "L.Gredmaiera,1,\x03 and the kiln\x1b record.\x0cThe bricks were fired at 950 °C."
)
STORED_TEXT = (
    "Calcium and sulphur distribution in red clay brick by micro X-ray uorescence mapping "
    "L.Gredmaiera,1, and the kiln record. The bricks were fired at 950 °C."
)
QUOTE = "mapping L.Gredmaiera,1,\x03 and the kiln record"
PDF_ITEM = evidence_item(
    id="core:4242",
    adapter="core",
    url="https://core.ac.uk/works/4242",
    title="Calcium and sulphur distribution\x00 in red clay brick",
    authors=["L. Gredmaier\x03"],
    doi=None,
    quotes=[],
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def test_a_pdf_with_nul_and_control_bytes_is_stored_and_read(session: AsyncSession) -> None:
    source_id = await keep_document(session, build_document(PDF_ITEM, PDF_TEXT, "FULL_TEXT"))
    await session.flush()
    texts = (await session.scalars(select(Chunk.text).where(Chunk.sourceId == source_id))).all()
    assert texts == [STORED_TEXT]
    source = await session.get(Source, source_id)
    assert source is not None
    assert (source.title, source.authors) == (
        "Calcium and sulphur distribution in red clay brick",
        ["L. Gredmaier"],
    )
    found = await chunk_for_quote(session, source_id, QUOTE)
    assert found is not None
    assert found.locator == "para 1"
