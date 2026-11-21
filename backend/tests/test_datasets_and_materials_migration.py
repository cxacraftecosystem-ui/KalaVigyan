from app.models import ComponentProposal, DatasetTable, DatasetUpload, EnvDataset, KnowledgePiece
from app.models.component_kinds import COMPONENT_KINDS, GENERAL_KINDS, PIECE_KINDS
from app.models.crafts import DATASET_ORIGINS

from .migration_scripts import migration

STEP = migration("0056_datasets_and_materials")
RETIRED = {"general_drawing", "general_chart", "general_table", "general_timeline", "general_map_layer"}


def test_it_follows_the_answer_gaps_migration() -> None:
    assert (STEP.revision, STEP.down_revision) == ("0056_datasets_and_materials", "0055_answer_gaps")


def test_it_renames_each_general_kind_to_the_one_kind_of_its_job() -> None:
    assert dict(STEP.RENAMED_KINDS) == {
        "general_drawing": "drawing",
        "general_chart": "chart",
        "general_table": "fact_table",
        "general_timeline": "timeline",
        "general_map_layer": "map_layer",
    }
    assert STEP.PIECE_KINDS == PIECE_KINDS
    assert set(STEP.PIECE_KINDS_BEFORE) - set(PIECE_KINDS) == RETIRED
    assert set(PIECE_KINDS) - set(STEP.PIECE_KINDS_BEFORE) == {"drawing"}
    assert set(COMPONENT_KINDS) - set(STEP.COMPONENT_KINDS_BEFORE) == {"drawing"}
    assert set(GENERAL_KINDS) == {new for _, new in STEP.RENAMED_KINDS}
    assert (KnowledgePiece.__tablename__, ComponentProposal.__tablename__) == STEP.KIND_CHECKS


def test_stored_documents_name_their_components_by_the_new_kinds() -> None:
    sql = STEP.DOCUMENT_KINDS.format(old="general_table", new="fact_table")
    assert 'UPDATE "MonographDocument"' in sql
    assert "WHEN c ->> 'kind' = 'general_table' THEN jsonb_set(c, '{kind}', '\"fact_table\"')" in sql
    assert '\'[{"kind": "general_table"}]\'' in sql


def test_it_adds_the_dataset_record_columns_and_tables_the_models_hold() -> None:
    columns = set(EnvDataset.__table__.c.keys())
    assert {
        "version",
        "doi",
        "landingUrl",
        "origin",
        "proposedById",
        "crs",
        "redistributable",
        "sha256",
    } <= columns
    assert STEP.ORIGINS == DATASET_ORIGINS == ("SITE", "CONTRIBUTED")
    assert (DatasetTable.__tablename__, DatasetUpload.__tablename__) == STEP.NEW_TABLES
    assert set(DatasetTable.__table__.c.keys()) == {
        "id",
        "datasetId",
        "columns",
        "rows",
        "rowCount",
        "byteSize",
        "sha256",
        "createdAt",
    }
    assert {"slotHash", "record", "sha256", "expiresAt", "usedAt", "datasetId"} <= set(
        DatasetUpload.__table__.c.keys()
    )
