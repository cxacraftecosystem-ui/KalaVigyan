from __future__ import annotations

import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Concept, Craft, Term, TermConcept, TermCraft
from app.research.craft_page_context import PageRelative
from app.research.kin_crafts import KIN_CHAPTER, KIN_KIND, KIN_SHARES_MAX, KinCraft, KinCraftsSpec, KinHead
from app.research.monograph_page import CitedSource, ComponentEntry

from . import knowledge_view
from .claim_holds import unheld_by_id
from .craft_page_family import family_relatives
from .craft_page_records import PAGE_MODE
from .knowledge_view import ClaimView
from .monograph_generated_units import DraftUnit, stored_source
from .open_work_subjects import WorkSubject

__all__ = [
    "KIN_TITLE",
    "KinRead",
    "KinShown",
    "kin_label",
    "kin_placed",
    "place_kin",
    "shared_materials",
    "subject_kin",
]

KIN_TITLE = "Crafts of the same family"
KIN_FIELD = "OVERVIEW"
LABEL_TAIL = "kin/related-crafts"
UNIT_PREFIX = "kin-"
MATERIAL = "MATERIAL"
CRAFT = "craft"
PLACE_SEPARATOR = ", "


@dataclass(frozen=True)
class KinShown:
    relative: PageRelative
    shares: tuple[str, ...]
    text: str
    claim_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class KinRead:
    crafts: tuple[KinShown, ...] = ()
    family: str | None = None
    visible: Mapping[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: Mapping[str, CitedSource] = field(default_factory=dict)


@dataclass(frozen=True)
class KinPlaced:
    label: str
    entry: ComponentEntry
    spec: dict[str, Any]
    drafts: tuple[DraftUnit, ...]


class PlacingPage(Protocol):
    drafts: dict[str, DraftUnit]
    components: dict[str, ComponentEntry]
    specs: dict[str, dict[str, Any]]
    held: dict[str, list[str]]


async def subject_kin(session: AsyncSession, subject: WorkSubject, family: str | None) -> KinRead:
    craft = await session.get(Craft, subject.id) if subject.kind == CRAFT else None
    if craft is None:
        return KinRead()
    relatives = [
        relative for relative in await family_relatives(session, craft, mode=PAGE_MODE) if relative.lede
    ]
    if not relatives:
        return KinRead()
    cited = [
        uuid.UUID(c.claim_id) for relative in relatives if relative.lede for c in relative.lede.citations
    ]
    views, rows = await knowledge_view.claims_by_id(session, cited)
    visible = await unheld_by_id(session, views)
    shares = await shared_materials(session, craft.id, [relative.craft.slug for relative in relatives])
    shown = tuple(
        kin for kin in (_shown(relative, shares, visible) for relative in relatives) if kin is not None
    )
    sources = {str(key): stored_source(knowledge_view.source_ref(row)) for key, row in rows.items()}
    return KinRead(crafts=shown, family=family, visible=visible, sources=sources)


async def shared_materials(
    session: AsyncSession, craft_id: uuid.UUID, slugs: Sequence[str]
) -> dict[str, tuple[str, ...]]:
    materials = select(TermConcept.termId).join(Concept, Concept.id == TermConcept.conceptId)
    rows = await session.execute(
        select(Craft.id, Craft.slug, Term.key, Term.label)
        .join(TermCraft, TermCraft.craftId == Craft.id)
        .join(Term, Term.id == TermCraft.termId)
        .where(or_(Craft.id == craft_id, Craft.slug.in_(list(slugs))))
        .where(Term.id.in_(materials.where(Concept.type == MATERIAL)))
        .order_by(Term.label, Term.key)
    )
    found = rows.all()
    own = {row.key for row in found if row.id == craft_id}
    shared: dict[str, list[str]] = {}
    for row in found:
        if row.id != craft_id and row.key in own and row.label not in shared.get(row.slug, []):
            shared.setdefault(row.slug, []).append(row.label)
    return {slug: tuple(labels[:KIN_SHARES_MAX]) for slug, labels in shared.items()}


def kin_label(slug: str) -> str:
    stem = re.sub(r"-+", "-", re.sub(r"[^a-z0-9-]", "", slug.lower())).strip("-")
    return f"{stem}/{LABEL_TAIL}"


def kin_placed(read: KinRead, slug: str) -> KinPlaced | None:
    if not read.crafts:
        return None
    label = kin_label(slug)
    drafts = tuple(
        DraftUnit(f"{UNIT_PREFIX}{at}", KIN_CHAPTER, KIN_FIELD, kin.text, kin.claim_ids)
        for at, kin in enumerate(read.crafts, start=1)
    )
    crafts = [_kin_craft(kin, draft.unit_id) for kin, draft in zip(read.crafts, drafts, strict=True)]
    spec = KinCraftsSpec(head=KinHead(title=KIN_TITLE, family=read.family), crafts=crafts)
    return KinPlaced(label, _entry(label, slug), spec.model_dump(mode="json", by_alias=True), drafts)


def place_kin(read: KinRead, slug: str, page: PlacingPage, components: dict[str, list[str]]) -> None:
    placed = kin_placed(read, slug)
    if placed is None or placed.label in page.components:
        return
    page.components[placed.label] = placed.entry
    page.specs[placed.label] = placed.spec
    page.drafts.update((draft.unit_id, draft) for draft in placed.drafts)
    page.held[placed.label] = [draft.unit_id for draft in placed.drafts]
    components.setdefault(KIN_CHAPTER, []).append(placed.label)


def _shown(
    relative: PageRelative, shares: Mapping[str, tuple[str, ...]], visible: Mapping[uuid.UUID, ClaimView]
) -> KinShown | None:
    lede = relative.lede
    if lede is None:
        return None
    claim_ids = tuple(dict.fromkeys(uuid.UUID(citation.claim_id) for citation in lede.citations))
    if not claim_ids or any(claim_id not in visible for claim_id in claim_ids):
        return None
    return KinShown(relative, shares.get(relative.craft.slug, ()), lede.text, claim_ids)


def _kin_craft(kin: KinShown, unit_id: str) -> KinCraft:
    relative = kin.relative
    return KinCraft(
        name=relative.display_name,
        path=relative.craft.path,
        place=PLACE_SEPARATOR.join(relative.state_of_practice) or None,
        gi=relative.gi_status == "GI",
        monograph=relative.coverage is not None,
        shares=list(kin.shares),
        sentence=unit_id,
    )


def _entry(label: str, slug: str) -> ComponentEntry:
    return ComponentEntry(
        label=label,
        chapter=KIN_CHAPTER,
        anchor="#" + label.replace("/", "--"),
        kind=KIN_KIND,
        title=KIN_TITLE,
        description="The crafts of the same family, each with its family swatch, the materials it shares and one cited sentence.",
        field=KIN_FIELD,
        fields=[KIN_FIELD],
        subjects=[f"craft:{slug}"],
    )
