import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from app.models import Source
from app.research.depth import depth_at_least
from app.research.knowledge_pieces import (
    CLAIM_KEYED_KINDS,
    KnowledgePiece,
    PieceSlot,
    ReuseAsk,
    knowledge_piece,
    piece_slot,
)
from app.research.piece_reuse import (
    ClaimState,
    answered_first,
    reusable_groups,
    with_region_story,
    with_simulation,
)
from app.research.piece_topics import TopicSubjects, facet_topics
from app.services.answer_events import cited_claims
from app.services.knowledge_view import ClaimView
from app.services.piece_lookup import PieceAsk, PieceLookup, ReusedSection
from app.services.piece_store import BuiltSection, piece_id, storable

CRAFT_ID = uuid.UUID("54081f83-8396-5a46-a3bc-a467984eebc2")
FIRST_KEPT_AT = datetime(2026, 11, 12, 8, 15, tzinfo=UTC)


@dataclass
class MemoryPieces:
    views: Sequence[ClaimView] = ()
    sources: dict[uuid.UUID, Source] = field(default_factory=dict)
    pieces: list[KnowledgePiece] = field(default_factory=list)
    asked: list[PieceAsk] = field(default_factory=list)
    kept: list[tuple[uuid.UUID, str, tuple[BuiltSection, ...]]] = field(default_factory=list)
    held_fields: tuple[str, ...] = ()

    async def fields(self, craft_slug: str) -> tuple[str, ...]:
        return self.held_fields

    async def reusable(self, ask: PieceAsk) -> PieceLookup:
        self.asked.append(ask)
        if ask.craft is None:
            return PieceLookup()
        topics = facet_topics(ask.facets, TopicSubjects(craft_slug=ask.craft.slug))
        if ask.fresh:
            return PieceLookup(craft_id=CRAFT_ID, topics=topics)
        states = {
            view.id: ClaimState(level=view.level, citation_ids=frozenset(c["id"] for c in view.citations))
            for view in self.views
        }
        cited = cited_claims(list(self.views), self.sources)
        newest_first = sorted(self.pieces, key=lambda piece: piece.created_at, reverse=True)
        own = [piece for piece in newest_first if piece.craft_id == CRAFT_ID]
        regions = [piece for piece in newest_first if piece.craft_id is None]
        curated = frozenset(
            claim for piece in own if piece.created_from_answer_id is None for claim in piece.claim_ids
        )
        reused = {}
        for facet, topic in topics.items():
            ask_for = ReuseAsk(
                craft_id=CRAFT_ID,
                facet=facet,
                topic_key=topic,
                depth=ask.depth,
                reading_style=ask.reading_style,
            )
            groups = answered_first(reusable_groups(own, ask_for, states), curated)
            if groups:
                shown = with_region_story(groups[0], regions, depth=ask.depth, current=states)
                shown = with_simulation(shown, regions, depth=ask.depth, current=states)
                reused[facet] = ReusedSection(pieces=shown, cited=cited, curated=curated)
        return PieceLookup(craft_id=CRAFT_ID, topics=topics, reused=reused)

    async def keep(
        self,
        lookup: PieceLookup,
        *,
        answer_id: uuid.UUID,
        depth: str,
        sections: Sequence[BuiltSection],
        reading_style: str | None = None,
    ) -> None:
        self.kept.append((answer_id, depth, tuple(sections)))
        created_at = FIRST_KEPT_AT + timedelta(minutes=len(self.kept))
        for section in sections:
            if section.deepened or lookup.craft_id is None or section.facet not in lookup.topics:
                continue
            slot = PieceSlot(lookup.craft_id, section.facet, lookup.topics[section.facet], depth)
            for block in section.blocks:
                if storable(block):
                    new = knowledge_piece(
                        block,
                        piece_slot(block, slot),
                        piece_id=piece_id(answer_id, f"{block.id}-{len(self.kept)}"),
                        answer_id=uuid.uuid5(answer_id, str(len(self.kept))),
                        created_at=created_at,
                        reading_style=reading_style,
                    )
                    self._supersede(new)
                    self.pieces.append(new)

    def retract(self, claim_id: uuid.UUID) -> None:
        self.views = [view for view in self.views if view.id != claim_id]
        at = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
        self.pieces = [
            piece.model_copy(update={"stale_since": at}) if claim_id in piece.claim_ids else piece
            for piece in self.pieces
        ]

    def current(self) -> list[KnowledgePiece]:
        return [piece for piece in self.pieces if piece.superseded_by_id is None]

    def _supersede(self, new: KnowledgePiece) -> None:
        self.pieces = [
            piece.model_copy(update={"superseded_by_id": new.id}) if superseded_by(piece, new) else piece
            for piece in self.pieces
        ]


def superseded_by(piece: KnowledgePiece, new: KnowledgePiece) -> bool:
    slot = (piece.craft_id, piece.facet, piece.topic_key, piece.kind)
    return (
        slot == (new.craft_id, new.facet, new.topic_key, new.kind)
        and depth_at_least(new.depth, piece.depth)
        and piece.reading_style == new.reading_style
        and piece.id != new.id
        and piece.created_from_answer_id is not None
        and piece.created_from_answer_id != new.created_from_answer_id
        and piece.superseded_by_id is None
        and piece.created_at <= new.created_at
        and (new.kind not in CLAIM_KEYED_KINDS or piece.claim_ids == new.claim_ids)
    )
