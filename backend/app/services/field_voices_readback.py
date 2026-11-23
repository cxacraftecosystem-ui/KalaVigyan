from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ClaimSource, FieldRecording
from app.research.blocks import BlockBase, ProseBlock
from app.research.blocks_people import ArtisanVoiceBlock
from app.research.citations import Citation, SourceRef
from app.research.explainer import Explainer, ExplainerSection, explainer_blocks
from app.research.field_voices import FIELD_SOURCE_KIND, PORTAL_PUBLISHERS
from app.research.section_pictures import pictures_of_cited
from app.retrieval.field_scope import shown_recordings, withheld_field_sources

__all__ = [
    "WITHDRAWN_SEARCHED",
    "Withdrawn",
    "current_field_voices",
    "field_withdrawals",
    "portal_field_source",
    "without_withdrawn",
]

WITHDRAWN_SEARCHED = "A field interview this section quoted is no longer shown."
READY = "READY"
EMPTY = "EMPTY"


@dataclass(frozen=True)
class Withdrawn:
    citations: frozenset[tuple[str, str]] = frozenset()
    sources: frozenset[str] = frozenset()

    def __bool__(self) -> bool:
        return bool(self.citations or self.sources)

    def out(self, citation: Citation) -> bool:
        return self.interview_out(citation)

    def interview_out(self, citation: Citation) -> bool:
        return citation.source_id in self.sources or (citation.claim_id, citation.source_id) in self.citations

    def cites(self, block: BlockBase) -> bool:
        return any(self.out(citation) for citation in block.citations())

    def takes_interview_from(self, block: BlockBase) -> bool:
        if isinstance(block, ArtisanVoiceBlock) and any(q.source_id in self.sources for q in block.quotes):
            return True
        return any(self.interview_out(citation) for citation in block.citations())


def portal_field_source(source: SourceRef) -> bool:
    return source.kind == FIELD_SOURCE_KIND and source.publisher in PORTAL_PUBLISHERS.values()


async def current_field_voices(session: AsyncSession, explainer: Explainer) -> Explainer | None:
    return without_withdrawn(explainer, await field_withdrawals(session, explainer))


async def field_withdrawals(session: AsyncSession, explainer: Explainer) -> Withdrawn:
    portal = {source.id for source in explainer.sources if portal_field_source(source)}
    if not portal:
        return Withdrawn()
    ids = _uuids(portal)
    shown = {
        str(source_id)
        for source_id in await session.scalars(
            select(FieldRecording.sourceId).where(FieldRecording.sourceId.in_(ids), *shown_recordings())
        )
    }
    backed = {
        (str(row.claimId), str(row.sourceId))
        for row in await session.execute(
            select(ClaimSource.claimId, ClaimSource.sourceId).where(
                ClaimSource.sourceId.in_(ids), ClaimSource.sourceId.not_in(withheld_field_sources())
            )
        )
    }
    cited = {
        (citation.claim_id, citation.source_id)
        for block in explainer_blocks(explainer)
        for citation in block.citations()
        if citation.source_id in portal
    }
    return Withdrawn(citations=frozenset(cited - backed), sources=frozenset(portal - shown))


def without_withdrawn(explainer: Explainer, withdrawn: Withdrawn) -> Explainer | None:
    if not withdrawn:
        return explainer
    lede = explainer.lede if explainer.lede is not None and not withdrawn.cites(explainer.lede) else None
    sections = [_section(section, withdrawn) for section in explainer.sections]
    if all(section.state == EMPTY for section in sections):
        return None
    blocks = [
        *([lede] if lede is not None else []),
        *(block for section in sections for block in section.blocks),
    ]
    cited = dict.fromkeys(source_id for block in blocks for source_id in block.cited_source_ids())
    known = {source.id: source for source in explainer.sources}
    changed = explainer.model_copy(
        update={"lede": lede, "sections": sections, "sources": [known[source_id] for source_id in cited]}
    )
    try:
        return Explainer.model_validate(changed.model_dump(mode="json", by_alias=True))
    except KeyError, ValidationError:
        return None


def _section(section: ExplainerSection, withdrawn: Withdrawn) -> ExplainerSection:
    if section.state != READY:
        return section
    kept = [_kept(block, withdrawn) for block in section.blocks]
    if all(after is before for after, before in zip(kept, section.blocks, strict=True)):
        return section
    blocks = pictures_of_cited([block for block in kept if block is not None])
    if blocks:
        lost = sum(
            _lost(before, after, withdrawn) for before, after in zip(section.blocks, kept, strict=True)
        )
        try:
            changed = section.model_copy(update={"blocks": blocks, "withdrawn": section.withdrawn + lost})
            return ExplainerSection.model_validate(changed.model_dump(mode="json", by_alias=True))
        except ValidationError:
            pass
    return section.model_copy(update={"state": EMPTY, "blocks": [], "searched": WITHDRAWN_SEARCHED})


def _lost(before: BlockBase, after: BlockBase | None, withdrawn: Withdrawn) -> int:
    if after is before or not withdrawn.takes_interview_from(before):
        return 0
    return _shown(before) - _shown(after)


def _shown(block: BlockBase | None) -> int:
    if block is None:
        return 0
    quotes = len(block.quotes) if isinstance(block, ArtisanVoiceBlock) else 0
    return quotes + sum(1 for _ in block.cited_sentences())


def _kept(block: BlockBase, withdrawn: Withdrawn) -> BlockBase | None:
    if isinstance(block, ArtisanVoiceBlock):
        return _voice(block, withdrawn)
    if not withdrawn.cites(block):
        return block
    if isinstance(block, ProseBlock):
        sentences = [s for s in block.sentences if not any(withdrawn.out(c) for c in s.citations)]
        return block.model_copy(update={"sentences": sentences}) if sentences else None
    return None


def _voice(block: ArtisanVoiceBlock, withdrawn: Withdrawn) -> ArtisanVoiceBlock:
    quotes = []
    for quote in block.quotes:
        if quote.source_id in withdrawn.sources:
            continue
        kept = [citation for citation in quote.corroborated_by if not withdrawn.out(citation)]
        quotes.append(
            quote.model_copy(update={"corroborated_by": kept}) if kept != quote.corroborated_by else quote
        )
    if quotes == block.quotes:
        return block
    removed = block.removed + len(block.quotes) - len(quotes)
    return block.model_copy(update={"quotes": quotes, "removed": removed})


def _uuids(ids: Iterable[str]) -> list[uuid.UUID]:
    found: list[uuid.UUID] = []
    for value in ids:
        try:
            found.append(uuid.UUID(value))
        except ValueError:
            continue
    return found
