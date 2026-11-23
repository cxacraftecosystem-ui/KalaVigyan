import copy
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Chunk, Claim, ClaimSource, Concept, Craft, FieldRecording, FieldVoiceStream
from app.research.retrieval import PASSAGE_CHUNK_KIND, PUBLIC_CHUNK_ACL
from app.services.field_voices_feed import FieldVoicesPage, parse_page
from app.services.field_voices_ledger import SqlFieldVoicesLedger
from app.services.field_voices_reader import field_voices_reader
from app.services.field_voices_store import ApplyContext
from app.services.field_voices_sync import sync_portal
from tests.field_voices.fakes import FakeClock, FakeCopier
from tests.field_voices.fixtures import FR, caught_up, enabled_settings, portal_transport, recorded, resigned

WEB = "https://kalavigyan.example.org"
API = "https://api.kalavigyan.example.org"
AJRAKH = "Kutch-Ajrakh"
DIMENSIONS = 1536


class KeptStore:
    def __init__(self) -> None:
        self.deleted: list[str] = []

    async def delete(self, key: str) -> None:
        self.deleted.append(key)


async def fake_embed(texts: list[str]) -> list[list[float]]:
    return [[0.001 * (index + 1)] * DIMENSIONS for index, _ in enumerate(texts)]


@asynccontextmanager
async def rolled_back() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def ledger_for(session: AsyncSession, store: KeptStore) -> SqlFieldVoicesLedger:
    @asynccontextmanager
    async def same_session() -> AsyncIterator[AsyncSession]:
        yield session

    context = ApplyContext(now=datetime.now(UTC), web_base=WEB, api_base=API)
    return SqlFieldVoicesLedger(same_session, embed=fake_embed, store=store, context=context)


async def synced(session: AsyncSession, store: KeptStore) -> dict[str, Any]:
    reader = field_voices_reader(enabled_settings(), FR, transport=portal_transport(caught_up(FR)))
    report = await sync_portal(reader, ledger_for(session, store), FakeCopier(), clock=FakeClock().clock())
    return report.as_dict()


async def ajrakh(session: AsyncSession) -> Craft:
    craft = await session.scalar(select(Craft).where(Craft.slug == AJRAKH))
    assert craft is not None, "the craft catalogue is seeded before the database tests"
    return craft


async def count(session: AsyncSession, model: Any, *where: Any) -> int:
    return int(await session.scalar(select(func.count()).select_from(model).where(*where)) or 0)


def page_of(stream: str, view: str, cursor: str | None, changes: list[dict[str, Any]]) -> FieldVoicesPage:
    payload = {
        "schemaVersion": 2,
        "portal": FR,
        "generatedAt": "2026-11-18T03:00:00Z",
        "stream": stream,
        "view": view,
        "cursor": cursor,
        "nextCursor": f"{cursor or 'start'}-after",
        "hasMore": False,
        "changes": changes,
    }
    return parse_page(payload, portal=FR, asked=(stream, view, cursor))


async def gone_page(session: AsyncSession, stream: str, item_id: str) -> FieldVoicesPage:
    row = await session.get(FieldVoiceStream, (FR, stream.upper()))
    tombstone = {
        "state": "GONE",
        "id": item_id,
        "updatedAt": "2026-11-18T02:59:00.000001Z",
        "reason": "WITHDRAWN",
        "successorId": None,
    }
    return page_of(stream, "gone", row.goneCursor if row else None, [tombstone])


def recorded_recording(changes: Any = None) -> dict[str, Any]:
    change = copy.deepcopy(recorded("field-transcripts-all-1")["changes"][0])
    if changes is not None:
        changes(change)
    change["updatedAt"] = "2026-11-18T04:00:00.000001Z"
    return resigned(change)


async def stored_recording(session: AsyncSession, media_id: str = "fr-media-1") -> FieldRecording:
    recording = await session.scalar(
        select(FieldRecording)
        .where(FieldRecording.portal == FR, FieldRecording.portalMediaId == media_id)
        .execution_options(populate_existing=True)
    )
    assert recording is not None
    return recording


async def public_chunk(session: AsyncSession, source_id: uuid.UUID, quote: str) -> Chunk:
    rows = await session.scalars(
        select(Chunk)
        .where(Chunk.sourceId == source_id, Chunk.acl == PUBLIC_CHUNK_ACL, Chunk.kind == PASSAGE_CHUNK_KIND)
        .order_by(Chunk.ordinal)
    )
    found = next((chunk for chunk in rows if quote in chunk.text), None)
    assert found is not None, f"no quote chunk of {source_id} holds {quote!r}"
    return found


async def cited_claim(session: AsyncSession, craft: Craft, source_id: uuid.UUID, quote: str) -> uuid.UUID:
    concept = Concept(craftId=craft.id, type="PROCESS_STAGE", name=f"Mordant paste {uuid.uuid4().hex[:8]}")
    session.add(concept)
    await session.flush()
    claim = Claim(
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=f"The artisan says: {quote}.",
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status="APPROVED",
    )
    session.add(claim)
    await session.flush()
    chunk = await public_chunk(session, source_id, quote)
    session.add(
        ClaimSource(
            claimId=claim.id,
            sourceId=source_id,
            chunkId=chunk.id,
            locator=chunk.locator,
            quote=quote,
            quoteCheck="PASS",
            relation="DIRECT",
        )
    )
    await session.flush()
    return claim.id
