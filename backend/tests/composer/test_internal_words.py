import pytest

from app.composer.candidates import compose_request
from app.composer.drafts import checked_sentence
from app.research.internal_words import internal_words

from .fixtures import ALUM_CLAIM_ID, QUESTION, pack, quote, sentence

ALUM_QUOTE = "Alum is the mordant that binds alizarin to cotton"
BIDRI_OVERVIEW = (
    "The stored statements say the technique is known only in the Indian subcontinent, and that the "
    "craft has obtained a Geographical Indication registry."
)


@pytest.mark.parametrize(
    ("text", "named"),
    [
        (BIDRI_OVERVIEW, "stored statements"),
        ("According to the stored passages, alum binds the red.", "stored passages"),
        ("The given sources do not say how long the cloth soaks.", "The given sources"),
        ("These offered statements agree that alum binds the red.", "These offered statements"),
        ("Alum binds alizarin to cotton in Ajrakh.", None),
        ("The GI journal provided evidence that the cloth is printed in Kutch.", None),
        ("Printers stored the blocks in a dry room.", None),
    ],
)
def test_a_reader_sentence_naming_our_internals_is_found(text: str, named: str | None) -> None:
    assert internal_words(text) == named


def test_a_composed_sentence_naming_stored_statements_fails_its_check() -> None:
    allowed = compose_request(pack(), QUESTION).allowed
    said = "The stored statements say alum binds alizarin to cotton in Ajrakh."
    failed = checked_sentence(sentence(said, quote(ALUM_CLAIM_ID, ALUM_QUOTE)), "Alum", allowed)
    assert "INTERNAL_WORDS: stored statements" in failed.problems and not failed.passes
    plain = "Alum binds alizarin to cotton in Ajrakh."
    assert checked_sentence(sentence(plain, quote(ALUM_CLAIM_ID, ALUM_QUOTE)), "Alum", allowed).passes
