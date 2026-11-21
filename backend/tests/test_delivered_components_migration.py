from sqlalchemy import CheckConstraint

from app.models import ComponentProposal, KnowledgePiece, PagePreview
from app.models.component_kinds import GENERAL_KINDS, PIECE_KINDS
from app.models.open_work import DELIVERED_SPEC
from app.models.page_previews import PREVIEW_SUBJECT_KINDS

from .migration_scripts import migration


def test_the_delivered_components_migration_follows_the_image_screens() -> None:
    step = migration("0049_delivered_components")
    assert (step.revision, step.down_revision) == ("0049_delivered_components", "0050_image_screens")


def test_it_widens_both_kind_checks_by_the_general_kinds_only() -> None:
    step = migration("0049_delivered_components")
    renamed = migration("0056_datasets_and_materials")
    assert step.PIECE_KINDS == renamed.PIECE_KINDS_BEFORE
    assert tuple(old for old, _ in renamed.RENAMED_KINDS) == step.GENERAL_KINDS
    assert set(step.PIECE_KINDS) - set(step.PIECE_KINDS_BEFORE) == set(step.GENERAL_KINDS)
    assert set(PIECE_KINDS) >= set(GENERAL_KINDS)
    assert (KnowledgePiece.__tablename__, ComponentProposal.__tablename__) == step.KIND_CHECKS


def test_it_writes_the_delivered_columns_and_the_preview_table_as_the_models_hold_them() -> None:
    step = migration("0049_delivered_components")
    proposals = ComponentProposal.__table__
    assert {"spec", "units", "claimIds"} <= set(proposals.c.keys())
    checks = {str(item.sqltext) for item in proposals.constraints if isinstance(item, CheckConstraint)}
    assert step.DELIVERED_SPEC == DELIVERED_SPEC and DELIVERED_SPEC in checks
    assert PagePreview.__tablename__ == step.PREVIEWS
    assert step.PREVIEW_SUBJECT_KINDS == PREVIEW_SUBJECT_KINDS
    assert set(PagePreview.__table__.c.keys()) == {
        "id",
        "userId",
        "subjectKind",
        "subjectSlug",
        "document",
        "expiresAt",
        "createdAt",
    }
