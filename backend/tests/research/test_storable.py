import hashlib
import uuid

from app.research.quotes import quote_key, quote_occurs
from app.research.storable import storable_text
from app.retrieval.chunking import chunk_text
from app.retrieval.quote_passages import Passage, QuotePassages
from app.sources.adapter import build_document

from .fixtures import evidence_item

PDF_TEXT = (
    "Calcium and sulphur distribution in red clay brick\x00 by micro X-ray uorescence mapping "
    "L.Gredmaiera,1,\x03 and the kiln\x1b record.\x0cThe bricks were fired at 950 °C.\r\n"
    "Tab\there stays."
)
CLEAN_TEXT = (
    "Calcium and sulphur distribution in red clay brick by micro X-ray uorescence mapping "
    "L.Gredmaiera,1, and the kiln record.\nThe bricks were fired at 950 °C.\r\n"
    "Tab\there stays."
)
QUOTE = "micro X-ray uorescence mapping L.Gredmaiera,1,"
RAW_QUOTE = "mapping L.Gredmaiera,1,\x03 and the kiln\x1b record"
PDF_ITEM = evidence_item(
    id="core:4242",
    adapter="core",
    url="https://core.ac.uk/works/4242",
    title="Calcium and sulphur distribution in red clay brick",
    doi=None,
    quotes=[],
)


def test_nul_and_the_c0_controls_go_and_the_visible_text_stays_byte_for_byte() -> None:
    assert storable_text(PDF_TEXT) == CLEAN_TEXT
    assert storable_text(CLEAN_TEXT) == CLEAN_TEXT
    assert not any(ord(char) < 0x20 and char not in "\t\n\r" for char in storable_text(PDF_TEXT))


def test_a_control_that_separates_lines_becomes_a_line_break_so_words_stay_apart() -> None:
    assert storable_text("page one\x0cpage two\x0bline\x1fend") == "page one\npage two\nline\nend"
    assert storable_text("a\x00b\x01c\x08d\x0ee\x1bf") == "abcdef"


def test_a_fetched_document_is_stored_as_storable_text_and_hashed_as_stored() -> None:
    document = build_document(PDF_ITEM, PDF_TEXT, "FULL_TEXT")
    assert document.text == CLEAN_TEXT
    assert document.text_sha256 == hashlib.sha256(CLEAN_TEXT.encode("utf-8")).hexdigest()
    assert "\x00" not in "".join(piece.text for piece in chunk_text(document.text))


def test_the_quote_matcher_reads_a_quote_as_the_store_keeps_it() -> None:
    assert quote_key(RAW_QUOTE) == quote_key(storable_text(RAW_QUOTE))
    assert quote_key(RAW_QUOTE) == "mapping L.Gredmaiera,1, and the kiln record"
    assert quote_occurs(QUOTE, CLEAN_TEXT)
    assert quote_occurs(RAW_QUOTE, CLEAN_TEXT)


def test_a_quote_is_held_by_the_stored_passage_of_a_cleaned_pdf() -> None:
    stored = [
        Passage(uuid.UUID(int=piece.ordinal + 1), piece.ordinal, piece.locator, piece.text, "PUBLIC")
        for piece in chunk_text(storable_text(PDF_TEXT))
    ]
    passages = QuotePassages(stored)
    for quote in (QUOTE, RAW_QUOTE, "The bricks were fired at 950 °C"):
        held = passages.holding(quote)
        assert held is not None
        assert held.chunk_id == stored[0].id
