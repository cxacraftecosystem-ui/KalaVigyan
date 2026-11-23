from __future__ import annotations

from pathlib import Path

import pytest

import atomic_write
from atomic_write import write_text_atomically
from curation import output
from hygiene import baseline


def test_text_is_written_whole_with_lf_endings_and_replaces_the_old_file(tmp_path: Path) -> None:
    target = tmp_path / "deep" / "index.json"
    write_text_atomically(target, "first\r\n")
    write_text_atomically(target, "second\nline\n")
    assert target.read_bytes() == b"second\nline\n"
    assert [path.name for path in target.parent.iterdir()] == ["index.json"]


def test_a_failed_replace_leaves_no_temporary_file(tmp_path: Path) -> None:
    occupied = tmp_path / "occupied"
    occupied.mkdir()
    (occupied / "inside.txt").write_text("kept", encoding="utf-8")
    with pytest.raises(OSError):
        write_text_atomically(occupied, "text")
    assert sorted(path.name for path in tmp_path.iterdir()) == ["occupied"]


def test_curation_and_the_hygiene_baseline_write_through_the_one_writer() -> None:
    assert output.write_text_atomically is atomic_write.write_text_atomically
    assert baseline.write_text_atomically is atomic_write.write_text_atomically
