from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Collection, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.expert_takes import TAKE_SENTENCES_MAX
from app.core.config import get_settings
from app.models import ClaimSource, Craft, FieldRecording, FieldSegment
from app.research.field_voices import FIELD_SOURCE_KIND
from app.research.retrieval import EVERY_CHUNK_KINDS, OPEN_CHUNK_ACLS, ChunkHit, KnowledgeQuery
from app.research.vocabulary import FACT_LEVELS
from app.retrieval.field_scope import shown_recordings

from . import knowledge_view
from .answer_events import CitedClaims, cited_claims, joined_claims
from .artisan_turns import ARTISAN_ROLE, FieldTurn, TurnCite, artisan_turn, backing_rank, says, unquoted_turns
from .artisan_write_back import TurnFiling, written_turns
from .builder_interface import BuildAsk, BuilderTools
from .field_voices_view import craft_name_of
from .section_blocks import KeptSentence, prose_problems

__all__ = [
    "ARTISAN_ROLE",
    "ARTISAN_SEARCH_LIMIT",
    "FIELD_READING_ACLS",
    "FIELD_READING_KINDS",
    "Heard",
    "HeardQuote",
    "VoiceSearch",
    "artisan_take",
    "attributed",
    "stored_voices",
]

ARTISAN_SEARCH_LIMIT = 12
FIELD_READING_ACLS = OPEN_CHUNK_ACLS
FIELD_READING_KINDS = EVERY_CHUNK_KINDS


@dataclass(frozen=True)
class HeardQuote:
    claim_id: uuid.UUID
    quote: str
    name: str | None
    craft: str
    district: str | None


@dataclass(frozen=True)
class Heard:
    quotes: tuple[HeardQuote, ...] = ()
    cited: CitedClaims = field(default_factory=CitedClaims)


@dataclass(frozen=True)
class _Transcript:
    hits: tuple[ChunkHit, ...]
    cites: tuple[TurnCite, ...]
    rows: tuple[tuple[FieldSegment, FieldRecording], ...]


VoiceSearch = Callable[[BuildAsk], Awaitable[Heard]]


def attributed(heard: HeardQuote) -> str:
    place = f" in {heard.district} district" if heard.district else ""
    said = heard.quote.strip()
    if heard.name is None:
        return f"In one account from an artisan who practises {heard.craft}{place}: “{said}”"
    return f"In one artisan's account, {heard.name}, who practises {heard.craft}{place}, said: “{said}”"


def _heard_quote(claim_id: uuid.UUID, quote: str, turn: FieldTurn) -> HeardQuote:
    speaker = turn.voice.speaker
    return HeardQuote(
        claim_id=claim_id,
        quote=quote,
        name=speaker.name,
        craft=craft_name_of(turn.recording.context or {}),
        district=speaker.district,
    )


def artisan_take(heard: Heard, shown: Collection[str]) -> tuple[KeptSentence, ...]:
    kept: dict[uuid.UUID, KeptSentence] = {}
    for quote in heard.quotes:
        view = heard.cited.views.get(quote.claim_id)
        if view is None or view.id in kept or str(view.id) in shown or view.level not in FACT_LEVELS:
            continue
        if prose_problems([KeptSentence(quote.quote, (view.id,), (), False)], heard.cited):
            continue
        kept[view.id] = KeptSentence(attributed(quote), (view.id,), (), False)
        if len(kept) == TAKE_SENTENCES_MAX:
            break
    return tuple(kept.values())


def _field_voices_on() -> bool:
    return get_settings().field_voices_enabled


def stored_voices(tools: BuilderTools, *, enabled: Callable[[], bool] = _field_voices_on) -> VoiceSearch:
    async def heard(ask: BuildAsk) -> Heard:
        craft, retriever = ask.request.craft, tools.retriever
        if craft is None or retriever is None or tools.sessions is None or not enabled():
            return Heard()
        query = KnowledgeQuery(
            craft_slug=craft.slug,
            text=ask.request.question,
            mode=ask.request.mode,
            chunk_acls=FIELD_READING_ACLS,
            chunk_kinds=FIELD_READING_KINDS,
            limit=ARTISAN_SEARCH_LIMIT,
        )
        hits = await retriever.search(query)
        found = tuple(hit for hit in hits.chunks if hit.source_kind == FIELD_SOURCE_KIND)
        if not found:
            return Heard()
        async with tools.sessions() as session:
            return await _heard_in(session, ask, craft.slug, found)

    return heard


async def _heard_in(session: AsyncSession, ask: BuildAsk, slug: str, hits: tuple[ChunkHit, ...]) -> Heard:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        return Heard()
    transcript = await _transcript(session, craft, hits)
    backed = await _read(session, _backed_quotes(transcript))
    turns = unquoted_turns(transcript.hits, transcript.cites, transcript.rows, limit=_room(backed))
    filing = TurnFiling(craft.slug, craft.name, ask.section.discipline, ask.answer_id)
    written = await written_turns(session, filing, turns)
    added = await _read(
        session, [_heard_quote(one.claim_id, one.unquoted.quote, one.unquoted.turn) for one in written]
    )
    return Heard((*backed.quotes, *added.quotes), joined_claims(backed.cited, added.cited))


def _room(backed: Heard) -> int:
    shown = {quote.claim_id for quote in backed.quotes if quote.claim_id in backed.cited.views}
    return TAKE_SENTENCES_MAX - len(shown)


async def _transcript(session: AsyncSession, craft: Craft, hits: tuple[ChunkHit, ...]) -> _Transcript:
    sources = list({hit.source_id for hit in hits})
    cites = (
        await session.execute(
            select(ClaimSource.claimId, ClaimSource.sourceId, ClaimSource.chunkId, ClaimSource.quote).where(
                ClaimSource.sourceId.in_(sources), ClaimSource.quote.is_not(None)
            )
        )
    ).all()
    rows = (
        await session.execute(
            select(FieldSegment, FieldRecording)
            .join(FieldRecording, FieldRecording.id == FieldSegment.recordingId)
            .where(FieldRecording.sourceId.in_(sources), *shown_recordings(craft.id))
            .order_by(FieldSegment.position)
        )
    ).all()
    return _Transcript(
        hits=hits,
        cites=tuple(TurnCite(row.claimId, row.sourceId, row.chunkId, row.quote) for row in cites),
        rows=tuple((segment, recording) for segment, recording in rows),
    )


def _backed_quotes(transcript: _Transcript) -> list[HeardQuote]:
    ranked = [
        (rank, cite) for cite in transcript.cites if (rank := backing_rank(cite, transcript.hits)) is not None
    ]
    ranked.sort(key=lambda entry: entry[0])
    return [found for _, cite in ranked if (found := _spoken(cite, transcript.rows)) is not None]


async def _read(session: AsyncSession, quotes: Sequence[HeardQuote]) -> Heard:
    if not quotes:
        return Heard()
    views, sources = await knowledge_view.claims_by_id(
        session, [quote.claim_id for quote in quotes], acls=FIELD_READING_ACLS
    )
    return Heard(tuple(quotes), cited_claims(list(views.values()), sources))


def _spoken(cite: TurnCite, rows: Sequence[tuple[FieldSegment, FieldRecording]]) -> HeardQuote | None:
    for segment, recording in rows:
        if recording.sourceId != cite.source_id or not says(segment, cite.quote):
            continue
        turn = artisan_turn(segment, recording)
        return None if turn is None else _heard_quote(cite.claim_id, cite.quote, turn)
    return None
