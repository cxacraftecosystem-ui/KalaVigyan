from app.services.write_back_passages import PASSAGE_MAX_CHARS, passage_around

QUOTE = "clay is aged for two days"
SHORT_PARAGRAPHS = (
    "Jaipur blue pottery uses quartz frit.\n"
    "\n"
    "In the workshop the clay is aged for two days. It is then wedged by foot.\n"
    "  \n"
    "The kiln is fired with wood."
)


def filler(number: int) -> str:
    return f"S{number:02d} " + "a" * 95 + "."


def hundred_char_sentences() -> list[str]:
    sentences = [filler(number) for number in range(30)]
    sentences[15] = "The clay is aged for two days " + "b" * 69 + "."
    return sentences


def test_a_quote_s_passage_is_the_paragraph_that_holds_it() -> None:
    assert passage_around(SHORT_PARAGRAPHS, QUOTE) == (
        "In the workshop the clay is aged for two days. It is then wedged by foot."
    )


def test_a_long_text_without_paragraphs_gives_the_quote_s_neighbours_within_the_bound() -> None:
    sentences = hundred_char_sentences()
    assert all(len(sentence) == 100 for sentence in sentences)
    assert PASSAGE_MAX_CHARS == 1200
    passage = passage_around(" ".join(sentences), QUOTE)
    assert passage == " ".join(sentences[10:21])
    assert len(passage) == 1110


def test_a_paragraph_over_the_bound_is_cut_at_sentence_ends_around_the_quote() -> None:
    sentences = hundred_char_sentences()
    text = "A short first paragraph.\n\n" + " ".join(sentences) + "\n\nA short last paragraph."
    assert passage_around(text, QUOTE) == " ".join(sentences[10:21])


def test_a_quote_at_the_start_grows_only_after_it() -> None:
    sentences = [filler(number) for number in range(20)]
    sentences[0] = "The clay is aged for two days " + "b" * 69 + "."
    assert passage_around(" ".join(sentences), QUOTE) == " ".join(sentences[0:11])


def test_a_quote_the_text_does_not_hold_has_no_passage() -> None:
    assert passage_around(SHORT_PARAGRAPHS, "the glaze is fired twice over") is None
