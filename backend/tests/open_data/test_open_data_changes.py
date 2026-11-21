import hashlib

import pytest

from app.services.open_data_changes import release_changes, row_digest, row_digests
from app.services.open_data_readme import changes_text
from app.services.open_data_rows import checked_tables, row_key
from app.services.open_data_structure_tables import NATIVE_NAMES
from app.services.open_data_tables import FAMILIES, TABLES

from .release_fixtures import STAMP, family_row, tables_with


def test_a_row_digest_is_the_sha256_of_its_sorted_compact_json() -> None:
    expected = hashlib.sha256('{"a":1,"b":"अ"}'.encode()).hexdigest()[:16]
    assert row_digest({"b": "अ", "a": 1}) == expected


def test_a_row_is_named_by_its_key_columns_joined() -> None:
    row = {"craft": "Kutch-Ajrakh", "text": "અજરખ", "language": "gu", "script": None, "claim_id": "c7"}
    assert row_key(NATIVE_NAMES, row) == "Kutch-Ajrakh|c7|અજરખ"
    assert row_key(FAMILIES, family_row("Embroidery", "Embroidery", 2)) == "Embroidery"


def test_changes_name_what_was_added_removed_and_changed_by_key() -> None:
    before = {"claims": {"a": "1", "b": "2", "c": "3"}, "sources": {"s1": "9"}}
    now = {"claims": {"b": "2", "c": "4", "d": "5"}, "sources": {"s1": "9"}}
    found = release_changes(now, before, "2026.10.01")
    assert found.previous == "2026.10.01"
    claims = found.tables["claims"]
    assert (claims.added, claims.removed, claims.changed) == (["d"], ["a"], ["c"])
    assert found.counts()["sources"] == {"added": 0, "removed": 0, "changed": 0}
    assert set(found.tables) == {table.name for table in TABLES}


def test_the_changes_file_tables_the_counts_and_lists_the_keys() -> None:
    before = {"claims": {"a": "1", "c": "3"}}
    now = {"claims": {"c": "4", "d": "5"}}
    text = changes_text(STAMP, release_changes(now, before, "2026.10.01"))
    assert "Compared with version 2026.10.01." in text
    assert "| claims | 1 | 1 | 1 |" in text
    assert "| sources | 0 | 0 | 0 |" in text
    assert "- Added: d.\n- Removed: a.\n- Changed: c.\n" in text


def test_digests_cover_every_table_by_key() -> None:
    tables = tables_with(families=[family_row("Embroidery", "Embroidery", 2)])
    digests = row_digests(tables)
    assert set(digests) == {table.name for table in TABLES}
    assert digests["families"] == {"Embroidery": row_digest(family_row("Embroidery", "Embroidery", 2))}


def test_a_row_with_other_columns_or_a_repeated_key_is_refused() -> None:
    empty = {table.name: [] for table in TABLES}
    with pytest.raises(ValueError, match="not the columns"):
        checked_tables({**empty, "families": [{"slug": "Embroidery", "name": "Embroidery"}]})
    twice = [family_row("Embroidery", "Embroidery", 1), family_row("Embroidery", "Embroidery", 2)]
    with pytest.raises(ValueError, match="share the key Embroidery"):
        checked_tables({**empty, "families": twice})
    with pytest.raises(ValueError, match="holds the tables"):
        checked_tables({"families": []})
