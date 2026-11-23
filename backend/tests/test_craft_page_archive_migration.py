from app.models import Base
from app.research.craft_origins import ItemOrigin

from .db.previous_release_probe import RETIRED_TABLES
from .migration_scripts import migration

STEP = migration("0091_craft_page_archive_dropped")
CREATED = migration("0031_craft_page_chapters")


def test_it_follows_the_head_of_round_7s_chain() -> None:
    assert (STEP.revision, STEP.down_revision) == (
        "0091_craft_page_archive_dropped",
        "0086_mcp_call_name_required",
    )


def test_it_drops_the_archive_no_model_maps_and_the_probe_leaves_unread_once_dropped() -> None:
    assert STEP.ARCHIVE == "CraftPageArchive"
    assert STEP.ARCHIVE in CREATED.NEW_TABLES
    assert STEP.ARCHIVE not in Base.metadata.tables
    assert {STEP.ARCHIVE} == RETIRED_TABLES
    assert STEP.VARIANTS == CREATED.VARIANTS


def test_an_item_s_origin_no_longer_names_a_reader_s_question() -> None:
    assert "from_question" not in ItemOrigin.model_fields
    origin = ItemOrigin(basis="CURATED", generated=None, model=None, generated_on=None)
    assert origin.model_dump(mode="json", by_alias=True) == {
        "basis": "CURATED",
        "generated": None,
        "model": None,
        "generatedOn": None,
    }
