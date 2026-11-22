from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any

from sqlalchemy import (
    ColumnElement,
    Select,
    String,
    and_,
    extract,
    func,
    literal,
    literal_column,
    or_,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB, aggregate_order_by
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    AppSetting,
    ArtisanContribution,
    ArtisanConversation,
    Claim,
    ClaimSource,
    Compound,
    Concept,
    Craft,
    CraftGiRecord,
    CraftLocation,
    CraftPrice,
    CraftSubCategory,
    CraftWorkforce,
    CuratedCategory,
    CuratedCategoryClaim,
    CuratedCraft,
    DistrictEnvValue,
    EnvDataset,
    FieldImage,
    FieldImageCraft,
    FieldPhotoReview,
    FieldRecording,
    FieldRecordingCraft,
    FieldSegment,
    FieldVoiceStream,
    ImageContribution,
    KnowledgePiece,
    Material,
    MediaAsset,
    MediaJob,
    MediaRef,
    MediaRefClaim,
    Process,
    ProcessStage,
    Reaction,
    Source,
    StageMaterial,
    Term,
    TermCraft,
    WikidataPoint,
)
from app.models.science import live_process
from app.research.craft_page import CRAFT_PAGE_SCHEMA_VERSION
from app.research.field_voices import ARTISAN_IMAGES_SETTING
from app.retrieval.field_scope import FIELD_STALE_AFTER
from app.retrieval.statements import CraftScope, scope_claims, scope_concepts

from .contributed_pictures import shown_contributions
from .page_code import page_code_fingerprint

__all__ = [
    "PAGE_VARIANTS",
    "Terms",
    "count_term",
    "counted_terms",
    "craft_compound_ids",
    "page_stamp",
    "plain_term",
    "scalar_term",
    "stamp_terms",
    "stamp_text",
]

PAGE_VARIANTS = ("OPEN", "RESEARCHER")

Terms = dict[str, ColumnElement[Any]]


async def page_stamp(session: AsyncSession, craft: Craft, variant: str) -> str:
    row = (await session.execute(stamp_terms(craft))).one()
    site = get_settings().public_web_url
    return stamp_text(dict(row._mapping), code=page_code_fingerprint(), site=site, variant=variant)


def stamp_text(terms: Mapping[str, Any], *, code: str, site: str, variant: str) -> str:
    if variant not in PAGE_VARIANTS:
        raise ValueError(f"a craft page has the variants {', '.join(PAGE_VARIANTS)}, not {variant!r}")
    record = {
        "code": code,
        "site": site,
        "schemaVersion": CRAFT_PAGE_SCHEMA_VERSION,
        "variant": variant,
        "terms": {key: plain_term(value) for key, value in sorted(terms.items())},
    }
    text = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stamp_terms(craft: Craft) -> Select[Any]:
    own = select(Claim.id).where(scope_claims(CraftScope(craft.id, craft.subCategoryId)))
    family = select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId.in_(_family(craft)))
    shown = or_(MediaRefClaim.claimId.in_(own), MediaRefClaim.claimId.in_(family))
    terms = {**_curation_terms(craft), **_claim_terms(craft, own), **_family_terms(family)}
    terms |= {**_relative_terms(craft), **_science_terms(craft), **_picture_terms(shown)}
    terms |= {**_place_terms(craft), **_piece_terms(craft), **_voice_terms(craft), **_testimony_terms(craft)}
    terms |= _contributed_terms(craft)
    return select(*(value.label(key) for key, value in terms.items()))


def craft_compound_ids(craft: Craft) -> Select[Any]:
    return select(Material.compoundId).where(Material.id.in_(_craft_materials(craft)))


def _craft_materials(craft: Craft) -> Select[Any]:
    processes = select(Process.id).where(Process.craftId == craft.id, live_process())
    stages = select(ProcessStage.id).where(ProcessStage.processId.in_(processes))
    staged = select(StageMaterial.materialId).where(StageMaterial.stageId.in_(stages))
    concepts = scope_concepts(CraftScope(craft.id, craft.subCategoryId))
    return select(Material.id).where(or_(Material.id.in_(staged), Material.conceptId.in_(concepts)))


def _family(craft: Craft) -> Select[Any]:
    return select(CraftSubCategory.categoryId).where(CraftSubCategory.id == craft.subCategoryId)


def _curation_terms(craft: Craft) -> Terms:
    family = _family(craft)
    return {
        "curatedVersion": scalar_term(CuratedCraft.version, CuratedCraft.craftId == craft.id),
        "curatedAt": scalar_term(CuratedCraft.updatedAt, CuratedCraft.craftId == craft.id),
        "familyVersion": scalar_term(CuratedCategory.version, CuratedCategory.categoryId.in_(family)),
        "familyAt": scalar_term(CuratedCategory.updatedAt, CuratedCategory.categoryId.in_(family)),
        "craftAt": scalar_term(Craft.updatedAt, Craft.id == craft.id),
    }


def _claim_terms(craft: Craft, own: Select[Any]) -> Terms:
    concepts = scope_concepts(CraftScope(craft.id, craft.subCategoryId))
    cited = select(ClaimSource.sourceId).where(ClaimSource.claimId.in_(own))
    glossary = select(TermCraft.termId).where(TermCraft.craftId == craft.id)
    return {
        **counted_terms("concepts", Concept.id, Concept.updatedAt, Concept.id.in_(concepts)),
        **counted_terms("claims", Claim.id, Claim.updatedAt, Claim.id.in_(own)),
        **counted_terms("citations", ClaimSource.id, ClaimSource.updatedAt, ClaimSource.claimId.in_(own)),
        **counted_terms("sources", Source.id, Source.updatedAt, Source.id.in_(cited)),
        **counted_terms(
            "glossaryLinks", TermCraft.termId, TermCraft.createdAt, TermCraft.craftId == craft.id
        ),
        **counted_terms("glossary", Term.id, Term.updatedAt, Term.id.in_(glossary)),
    }


def _family_terms(family: Select[Any]) -> Terms:
    return {
        **counted_terms("familyClaims", Claim.id, Claim.updatedAt, Claim.id.in_(family)),
        **counted_terms(
            "familyCitations", ClaimSource.id, ClaimSource.updatedAt, ClaimSource.claimId.in_(family)
        ),
    }


def _relative_terms(craft: Craft) -> Terms:
    kin = select(Craft.id).where(Craft.subCategoryId == craft.subCategoryId, Craft.id != craft.id)
    concepts = select(Concept.id).where(Concept.craftId.in_(kin))
    return {
        **counted_terms("relatives", Craft.id, Craft.updatedAt, Craft.id.in_(kin)),
        **counted_terms(
            "relativeCurations", CuratedCraft.craftId, CuratedCraft.updatedAt, CuratedCraft.craftId.in_(kin)
        ),
        **counted_terms("relativeClaims", Claim.id, Claim.updatedAt, Claim.subjectId.in_(concepts)),
    }


def _science_terms(craft: Craft) -> Terms:
    processes = select(Process.id).where(Process.craftId == craft.id, live_process())
    stages = select(ProcessStage.id).where(ProcessStage.processId.in_(processes))
    materials = _craft_materials(craft)
    compounds = craft_compound_ids(craft)
    return {
        **counted_terms("processes", Process.id, Process.updatedAt, Process.id.in_(processes)),
        **counted_terms("stages", ProcessStage.id, ProcessStage.updatedAt, ProcessStage.id.in_(stages)),
        **counted_terms("reactions", Reaction.id, Reaction.updatedAt, Reaction.stageId.in_(stages)),
        **counted_terms("materials", Material.id, Material.updatedAt, Material.id.in_(materials)),
        **counted_terms("compounds", Compound.id, Compound.updatedAt, Compound.id.in_(compounds)),
        "conformersAt": scalar_term(func.max(Compound.conformerKeptAt), Compound.id.in_(compounds)),
    }


def _picture_terms(shown: ColumnElement[bool]) -> Terms:
    linked = select(MediaRefClaim.mediaRefId).where(shown)
    return {
        **counted_terms("pictures", MediaRefClaim.mediaRefId, MediaRefClaim.createdAt, shown),
        **counted_terms("mediaRefs", MediaRef.id, MediaRef.updatedAt, MediaRef.id.in_(linked)),
    }


def _place_terms(craft: Craft) -> Terms:
    districts = select(CraftLocation.districtLgd).where(CraftLocation.craftId == craft.id)
    places = func.jsonb_array_elements(CuratedCraft.page["places"], type_=JSONB)
    named = select(places["wikidataId"].astext).where(CuratedCraft.craftId == craft.id)
    return {
        **counted_terms(
            "locations", CraftLocation.id, CraftLocation.updatedAt, CraftLocation.craftId == craft.id
        ),
        **counted_terms(
            "gi", CraftGiRecord.craftId, CraftGiRecord.updatedAt, CraftGiRecord.craftId == craft.id
        ),
        **counted_terms("prices", CraftPrice.id, CraftPrice.updatedAt, CraftPrice.craftId == craft.id),
        **counted_terms(
            "workforce", CraftWorkforce.id, CraftWorkforce.updatedAt, CraftWorkforce.craftId == craft.id
        ),
        **counted_terms("datasets", EnvDataset.id, EnvDataset.updatedAt, EnvDataset.id.is_not(None)),
        **counted_terms(
            "geoValues",
            DistrictEnvValue.id,
            DistrictEnvValue.updatedAt,
            DistrictEnvValue.districtLgd.in_(districts),
        ),
        **counted_terms(
            "points", WikidataPoint.wikidataId, WikidataPoint.keptAt, WikidataPoint.wikidataId.in_(named)
        ),
    }


def _piece_terms(craft: Craft) -> Terms:
    own = KnowledgePiece.craftId == craft.id
    jobs = select(MediaJob.id).where(MediaJob.craftId == craft.id)
    return {
        **counted_terms("pieces", KnowledgePiece.id, KnowledgePiece.updatedAt, own),
        "piecesStaleAt": scalar_term(func.max(KnowledgePiece.staleSince), own),
        "piecesHiddenAt": scalar_term(func.max(KnowledgePiece.hiddenAt), own),
        "piecesSuperseded": count_term(KnowledgePiece.id, own & KnowledgePiece.supersededById.is_not(None)),
        "piecesShown": count_term(KnowledgePiece.id, own & KnowledgePiece.hiddenAt.is_(None)),
        **counted_terms("aiMedia", MediaAsset.id, MediaAsset.updatedAt, MediaAsset.jobId.in_(jobs)),
    }


def _voice_terms(craft: Craft) -> Terms:
    recordings = select(FieldRecordingCraft.recordingId).where(FieldRecordingCraft.craftId == craft.id)
    images = select(FieldImageCraft.imageId).where(FieldImageCraft.craftId == craft.id)
    recorded = FieldRecording.id.in_(recordings)
    pictured = FieldImage.id.in_(images)
    fresh = FieldVoiceStream.lastContactAt >= func.now() - FIELD_STALE_AFTER
    stream = FieldVoiceStream.stream + literal(":") + FieldVoiceStream.portal
    streams = func.string_agg(stream, aggregate_order_by(literal_column("','"), stream))
    return {
        **counted_terms("fieldRecordings", FieldRecording.id, FieldRecording.updatedAt, recorded),
        "fieldRecordingsShown": count_term(FieldRecording.id, recorded & FieldRecording.hiddenAt.is_(None)),
        "fieldRecordingsHiddenAt": scalar_term(func.max(FieldRecording.hiddenAt), recorded),
        "fieldSegments": count_term(FieldSegment.id, FieldSegment.recordingId.in_(recordings)),
        "fieldQuotable": count_term(
            FieldSegment.id, and_(FieldSegment.recordingId.in_(recordings), FieldSegment.quotable)
        ),
        **counted_terms("fieldImages", FieldImage.id, FieldImage.updatedAt, pictured),
        "fieldImagesShown": count_term(FieldImage.id, pictured & FieldImage.hiddenAt.is_(None)),
        "fieldImagesHiddenAt": scalar_term(func.max(FieldImage.hiddenAt), pictured),
        "fieldPhotoDecidedAt": scalar_term(
            func.max(FieldPhotoReview.decidedAt), FieldPhotoReview.imageId.in_(images)
        ),
        "freshStreams": select(streams).where(fresh).scalar_subquery(),
        "artisanImages": scalar_term(AppSetting.value.cast(String), AppSetting.key == ARTISAN_IMAGES_SETTING),
        "artisanImagesAt": scalar_term(AppSetting.updatedAt, AppSetting.key == ARTISAN_IMAGES_SETTING),
    }


def _testimony_terms(craft: Craft) -> Terms:
    given = ArtisanContribution.craftId == craft.id
    talks = ArtisanConversation.craftId == craft.id
    return {
        **counted_terms("testimony", ArtisanContribution.id, ArtisanContribution.updatedAt, given),
        "testimonyApprovedAt": scalar_term(func.max(ArtisanContribution.approvedAt), given),
        "testimonyWithdrawnAt": scalar_term(func.max(ArtisanContribution.withdrawnAt), given),
        "testimonyApproved": count_term(
            ArtisanContribution.id, and_(given, ArtisanContribution.status == "APPROVED")
        ),
        **counted_terms("conversations", ArtisanConversation.id, ArtisanConversation.updatedAt, talks),
        "conversationsDeleted": count_term(
            ArtisanConversation.id, and_(talks, ArtisanConversation.deletedAt.is_not(None))
        ),
    }


def _contributed_terms(craft: Craft) -> Terms:
    shown = ImageContribution.id.in_(shown_contributions(craft.id))
    assets = select(ImageContribution.assetId).where(shown)
    return {
        **counted_terms("contributed", ImageContribution.id, ImageContribution.updatedAt, shown),
        **counted_terms("contributedAssets", MediaAsset.id, MediaAsset.updatedAt, MediaAsset.id.in_(assets)),
    }


def counted_terms(name: str, key: Any, changed: Any, where: ColumnElement[bool]) -> Terms:
    return {
        f"{name}Count": count_term(key, where),
        f"{name}At": select(func.sum(extract("epoch", changed))).where(where).scalar_subquery(),
    }


def count_term(key: Any, where: ColumnElement[bool]) -> ColumnElement[Any]:
    return select(func.count(key)).where(where).scalar_subquery()


def scalar_term(value: Any, where: ColumnElement[bool]) -> ColumnElement[Any]:
    return select(value).where(where).limit(1).scalar_subquery()


def plain_term(value: Any) -> Any:
    if value is None or isinstance(value, (int, float, str, bool)):
        return value
    isoformat = getattr(value, "isoformat", None)
    return isoformat() if callable(isoformat) else str(value)
