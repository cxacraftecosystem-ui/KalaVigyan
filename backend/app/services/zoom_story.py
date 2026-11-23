from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping, Sequence, Set
from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.datasets import region_dataset
from app.models import Craft, Term, TermCraft
from app.research.blocks import ExplainerSentence, named_in
from app.research.blocks_journey import (
    IMAGE_ZOOM_LEVELS,
    ZOOM_LEVELS,
    ZoomCompound,
    ZoomLevel,
    ZoomStoryBlock,
)
from app.research.blocks_place import DistrictRef
from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, DatasetRef
from app.research.explainer import Block
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.science.records import KnownClaim

from .builder_evidence import fact_sentence, known_fact
from .knowledge_view import claims_for, resolve_craft, source_ref
from .ledger_payloads import sentence_keys
from .matter_builders import LinkedCompound
from .media_ref_store import StoredPicture, stored_pictures
from .place_offers import district_refs, mapped_districts
from .region_records import dataset_records
from .zoom_pictures import LevelPicture, LevelTerm

__all__ = [
    "ZOOM_DISTRICT_CLAIMS_MAX",
    "Captions",
    "ZoomGround",
    "district_level",
    "figure_texts",
    "level_terms",
    "molecule_level",
    "picture_level_of",
    "zoom_ground",
    "zoom_story_block",
]

logger = logging.getLogger(__name__)

ZOOM_DISTRICT_CLAIMS_MAX = 8
COMPOSED_PROSE = "prose"


def figure_texts(blocks: Iterable[Block]) -> set[str]:
    return {
        key
        for block in blocks
        if block.kind != COMPOSED_PROSE
        for sentence in block.cited_sentences()
        for key in sentence_keys(sentence.text, sentence.original)
    }


@dataclass(frozen=True)
class ZoomGround:
    districts: tuple[DistrictRef, ...] = ()
    boundary: DatasetRef | None = None
    claims: tuple[KnownClaim, ...] = ()
    sources: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    pictures: tuple[StoredPicture, ...] = ()
    terms: tuple[LevelTerm, ...] = ()


@dataclass
class Captions:
    claims: Mapping[uuid.UUID, KnownClaim]
    used: set[uuid.UUID] = field(default_factory=set)

    @classmethod
    def of(cls, *groups: Iterable[KnownClaim]) -> Captions:
        return cls({claim.id: claim for group in groups for claim in group})

    def without_said(self, said: Set[str]) -> Captions:
        self.used.update(
            claim_id for claim_id, claim in self.claims.items() if sentence_keys(claim.text) & said
        )
        return self

    def first(self, candidates: Iterable[uuid.UUID], names: str | None = None) -> KnownClaim | None:
        claim = self._found(candidates, names)
        if claim is not None:
            self.used.add(claim.id)
        return claim

    def names(self, name: str) -> bool:
        return self._found(self.claims, name) is not None

    def _found(self, candidates: Iterable[uuid.UUID], names: str | None) -> KnownClaim | None:
        for claim_id in candidates:
            claim = self.claims.get(claim_id)
            if claim is None or claim_id in self.used:
                continue
            if names is None or named_in(names, fact_sentence(claim, "caption")):
                return claim
        return None


async def zoom_ground(
    session: AsyncSession, craft_slug: str, *, mode: str, offered: Sequence[uuid.UUID]
) -> ZoomGround | None:
    craft = await resolve_craft(session, craft_slug)
    if craft is None:
        return None
    lgds = await mapped_districts(session, craft)
    named = await district_refs(session, lgds)
    districts = tuple(named[lgd] for lgd in lgds if lgd in named)
    record = (await dataset_records(session, [BOUNDARY_DATASET_CODE])).get(BOUNDARY_DATASET_CODE)
    boundary = region_dataset(record) if record is not None else None
    claims, sources = await _district_claims(session, craft, districts, mode) if boundary else ((), {})
    pictures = await stored_pictures(session, [*offered, *(claim.id for claim in claims)])
    terms = await level_terms(session, craft.id)
    return ZoomGround(districts, boundary, claims, sources, tuple(pictures), terms)


async def level_terms(session: AsyncSession, craft_id: uuid.UUID) -> tuple[LevelTerm, ...]:
    linked = select(TermCraft.termId).where(TermCraft.craftId == craft_id)
    rows = await session.scalars(
        select(Term).where(Term.id.in_(linked), Term.zoomLevel.in_(IMAGE_ZOOM_LEVELS)).order_by(Term.key)
    )
    return tuple(
        LevelTerm(
            level=str(row.zoomLevel), label=row.label, surfaces=(row.label, *row.aliases, *row.localNames)
        )
        for row in rows
    )


def district_level(ground: ZoomGround, captions: Captions) -> ZoomLevel | None:
    if ground.boundary is None:
        return None
    for district in ground.districts:
        claim = captions.first(captions.claims, district.name)
        if claim is not None:
            return _level("DISTRICT", claim, district=district)
    return None


def picture_level_of(picture: LevelPicture, captions: Captions) -> ZoomLevel | None:
    claim = captions.first(picture.claim_ids)
    if claim is None:
        return None
    return _level(picture.level, claim, media=picture.media, relevance=picture.relevance)


def molecule_level(linked: LinkedCompound, captions: Captions) -> ZoomLevel | None:
    claim = captions.first(captions.claims, linked.compound.name)
    if claim is None:
        return None
    compound = ZoomCompound(
        compound_id=linked.compound.id,
        pubchem_cid=linked.pubchem_cid,
        name=linked.compound.name,
        formula=linked.compound.formula,
        source_id=linked.source_id,
    )
    return _level("MOLECULE", claim, compound=compound)


def zoom_story_block(
    levels: Iterable[ZoomLevel | None], boundary: DatasetRef | None, *, block_id: str
) -> ZoomStoryBlock | None:
    shown = sorted(
        (level for level in levels if level is not None), key=lambda lv: ZOOM_LEVELS.index(lv.level)
    )
    if len(shown) < 2:
        return None
    mapped = any(level.district is not None for level in shown)
    numbered = [
        level.model_copy(update={"sentence": _renamed(level.sentence, f"{block_id}.{n}")})
        for n, level in enumerate(shown, start=1)
    ]
    try:
        return ZoomStoryBlock(
            id=block_id,
            kind="zoom_story",
            version=1,
            reuse=None,
            levels=numbered,
            datasets=[boundary] if mapped and boundary is not None else [],
            boundary_caption=BOUNDARY_CAPTION if mapped else None,
        )
    except ValidationError as refused:
        logger.warning("the zoom story %s is refused: %s", block_id, refused)
        return None


async def _district_claims(
    session: AsyncSession, craft: Craft, districts: Sequence[DistrictRef], mode: str
) -> tuple[tuple[KnownClaim, ...], dict[str, Mapping[str, Any]]]:
    if not districts:
        return (), {}
    question = " ".join(district.name for district in districts)
    views, sources = await claims_for(session, craft, mode=mode, question=question, acls=EVERY_CHUNK_ACLS)
    found: list[KnownClaim] = []
    for view in sorted(views, key=lambda v: (-v.rank, str(v.id))):
        claim = known_fact(view)
        sentence = fact_sentence(claim, "district") if claim is not None else None
        if sentence is not None and any(named_in(d.name, sentence) for d in districts):
            found.append(claim)
        if len(found) == ZOOM_DISTRICT_CLAIMS_MAX:
            break
    cited = {citation.source_id for claim in found for citation in claim.citations}
    refs = {str(sid): source_ref(source) for sid, source in sources.items() if str(sid) in cited}
    return tuple(found), refs


def _level(level: str, claim: KnownClaim, **matter: Any) -> ZoomLevel | None:
    fields = {"district": None, "media": None, "relevance": None, "compound": None, **matter}
    try:
        return ZoomLevel(level=level, sentence=fact_sentence(claim, f"zoom.{level.casefold()}"), **fields)
    except ValidationError as refused:
        logger.info("the zoom leaves out its %s level: %s", level, refused)
        return None


def _renamed(sentence: ExplainerSentence, sentence_id: str) -> ExplainerSentence:
    return sentence.model_copy(update={"id": sentence_id})
