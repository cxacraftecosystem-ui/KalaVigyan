import hashlib
import json
from pathlib import Path

import pytest

from app.data.source_texts import SOURCE_FILE, chapter_pages, load_vendored_texts, vendored_texts
from app.services.claim_seed import load_seed_claims, seed_id
from app.services.claim_seed_passages import seed_passages

WOOD_HANDBOOK = "inf:f388592d6a73"
CITED_CHAPTERS = {
    "structure and function of wood",
    "moisture relations and physical properties of wood",
    "mechanical properties of wood",
    "drying and control of moisture content and dimensional changes",
    "finishing of wood",
}
PAGES = "CHAPTER 4\nMoisture\n4-1\nWood is hygroscopic.\nTable 4-1 gives values.\n4-2\nGreen wood\n4-4\nDry wood\n4-3\nstill 4-4"


def test_a_chapter_splits_at_each_later_page_label_and_leaves_the_label_out() -> None:
    pages = chapter_pages(4, "Moisture", PAGES)
    assert [(page.page, page.text) for page in pages] == [
        ("4-1", "CHAPTER 4\nMoisture\nWood is hygroscopic.\nTable 4-1 gives values."),
        ("4-2", "Green wood"),
        ("4-4", "Dry wood\n4-3\nstill 4-4"),
    ]
    assert pages[0].locator == "Chapter 4, Moisture, p. 4-1"


def test_the_wood_handbook_s_cited_chapters_are_vendored_as_read() -> None:
    (text,) = [text for text in vendored_texts() if text.seed_source == WOOD_HANDBOOK]
    assert {page.chapter_title.casefold() for page in text.pages} == CITED_CHAPTERS
    seed = load_seed_claims()
    cited = {
        cite["locator"].casefold()
        for claim in seed["claims"]
        for cite in claim["sources"]
        if cite["sourceId"] == WOOD_HANDBOOK and cite.get("locator")
    }
    assert cited and cited <= CITED_CHAPTERS


def test_the_seed_stores_the_handbook_s_pages_as_its_passages() -> None:
    planned = {passages.source_id: passages.chunks for passages in seed_passages(load_seed_claims())}
    chunks = planned[seed_id("source", WOOD_HANDBOOK)]
    assert {chunk.acl for chunk in chunks} == {"PUBLIC"}
    assert all(chunk.locator.startswith("Chapter ") for chunk in chunks)
    assert any("fiber saturation point" in chunk.text for chunk in chunks)


def test_a_vendored_text_that_is_not_what_was_read_is_refused(tmp_path: Path) -> None:
    folder = tmp_path / "report"
    folder.mkdir()
    (folder / "chapter_01.txt").write_text("1-1\nEdited by hand.\n", encoding="utf-8")
    read = hashlib.sha256(b"1-1\nAs read.").hexdigest()
    record = {
        "schemaVersion": 1,
        "seedSource": "inf:report",
        "title": "A report",
        "chapters": [{"chapter": 1, "title": "One", "file": "chapter_01.txt", "textSha256": read}],
    }
    (folder / SOURCE_FILE).write_text(json.dumps(record), encoding="utf-8")
    with pytest.raises(ValueError, match="not the text its reader read"):
        load_vendored_texts(tmp_path)
