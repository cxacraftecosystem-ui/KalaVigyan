from __future__ import annotations

import uuid
from collections.abc import Sequence

from app.curation.dossier import Dossier
from app.curation.entities import After, Reaction, Timing
from app.curation.records import Picture
from app.data.district_register import DistrictCodes

from .curated_index import (
    CuratedPage,
    IndexAfter,
    IndexAlternative,
    IndexCommunity,
    IndexConflict,
    IndexEnvironment,
    IndexFact,
    IndexFocal,
    IndexMaterial,
    IndexNativeName,
    IndexOverview,
    IndexPicture,
    IndexPlace,
    IndexPlacement,
    IndexQuestion,
    IndexReaction,
    IndexSearch,
    IndexSpecies,
    IndexStage,
    IndexTerm,
    IndexTiming,
    IndexTool,
)
from .curation_keys import curated_id
from .curation_records import glossary_key, picture_media_id, term_names
from .curation_rows import ConceptPlan
from .curation_structure import place_codes

__all__ = [
    "curated_page_index",
    "index_category_reactions",
    "index_conflicts",
    "index_glossary",
    "index_key_facts",
    "index_native_names",
    "index_pictures",
]


def curated_page_index(
    dossier: Dossier, concepts: ConceptPlan, codes: DistrictCodes, location_ids: set[uuid.UUID]
) -> CuratedPage:
    slug = dossier.craft_slug
    return CuratedPage(
        craft_slug=slug,
        version=dossier.version,
        curated_at=dossier.curated_at,
        coverage=dossier.coverage,
        searched=[IndexSearch(query=item.query, site=item.site) for item in dossier.searched],
        process_id=curated_id(slug, "process") if dossier.stages else None,
        craft_concepts=dict(concepts.craft_concepts),
        overview=IndexOverview(key_facts=index_key_facts(dossier)),
        conflicts=index_conflicts(dossier),
        open_questions=_questions(dossier),
        places=_places(dossier, concepts, codes, location_ids),
        communities=_communities(dossier, concepts),
        stages=_stages(dossier, concepts),
        materials=_materials(dossier, concepts),
        tools=_tools(dossier, concepts),
        reactions=_reactions(dossier),
        glossary=index_glossary(dossier, concepts),
        pictures=index_pictures(dossier),
        environment=_environment(dossier),
        native_names=index_native_names(dossier),
        claim_order=_ids(slug, [claim.id for claim in dossier.claims]),
    )


def _ids(slug: str, claim_ids: Sequence[str]) -> list[uuid.UUID]:
    return [curated_id(slug, claim_id) for claim_id in claim_ids]


def index_conflicts(dossier: Dossier) -> list[IndexConflict]:
    slug = dossier.slug
    return [
        IndexConflict(about=item.about, claim_ids=_ids(slug, item.claim_ids)) for item in dossier.conflicts
    ]


def _questions(dossier: Dossier) -> list[IndexQuestion]:
    return [
        IndexQuestion(
            key=item.id,
            question=item.question,
            settled_by=item.settled_by,
            claim_ids=_ids(dossier.craft_slug, item.claim_ids),
        )
        for item in dossier.open_questions
    ]


def _environment(dossier: Dossier) -> list[IndexEnvironment]:
    return [
        IndexEnvironment(
            factor=item.factor, place_key=item.place_id, claim_ids=_ids(dossier.craft_slug, item.claim_ids)
        )
        for item in dossier.environment
    ]


def index_key_facts(dossier: Dossier) -> list[IndexFact]:
    return [
        IndexFact(label=fact.label, value=fact.value, claim_ids=_ids(dossier.slug, fact.claim_ids))
        for fact in dossier.overview.key_facts
    ]


def _places(
    dossier: Dossier, concepts: ConceptPlan, codes: DistrictCodes, location_ids: set[uuid.UUID]
) -> list[IndexPlace]:
    slug = dossier.craft_slug
    places = []
    for place in dossier.places:
        state_lgd, district_lgd = place_codes(place, codes)
        location = curated_id(slug, "location", place.id)
        places.append(
            IndexPlace(
                key=place.id,
                name=place.name,
                kind=place.kind,
                role=place.role,
                district=place.district,
                district_lgd=district_lgd,
                state=place.state,
                state_lgd=state_lgd,
                country=place.country,
                wikidata_id=place.wikidata,
                location_id=location if location in location_ids else None,
                concept_id=concepts.places[place.id],
                claim_ids=_ids(slug, place.claim_ids),
            )
        )
    return places


def _communities(dossier: Dossier, concepts: ConceptPlan) -> list[IndexCommunity]:
    return [
        IndexCommunity(
            key=group.id,
            kind=group.kind,
            name=group.name,
            local_names=list(group.local_names),
            honours=list(group.honours),
            place_key=group.place_id,
            concept_id=concepts.ids[group.id],
            claim_ids=_ids(dossier.craft_slug, group.claim_ids),
        )
        for group in dossier.communities
    ]


def _timing(slug: str, timing: Timing | None) -> IndexTiming | None:
    return (
        None if timing is None else IndexTiming(text=timing.text, claim_id=curated_id(slug, timing.claim_id))
    )


def _stages(dossier: Dossier, concepts: ConceptPlan) -> list[IndexStage]:
    slug = dossier.craft_slug
    return [
        IndexStage(
            key=stage.id,
            stage_id=curated_id(slug, "stage", stage.id),
            concept_id=concepts.ids[stage.id],
            local_name=stage.local_name,
            order=stage.order,
            order_claim_id=curated_id(slug, stage.order_claim_id) if stage.order_claim_id else None,
            duration=_timing(slug, stage.duration),
            season=_timing(slug, stage.season),
            claim_ids=_ids(slug, stage.claim_ids),
            after=_after(slug, stage.after),
            why_claim_id=curated_id(slug, stage.why_claim_id) if stage.why_claim_id else None,
        )
        for stage in dossier.stages
    ]


def _after(slug: str, after: After | None) -> IndexAfter | None:
    if after is None:
        return None
    return IndexAfter(text=after.text, colours=list(after.colours), claim_id=curated_id(slug, after.claim_id))


def _materials(dossier: Dossier, concepts: ConceptPlan) -> list[IndexMaterial]:
    slug = dossier.craft_slug
    return [
        IndexMaterial(
            key=item.id,
            material_id=curated_id(slug, "material", item.id),
            concept_id=concepts.ids[item.id],
            name=item.name,
            kind=item.kind,
            role=item.role,
            local_names=list(item.local_names),
            botanical_name=item.botanical_name,
            pubchem_cid=item.pubchem_cid,
            claim_ids=_ids(slug, item.claim_ids),
            alternatives=[
                IndexAlternative(key=other.material_id, claim_id=curated_id(slug, other.claim_id))
                for other in item.alternatives
            ],
        )
        for item in dossier.materials
    ]


def _tools(dossier: Dossier, concepts: ConceptPlan) -> list[IndexTool]:
    slug = dossier.craft_slug
    return [
        IndexTool(
            key=item.id,
            material_id=curated_id(slug, "tool", item.id),
            concept_id=concepts.ids[item.id],
            name=item.name,
            local_names=list(item.local_names),
            claim_ids=_ids(slug, item.claim_ids),
        )
        for item in dossier.tools
    ]


def _reactions(dossier: Dossier) -> list[IndexReaction]:
    slug = dossier.craft_slug
    return [
        _reaction(
            slug,
            item,
            reaction_id=curated_id(slug, "reaction", item.id) if item.stage_id else None,
            stage_key=item.stage_id,
        )
        for item in dossier.reactions
    ]


def index_category_reactions(dossier: Dossier) -> list[IndexReaction]:
    return [_reaction(dossier.slug, item, reaction_id=None, stage_key=None) for item in dossier.reactions]


def _reaction(
    slug: str, item: Reaction, *, reaction_id: uuid.UUID | None, stage_key: str | None
) -> IndexReaction:
    return IndexReaction(
        key=item.id,
        reaction_id=reaction_id,
        stage_key=stage_key,
        kind=item.kind,
        reactants=[IndexSpecies(name=s.name, formula=s.formula) for s in item.reactants],
        products=[IndexSpecies(name=s.name, formula=s.formula) for s in item.products],
        claim_ids=_ids(slug, item.claim_ids),
    )


def index_glossary(dossier: Dossier, concepts: ConceptPlan) -> list[IndexTerm]:
    return [
        IndexTerm(
            key=term.id,
            term_key=glossary_key(term),
            term=term.term,
            names=term_names(term),
            meaning=term.meaning,
            language=term.language,
            script=term.script,
            concept_id=concepts.ids[term.id],
            claim_ids=_ids(dossier.slug, term.claim_ids),
        )
        for term in dossier.glossary
    ]


def index_pictures(dossier: Dossier) -> list[IndexPicture]:
    return [
        IndexPicture(
            key=picture.id,
            media_ref_id=picture_media_id(picture),
            caption=picture.caption,
            stage_key=picture.stage_id,
            claim_ids=_ids(dossier.slug, picture.claim_ids),
            placement=_placement(picture),
            focal=IndexFocal.model_validate(picture.focal.model_dump()) if picture.focal else None,
            width=picture.width,
            height=picture.height,
            stand_in=picture.stand_in,
        )
        for picture in dossier.pictures
    ]


def _placement(picture: Picture) -> IndexPlacement | None:
    placement = picture.placement
    if placement is None:
        return None
    return IndexPlacement(
        chapter=placement.chapter,
        role=placement.role,
        stage_key=placement.stage_id,
        material_key=placement.material_id,
    )


def index_native_names(dossier: Dossier) -> list[IndexNativeName]:
    return [
        IndexNativeName(
            text=name.text,
            language=name.language,
            script=name.script,
            claim_id=curated_id(dossier.slug, name.claim_id),
        )
        for name in dossier.native_names
    ]
