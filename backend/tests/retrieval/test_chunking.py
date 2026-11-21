import pytest

from app.core.errors import InvalidInput
from app.retrieval.chunking import CHUNK_MAX_CHARS, CHUNK_OVERLAP_MAX_CHARS, chunk_text

LIMIT = 320


def sentence(letter: str, length: int) -> str:
    return letter * (length - 1) + "."


def test_the_overlap_can_hold_a_whole_stored_quote() -> None:
    assert CHUNK_OVERLAP_MAX_CHARS == 300
    assert CHUNK_MAX_CHARS == 1200


def test_short_paragraphs_share_one_chunk_and_the_locator_names_both() -> None:
    chunks = chunk_text("First para.\n\nSecond para.")
    assert [(c.ordinal, c.text, c.locator) for c in chunks] == [
        (0, "First para.\n\nSecond para.", "paras 1-2")
    ]


def test_whitespace_collapses_and_windows_line_breaks_split_paragraphs() -> None:
    chunks = chunk_text("Alum  fixes\nmadder.\r\n \r\nIron   darkens.\n\n\n")
    assert chunks[0].text == "Alum fixes madder.\n\nIron darkens."


def test_a_word_hyphenated_at_a_line_end_is_joined_as_the_quote_matcher_joins_it() -> None:
    (chunk,) = chunk_text("Iron black is a mor-\ndant print.\n\nIt is well-known.")
    assert chunk.text == "Iron black is a mordant print.\n\nIt is well-known."


def test_a_full_chunk_starts_the_next_with_its_last_paragraph() -> None:
    a, b, c = sentence("a", 150), sentence("b", 150), sentence("c", 150)
    chunks = chunk_text(f"{a}\n\n{b}\n\n{c}", max_chars=LIMIT)
    assert [(c_.text, c_.locator) for c_ in chunks] == [
        (f"{a}\n\n{b}", "paras 1-2"),
        (f"{b}\n\n{c}", "paras 2-3"),
    ]


def test_a_long_paragraph_splits_at_sentence_ends() -> None:
    s1, s2, s3, s4 = (sentence(letter, 100) for letter in "wxyz")
    chunks = chunk_text(f"{s1} {s2} {s3} {s4}", max_chars=LIMIT)
    assert [(c.text, c.locator) for c in chunks] == [(f"{s1} {s2} {s3}", "para 1"), (f"{s3} {s4}", "para 1")]


def test_a_word_longer_than_a_chunk_is_cut_and_long_tails_are_not_repeated() -> None:
    chunks = chunk_text("y" * 700, max_chars=LIMIT)
    assert [len(c.text) for c in chunks] == [320, 320, 60]
    assert [c.ordinal for c in chunks] == [0, 1, 2]


def test_every_chunk_fits_the_limit() -> None:
    text = "\n\n".join(" ".join(f"word{n} sentence{m}." for n in range(40)) for m in range(12))
    assert all(len(c.text) <= CHUNK_MAX_CHARS for c in chunk_text(text))


def test_a_text_without_words_is_refused() -> None:
    with pytest.raises(InvalidInput, match="no words"):
        chunk_text(" \n\n \t ")


def test_a_limit_that_cannot_hold_the_overlap_is_refused() -> None:
    with pytest.raises(InvalidInput):
        chunk_text("text", max_chars=CHUNK_OVERLAP_MAX_CHARS)
