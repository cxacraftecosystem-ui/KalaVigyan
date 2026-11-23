import uuid

from app.retrieval.chunking import chunk_text
from app.retrieval.quote_passages import Holding, Passage, QuotePassages, spanned_locator

FIRST_PARAGRAPH = " ".join(f"first{n:03d}" for n in range(110))
SECOND_PARAGRAPH = " ".join(f"second{n:03d}" for n in range(100))
SPANNING_QUOTE = " ".join(
    [*(f"first{n:03d}" for n in range(95, 110)), *(f"second{n:03d}" for n in range(10))]
)


def passages_of(text: str, acls: tuple[str, ...] = ()) -> QuotePassages:
    chunks = chunk_text(text)
    return QuotePassages(
        [
            Passage(
                uuid.uuid5(uuid.NAMESPACE_URL, f"passage/{chunk.ordinal}"),
                chunk.ordinal,
                chunk.locator,
                chunk.text,
                acl,
            )
            for chunk, acl in zip(chunks, acls or ("PUBLIC",) * len(chunks), strict=True)
        ]
    )


def test_the_two_long_paragraphs_make_two_passages_with_no_overlap() -> None:
    assert (len(FIRST_PARAGRAPH), len(SECOND_PARAGRAPH), len(SPANNING_QUOTE)) == (989, 999, 234)
    chunks = chunk_text(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}")
    assert [(chunk.text, chunk.locator) for chunk in chunks] == [
        (FIRST_PARAGRAPH, "para 1"),
        (SECOND_PARAGRAPH, "para 2"),
    ]


def test_a_quote_one_passage_holds_rests_on_that_passage() -> None:
    passages = passages_of(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}")
    first, second = passages.passages
    assert passages.holding("first001 first002 first003") == Holding(first.id, "para 1", "PUBLIC")
    assert passages.holding("second098 second099") == Holding(second.id, "para 2", "PUBLIC")


def test_a_quote_across_two_passages_rests_on_the_first_with_both_paragraphs() -> None:
    passages = passages_of(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}")
    assert passages.holding(SPANNING_QUOTE) == Holding(passages.passages[0].id, "paras 1-2", "PUBLIC")


def test_passages_of_different_access_are_never_joined_and_a_missing_quote_rests_nowhere() -> None:
    mixed = passages_of(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}", ("PUBLIC", "RESEARCHER"))
    assert mixed.holding(SPANNING_QUOTE) is None
    assert passages_of(FIRST_PARAGRAPH).holding("a sentence the page never held") is None


def test_a_quote_passage_and_the_transcript_window_after_it_are_never_joined() -> None:
    first, second = passages_of(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}").passages
    joined = QuotePassages([first, second])
    windowed = Passage(second.id, second.ordinal, second.locator, second.text, "PUBLIC", "WINDOW")
    window = QuotePassages([first, windowed])
    assert joined.holding(SPANNING_QUOTE) == Holding(first.id, "paras 1-2", "PUBLIC")
    assert window.holding(SPANNING_QUOTE) is None
    assert window.holding("second098 second099") == Holding(second.id, "para 2", "PUBLIC")


def test_a_span_of_paragraph_locators_runs_from_the_first_to_the_last() -> None:
    assert spanned_locator("paras 1-2", "paras 2-3") == "paras 1-3"
    assert spanned_locator("para 4", "para 4") == "para 4"
    assert spanned_locator("p. 12", "para 3") == "p. 12"
    assert spanned_locator(None, "para 3") is None


def test_a_kept_passage_follows_the_last_ordinal() -> None:
    assert QuotePassages([]).next_ordinal() == 0
    assert passages_of(f"{FIRST_PARAGRAPH}\n\n{SECOND_PARAGRAPH}").next_ordinal() == 2
