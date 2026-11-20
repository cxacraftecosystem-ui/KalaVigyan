from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.dialects import postgresql

from app.data import curation_scopes, monograph_files
from app.services import (
    component_library,
    monograph_document,
    monograph_generated_drawings,
    open_work_components,
    open_work_pages,
    open_work_subjects,
)

from .test_open_work_queries import CRAFT

BACKEND = Path(__file__).resolve().parents[1]


def test_the_monographs_folder_and_its_content_file_have_one_home_in_the_data() -> None:
    assert monograph_files.MONOGRAPHS_DIR == BACKEND / "app" / "data" / "monographs"
    assert monograph_files.CONTENT_FILE == "content.json"
    for module in (monograph_document, open_work_pages, monograph_generated_drawings):
        assert module.MONOGRAPHS_DIR is monograph_files.MONOGRAPHS_DIR
        assert module.CONTENT_FILE is monograph_files.CONTENT_FILE
    assert (monograph_files.MONOGRAPHS_DIR / "Kutch-Ajrakh" / "content.json").is_file()


@pytest.mark.parametrize(
    ("catch_all", "practice", "family"),
    [
        (True, ["Gujarat"], True),
        (False, ["All India"], True),
        (False, ["Gujarat"], False),
        (False, ["All India", "Gujarat"], False),
        (False, [], False),
    ],
)
def test_a_craft_is_a_family_when_it_is_a_catch_all_or_practised_in_all_india_only(
    catch_all: bool, practice: list[str], family: bool
) -> None:
    assert curation_scopes.is_family(catch_all, practice) is family
    assert open_work_subjects.is_family is curation_scopes.is_family


def test_open_work_and_the_library_share_one_registered_rule_and_one_applies_to_query() -> None:
    assert open_work_components.registered_pieces is component_library.registered_pieces
    statement: Any = component_library.applies_to([CRAFT])
    compiled = str(statement.compile(dialect=postgresql.dialect()))
    assert compiled.count("UNION") == 6
    for joined in ('"Concept"', '"ProcessStage"', '"Material"', '"StageMaterial"', '"CraftLocation"'):
        assert joined in compiled
    assert [column.name for column in statement.selected_columns] == ["craft", "piece"]
