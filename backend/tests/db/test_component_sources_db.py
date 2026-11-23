import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgePiece, Source
from app.research.blocks_component import ComponentBlock
from app.research.citations import SourceRef
from app.services import knowledge_view
from app.services.category_import import import_categories
from app.services.curation_import import import_curation
from app.services.monograph_document import monograph_content
from app.services.monograph_load import load_monograph

from ..contracts.blocks_golden import COMPONENT, BlocksFixture
from ..contracts.golden import golden_json
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)
AJRAKH = "Kutch-Ajrakh"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


def recorded() -> tuple[ComponentBlock, list[SourceRef]]:
    fixture = BlocksFixture.model_validate(golden_json(COMPONENT))
    (block,) = fixture.sections[0].blocks
    assert isinstance(block, ComponentBlock)
    return block, fixture.sources


async def stored_refs(session: AsyncSession, source_ids: list[str]) -> list[SourceRef]:
    rows = await session.scalars(select(Source).where(Source.id.in_([uuid.UUID(sid) for sid in source_ids])))
    refs = {str(row.id): SourceRef.model_validate(knowledge_view.source_ref(row)) for row in rows.all()}
    return [refs[sid] for sid in source_ids]


async def test_the_red_player_rests_on_the_sources_the_monograph_load_records(session: AsyncSession) -> None:
    await import_curation(session)
    await import_categories(session)
    await load_monograph(session, monograph_content(AJRAKH), now=NOW)
    block, sources = recorded()
    piece = await session.scalar(select(KnowledgePiece).where(KnowledgePiece.label == block.label))
    assert piece is not None
    assert (piece.kind, piece.title, piece.payload["anchor"]) == (
        block.component_kind,
        block.title,
        "#rp-red",
    )
    assert list(piece.sourceIds) == [source.source_id for source in block.sources]
    assert await stored_refs(session, list(piece.sourceIds)) == sources
