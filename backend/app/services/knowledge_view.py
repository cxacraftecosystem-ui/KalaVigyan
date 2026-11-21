import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminDistrict,
    AdminState,
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    Craft,
    CraftLocation,
    Source,
)
from app.research.retrieval import (
    HIDDEN_CLAIM_STATUSES,
    OPEN_CHUNK_ACLS,
    RESTRICTED_SENSITIVITY,
    VISIBLE_SENSITIVITY,
)
from app.research.vocabulary import LEVEL_ORDER
from app.retrieval.citation_access import FAILED_QUOTE, HELD_KEPT, HELD_LEFT_OUT, unheld
from app.retrieval.statements import (
    CraftScope,
    claim_conditions,
    lexical_rank,
    readable_citations,
    scope_concepts,
    text_query,
)
from app.retrieval.text import or_tsquery

STAGE_TYPE = "PROCESS_STAGE"
EDGE_SECTION = "RELATIONS"
SECTION_HEADINGS = {
    "TRADITION": "The tradition",
    "HISTORICAL_CONTEXT": "History",
    "DESIGN_PRINCIPLE": "Design",
    "MECHANISM": "How it works",
    "EXPLANATION": "How it works",
    "ENVIRONMENTAL_CONDITION": "Place and climate",
    "PROCESS_STAGE": "Process",
    "ARTISAN_ACTION": "Process",
    "ARTISAN_DECISION": "The artisan's judgement",
    "SENSORY_CUE": "The artisan's judgement",
    "MATERIAL": "Materials and tools",
    "TOOL": "Materials and tools",
    "OUTCOME": "Results",
    "COMPARISON": "Comparisons",
    "OPEN_QUESTION": "Open questions",
    EDGE_SECTION: "How the steps connect",
}
SECTION_ORDER = [
    "The tradition",
    "History",
    "Design",
    "Materials and tools",
    "Process",
    "How it works",
    "How the steps connect",
    "Place and climate",
    "The artisan's judgement",
    "Results",
    "Comparisons",
    "Other findings",
    "Open questions",
]


@dataclass
class ClaimView:
    id: uuid.UUID
    text: str
    level: str
    concept_type: str
    concept_id: uuid.UUID | None
    rank: float = 0.0
    citations: list[dict[str, Any]] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {"id": str(self.id), "text": self.text, "level": self.level, "citations": self.citations}


def source_ref(source: Source) -> dict[str, Any]:
    authors = [str(a) if not isinstance(a, dict) else str(a.get("name") or "") for a in source.authors or []]
    url = source.url if source.url and source.url.startswith("https://") else None
    if url is None and source.doi:
        url = f"https://doi.org/{source.doi}"
    return {
        "id": str(source.id),
        "kind": source.kind,
        "title": source.title,
        "authors": [a for a in authors if a],
        "year": source.year,
        "doi": source.doi,
        "url": url,
        "publisher": source.publisher,
        "licence": source.licence,
        "attribution": source.attribution,
        "reliability": source.reliability,
    }


def citation(cite: ClaimSource, level: str) -> dict[str, Any]:
    quote = shown_quote(cite)
    return {
        "id": str(cite.id),
        "claimId": str(cite.claimId),
        "sourceId": str(cite.sourceId),
        "quote": quote,
        "locator": cite.locator,
        "context": None,
        "evidence": "QUOTED" if quote else "INFERRED",
        "level": level,
    }


def shown_quote(cite: ClaimSource) -> str | None:
    return None if cite.quoteCheck == FAILED_QUOTE else cite.quote


def section_heading(concept_type: str) -> str:
    return SECTION_HEADINGS.get(concept_type, "Other findings")


def order_claims(claims: Iterable[ClaimView]) -> list[ClaimView]:
    return sorted(
        claims,
        key=lambda c: (
            SECTION_ORDER.index(section_heading(c.concept_type)),
            -c.rank,
            LEVEL_ORDER.get(c.level, 9),
            c.text,
        ),
    )


async def resolve_craft(session: AsyncSession, slug: str) -> Craft | None:
    craft = (await session.execute(select(Craft).where(Craft.slug == slug))).scalar_one_or_none()
    if craft is None:
        folded = (
            await session.scalars(select(Craft).where(func.lower(Craft.slug) == slug.lower()).limit(2))
        ).all()
        craft = folded[0] if len(folded) == 1 else None
    hops = 0
    while craft is not None and craft.status == "MERGED" and craft.mergedIntoId and hops < 5:
        craft = await session.get(Craft, craft.mergedIntoId)
        hops += 1
    return craft


def craft_ref(craft: Craft) -> dict[str, Any]:
    return {"slug": craft.slug, "name": craft.name, "path": f"/crafts/{craft.slug}"}


def craft_scope_of(craft: Craft) -> CraftScope:
    return CraftScope(craft_id=craft.id, sub_category_id=craft.subCategoryId)


async def craft_concepts(session: AsyncSession, craft: Craft) -> list[Concept]:
    concepts = scope_concepts(craft_scope_of(craft))
    return list((await session.scalars(select(Concept).where(Concept.id.in_(concepts)))).all())


async def claims_for(
    session: AsyncSession,
    craft: Craft,
    *,
    mode: str,
    question: str | None = None,
    acls: Sequence[str] = OPEN_CHUNK_ACLS,
) -> tuple[list[ClaimView], dict[uuid.UUID, Source]]:
    conditions = claim_conditions(craft_scope_of(craft), mode=mode, held=HELD_LEFT_OUT)
    return await _craft_claims(session, craft, conditions, question=question, acls=acls)


async def contributor_claims_for(
    session: AsyncSession,
    craft: Craft,
    *,
    mode: str,
    question: str | None = None,
    acls: Sequence[str] = OPEN_CHUNK_ACLS,
) -> tuple[list[ClaimView], dict[uuid.UUID, Source]]:
    conditions = claim_conditions(craft_scope_of(craft), mode=mode, held=HELD_KEPT)
    return await _craft_claims(session, craft, conditions, question=question, acls=acls)


async def _craft_claims(
    session: AsyncSession,
    craft: Craft,
    conditions: Sequence[Any],
    *,
    question: str | None,
    acls: Sequence[str],
) -> tuple[list[ClaimView], dict[uuid.UUID, Source]]:
    tsquery = or_tsquery(question or "")
    rank_column: Any = lexical_rank(Claim.tsv, text_query(tsquery)) if tsquery else text("0")
    rows = list((await session.execute(select(Claim, rank_column).where(*conditions))).all())
    concepts = {concept.id: concept for concept in await craft_concepts(session, craft)}
    edge_concept = await _edge_concepts(session, rows, concepts)

    def placed(claim: Claim) -> tuple[uuid.UUID | None, str]:
        if claim.subjectType == "EDGE":
            return edge_concept.get(claim.subjectId), EDGE_SECTION
        return claim.subjectId, concepts[claim.subjectId].type

    return await _cited_views(session, rows, placed, acls=acls)


async def _edge_concepts(
    session: AsyncSession, rows: list[Any], concepts: dict[uuid.UUID, Concept]
) -> dict[uuid.UUID, uuid.UUID]:
    edge_ids = [claim.subjectId for claim, _ in rows if claim.subjectType == "EDGE"]
    if not edge_ids:
        return {}
    edges = (await session.scalars(select(ConceptEdge).where(ConceptEdge.id.in_(edge_ids)))).all()
    return {edge.id: edge.srcId if edge.srcId in concepts else edge.dstId for edge in edges}


async def claims_by_id(
    session: AsyncSession, claim_ids: Iterable[uuid.UUID], *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> tuple[dict[uuid.UUID, ClaimView], dict[uuid.UUID, Source]]:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return {}, {}
    rows = await _visible_claims(session, Claim.id.in_(wanted), text("0"))

    def placed(claim: Claim) -> tuple[uuid.UUID | None, str]:
        return (claim.subjectId if claim.subjectType == "CONCEPT" else None), ""

    views, sources = await _cited_views(session, rows, placed, acls=acls)
    return {view.id: view for view in views}, sources


async def _visible_claims(session: AsyncSession, condition: Any, rank_column: Any) -> list[Any]:
    filters = [
        condition,
        Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
        *unheld(HELD_LEFT_OUT),
    ]
    return list((await session.execute(select(Claim, rank_column).where(*filters))).all())


async def _cited_views(
    session: AsyncSession,
    rows: list[Any],
    placed: Callable[[Claim], tuple[uuid.UUID | None, str]],
    *,
    acls: Sequence[str],
) -> tuple[list[ClaimView], dict[uuid.UUID, Source]]:
    if not rows:
        return [], {}
    claim_ids = [claim.id for claim, _ in rows]
    cites = (await session.execute(readable_citations(claim_ids, acls=acls))).scalars().all()
    source_ids = {cite.sourceId for cite in cites}
    sources = {
        source.id: source
        for source in (
            await session.execute(
                select(Source).where(Source.id.in_(source_ids), Source.sensitivity != RESTRICTED_SENSITIVITY)
            )
        )
        .scalars()
        .all()
    }
    by_claim: dict[uuid.UUID, list[ClaimSource]] = {}
    for cite in cites:
        if cite.sourceId in sources:
            by_claim.setdefault(cite.claimId, []).append(cite)
    views: list[ClaimView] = []
    for claim, rank in rows:
        attached = by_claim.get(claim.id)
        if attached:
            views.append(cited_view(claim, attached, placed(claim), rank=float(rank or 0)))
    return views, sources


def cited_view(
    claim: Claim, cites: list[ClaimSource], placed: tuple[uuid.UUID | None, str], *, rank: float = 0.0
) -> ClaimView:
    concept_id, concept_type = placed
    ordered = sorted(cites, key=lambda c: (shown_quote(c) is None, str(c.id)))
    return ClaimView(
        id=claim.id,
        text=claim.text,
        level=claim.evidenceLevel,
        concept_type=concept_type,
        concept_id=concept_id,
        rank=rank,
        citations=[citation(c, claim.evidenceLevel) for c in ordered],
    )


async def state_points(session: AsyncSession) -> dict[str, dict[str, Any]]:
    rows = (
        await session.execute(
            select(
                AdminState.lgd,
                AdminState.name,
                func.ST_Y(func.ST_PointOnSurface(AdminState.geom)),
                func.ST_X(func.ST_PointOnSurface(AdminState.geom)),
            )
        )
    ).all()
    return {
        name.casefold(): {"lgd": lgd, "name": name, "latitude": lat, "longitude": lon}
        for lgd, name, lat, lon in rows
    }


async def map_points(session: AsyncSession) -> list[dict[str, Any]]:
    states = await state_points(session)
    crafts = (
        await session.execute(
            select(Craft.slug, Craft.name, Craft.stateOfPractice).where(
                Craft.status == "ACTIVE", Craft.isCatchAll.is_(False)
            )
        )
    ).all()
    points: dict[str, dict[str, Any]] = {}
    for slug, name, practice in crafts:
        for state in practice or []:
            point = states.get(str(state).casefold())
            if point is None or point["latitude"] is None:
                continue
            key = f"state-{point['lgd']}"
            entry = points.setdefault(
                key,
                {
                    "key": key,
                    "name": point["name"],
                    "latitude": point["latitude"],
                    "longitude": point["longitude"],
                    "crafts": {},
                },
            )
            entry["crafts"][slug] = {"slug": slug, "name": name, "path": f"/crafts/{slug}"}
    located = (
        await session.execute(
            select(
                Craft.slug,
                Craft.name,
                CraftLocation.placeLabel,
                AdminDistrict.lgd,
                AdminDistrict.name,
                func.ST_Y(func.coalesce(func.geometry(CraftLocation.geom), AdminDistrict.centroid)),
                func.ST_X(func.coalesce(func.geometry(CraftLocation.geom), AdminDistrict.centroid)),
            )
            .join(Craft, Craft.id == CraftLocation.craftId)
            .outerjoin(AdminDistrict, AdminDistrict.lgd == CraftLocation.districtLgd)
            .where(Craft.status == "ACTIVE", CraftLocation.precision.in_(("DISTRICT", "POINT")))
        )
    ).all()
    for slug, name, label, district_lgd, district_name, lat, lon in located:
        if lat is None or lon is None:
            continue
        key = f"district-{district_lgd}" if district_lgd else f"point-{lat:.3f},{lon:.3f}"
        entry = points.setdefault(
            key,
            {
                "key": key,
                "name": label or district_name or name,
                "latitude": lat,
                "longitude": lon,
                "crafts": {},
            },
        )
        entry["crafts"][slug] = {"slug": slug, "name": name, "path": f"/crafts/{slug}"}
    out = []
    for entry in points.values():
        listed = sorted(entry["crafts"].values(), key=lambda c: c["name"].casefold())
        out.append({**entry, "total": len(listed), "crafts": listed})
    return sorted(out, key=lambda p: p["name"].casefold())
