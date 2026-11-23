from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence

from app.core.errors import InvalidInput
from app.curation.dossier import Dossier
from app.curation.entities import (
    After,
    Community,
    Material,
    MaterialAlternative,
    MaterialUse,
    Place,
    Reaction,
    Species,
    Stage,
    Timing,
    Tool,
    ToolUse,
)
from app.curation.parts import Conflict, OpenQuestion
from app.curation.records import EnvironmentLink, Focal, NativeName, Picture, Placement, Term

from .curated_category_index import CuratedCategoryPage, IndexCategoryQuestion
from .curated_index import CuratedPage, IndexPicture, IndexSpecies, IndexStage, IndexTiming
from .dossier_export_records import Row, StoredCuration, guided, keyed

__all__ = [
    "ClaimKeys",
    "page_communities",
    "page_conflicts",
    "page_environment",
    "page_glossary",
    "page_materials",
    "page_native_names",
    "page_pictures",
    "page_places",
    "page_questions",
    "page_reactions",
    "page_stages",
    "page_tools",
]

ClaimKeys = Mapping[uuid.UUID, str]
AnyPage = CuratedPage | CuratedCategoryPage


def page_places(page: CuratedPage, keys: ClaimKeys) -> list[Place]:
    return [
        Place(
            id=place.key,
            name=place.name,
            kind=place.kind,
            district=place.district,
            state=place.state,
            country=place.country,
            wikidata=place.wikidata_id,
            role=place.role,
            claim_ids=keyed(place.claim_ids, keys),
        )
        for place in page.places
    ]


def page_communities(page: CuratedPage, keys: ClaimKeys) -> list[Community]:
    return [
        Community(
            id=group.key,
            kind=group.kind,
            name=group.name,
            local_names=group.local_names,
            honours=group.honours,
            place_id=group.place_key,
            claim_ids=keyed(group.claim_ids, keys),
        )
        for group in page.communities
    ]


def page_materials(page: CuratedPage, keys: ClaimKeys) -> list[Material]:
    return [
        Material(
            id=item.key,
            name=item.name,
            kind=item.kind,
            role=item.role,
            local_names=item.local_names,
            botanical_name=item.botanical_name,
            pubchem_cid=item.pubchem_cid,
            claim_ids=keyed(item.claim_ids, keys),
            alternatives=[
                MaterialAlternative(material_id=other.key, claim_id=keyed([other.claim_id], keys)[0])
                for other in item.alternatives
            ],
        )
        for item in page.materials
    ]


def page_tools(page: CuratedPage, keys: ClaimKeys) -> list[Tool]:
    return [
        Tool(id=item.key, name=item.name, local_names=item.local_names, claim_ids=keyed(item.claim_ids, keys))
        for item in page.tools
    ]


def page_stages(stored: StoredCuration, keys: ClaimKeys, previous: Dossier | None) -> list[Stage]:
    page = stored.page
    if not isinstance(page, CuratedPage):
        return []
    uses: dict[uuid.UUID, list[Row]] = defaultdict(list)
    for row in stored.uses:
        uses[row["stageId"]].append(row)
    earlier = {stage.id: stage for stage in previous.stages} if previous else {}
    return [
        _stage(stage, _stage_row(stored, stage), (page, keys), (uses[stage.stage_id], earlier.get(stage.key)))
        for stage in page.stages
    ]


def _stage_row(stored: StoredCuration, stage: IndexStage) -> Row:
    row = stored.stages.get(stage.stage_id)
    if row is None:
        raise InvalidInput(f"stage {stage.key} of {stored.slug} has no stored process stage")
    return row


def _stage(
    stage: IndexStage,
    row: Row,
    index: tuple[CuratedPage, ClaimKeys],
    used: tuple[Sequence[Row], Stage | None],
) -> Stage:
    page, keys = index
    materials, tools = _uses(page, keys, *used)
    return Stage(
        id=stage.key,
        name=row["name"],
        local_name=stage.local_name,
        stage_type=row["stageType"],
        order=stage.order,
        order_claim_id=_one(stage.order_claim_id, keys),
        duration=_timing(stage.duration, keys),
        season=_timing(stage.season, keys),
        materials=materials,
        tools=tools,
        claim_ids=keyed(stage.claim_ids, keys),
        after=(
            None
            if stage.after is None
            else After(
                text=stage.after.text, colours=stage.after.colours, claim_id=_one(stage.after.claim_id, keys)
            )
        ),
        why_claim_id=_one(stage.why_claim_id, keys),
    )


def _uses(
    page: CuratedPage, keys: ClaimKeys, rows: Sequence[Row], earlier: Stage | None
) -> tuple[list[MaterialUse], list[ToolUse]]:
    materials = {item.material_id: item.key for item in page.materials}
    tools = {item.material_id: item.key for item in page.tools}
    unknown = [str(row["materialId"]) for row in rows if row["materialId"] not in materials | tools]
    if unknown:
        raise InvalidInput(f"a stage uses materials that are not the dossier's: {', '.join(unknown)}")
    material_uses = [
        MaterialUse(material_id=materials[row["materialId"]], claim_id=_one(row["claimId"], keys))
        for row in rows
        if row["materialId"] in materials
    ]
    tool_uses = [
        ToolUse(tool_id=tools[row["materialId"]], claim_id=_one(row["claimId"], keys))
        for row in rows
        if row["materialId"] in tools
    ]
    material_order = list(materials.values())
    tool_order = list(tools.values())
    earlier_materials = [use.material_id for use in earlier.materials] if earlier else []
    earlier_tools = [use.tool_id for use in earlier.tools] if earlier else []
    return (
        guided(
            material_uses,
            lambda use: use.material_id,
            [earlier_materials],
            lambda use: material_order.index(use.material_id),
        ),
        guided(
            tool_uses, lambda use: use.tool_id, [earlier_tools], lambda use: tool_order.index(use.tool_id)
        ),
    )


def page_reactions(
    page: AnyPage, keys: ClaimKeys, *, stages: Mapping[str, str | None] | None = None
) -> list[Reaction]:
    kept = stages or {}
    return [
        Reaction(
            id=item.key,
            kind=item.kind,
            stage_id=item.stage_key or kept.get(item.key),
            reactants=_species(item.reactants),
            products=_species(item.products),
            claim_ids=keyed(item.claim_ids, keys),
        )
        for item in page.reactions
    ]


def _species(items: Sequence[IndexSpecies]) -> list[Species]:
    return [Species(name=item.name, formula=item.formula) for item in items]


def page_environment(page: CuratedPage, keys: ClaimKeys) -> list[EnvironmentLink]:
    return [
        EnvironmentLink(factor=item.factor, place_id=item.place_key, claim_ids=keyed(item.claim_ids, keys))
        for item in page.environment
    ]


def page_glossary(page: AnyPage, keys: ClaimKeys) -> list[Term]:
    return [
        Term(
            id=term.key,
            term=term.term,
            meaning=term.meaning,
            language=term.language,
            script=term.script,
            claim_ids=keyed(term.claim_ids, keys),
        )
        for term in page.glossary
    ]


def page_conflicts(page: AnyPage, keys: ClaimKeys) -> list[Conflict]:
    return [Conflict(claim_ids=keyed(item.claim_ids, keys), about=item.about) for item in page.conflicts]


def page_questions(page: AnyPage, keys: ClaimKeys) -> list[OpenQuestion]:
    return [
        OpenQuestion(
            id=item.key,
            question=item.question,
            claim_ids=keyed(item.claim_ids, keys),
            settled_by=item.settled_by,
            sub_categories=item.sub_categories if isinstance(item, IndexCategoryQuestion) else [],
        )
        for item in page.open_questions
    ]


def page_pictures(page: AnyPage, media: Mapping[uuid.UUID, Row], keys: ClaimKeys) -> list[Picture]:
    return [_picture(picture, _media(media, picture), keys) for picture in page.pictures]


def _media(media: Mapping[uuid.UUID, Row], picture: IndexPicture) -> Row:
    row = media.get(picture.media_ref_id)
    if row is None:
        raise InvalidInput(f"picture {picture.key} has no stored media record")
    return row


def _picture(picture: IndexPicture, row: Row, keys: ClaimKeys) -> Picture:
    placement = picture.placement
    return Picture(
        id=picture.key,
        url=row["imageUrl"],
        page_url=row["pageUrl"],
        author=row["author"],
        licence=row["licence"],
        licence_url=row["licenceUrl"],
        caption=picture.caption,
        claim_ids=keyed(picture.claim_ids, keys),
        stage_id=picture.stage_key,
        placement=(
            None
            if placement is None
            else Placement(
                chapter=placement.chapter,
                role=placement.role,
                stage_id=placement.stage_key,
                material_id=placement.material_key,
            )
        ),
        focal=None if picture.focal is None else Focal.model_validate(picture.focal.model_dump()),
        width=picture.width,
        height=picture.height,
        stand_in=picture.stand_in,
    )


def page_native_names(page: CuratedPage, keys: ClaimKeys) -> list[NativeName]:
    return [
        NativeName(
            text=name.text, language=name.language, script=name.script, claim_id=_one(name.claim_id, keys)
        )
        for name in page.native_names
    ]


def _timing(timing: IndexTiming | None, keys: ClaimKeys) -> Timing | None:
    return None if timing is None else Timing(text=timing.text, claim_id=_one(timing.claim_id, keys))


def _one(claim_id: uuid.UUID | None, keys: ClaimKeys) -> str | None:
    return None if claim_id is None else keyed([claim_id], keys)[0]
