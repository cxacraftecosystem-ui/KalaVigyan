import pytest

from app.research.composition import ComposeCandidate, ComposedSentence, QuotedSpan, sentence_violations
from app.research.sentence_support import NUMBER_WORD_VALUES, number_words_in

BAGRU = "alum is used as a mordant in Bagru printing"
TWICE = "the cloth is dyed twice in indigo"
CELSIUS = "the bath is kept at 30 °C"
IRON = "the red may come from iron"
VAT = "indigo is reduced by lime and jaggery in the vat"
MARKET = "the market in Bhuj opens every Sunday morning"
MARKET_INDIGO = "the market in Bhuj opens every Sunday morning to sell indigo"
SHOP = "Ajrakh is sold at www.example.in to buyers"
PHONE = "Call 98250 12345 to order Ajrakh cloth"


def evidence(number: int, text: str) -> ComposeCandidate:
    return ComposeCandidate(
        id=f"searxng:https://pages.example.org/{number}",
        kind="EVIDENCE",
        text=text,
        sourceLabel="A web page",
        level="PROVISIONAL",
    )


def kinds(text: str, *quoted: tuple[ComposeCandidate, str]) -> list[tuple[str, str]]:
    allowed = {candidate.id: candidate for candidate, _ in quoted}
    sentence = ComposedSentence(
        text=text,
        evidenceIds=list(allowed),
        spans=[QuotedSpan(ref=candidate.id, text=quote) for candidate, quote in quoted],
    )
    return [(v.kind, v.detail) for v in sentence_violations(sentence, allowed)]


def one(text: str, quote: str) -> list[tuple[str, str]]:
    return kinds(text, (evidence(1, quote), quote))


def test_a_negation_its_quote_does_not_hold_is_refused() -> None:
    assert one("Alum is not used as a mordant in Bagru printing.", BAGRU) == [
        ("NEGATION_CHANGED", "the sentence holds 1 negation(s) where its quotes hold 0 to 0")
    ]
    assert one("Alum is used as a mordant in Bagru printing.", BAGRU) == []


def test_a_negation_the_quote_holds_must_stay() -> None:
    assert one(
        "Alum is used as a mordant in Bagru printing.", "alum is never used as a mordant in Bagru"
    ) == [("NEGATION_CHANGED", "the sentence holds 0 negation(s) where its quotes hold 1 to 1")]


def test_a_number_word_its_quote_does_not_hold_is_refused() -> None:
    assert one("The cloth is dyed three times.", TWICE) == [("NUMBER_WORD", "three")]
    assert one("The cloth is dyed twice.", TWICE) == []
    assert one("The cloth is dyed two times.", TWICE) == []


@pytest.mark.parametrize(
    ("text", "words"),
    [
        ("No one dyes it, and one another of the vats is one of three.", ["three"]),
        ("The two vats hold a dozen cloths and half the dye.", ["two", "dozen", "half"]),
        ("Each one of the blocks is used once.", []),
    ],
)
def test_number_words_are_read_and_one_as_a_pronoun_is_not(text: str, words: list[str]) -> None:
    assert number_words_in(text) == words
    assert all(word in NUMBER_WORD_VALUES for word in words)


def test_a_unit_that_differs_from_the_quote_is_refused() -> None:
    assert one("The bath is kept at 30 °F.", CELSIUS) == [("UNIT_CHANGED", "30 °F")]
    assert one("The bath is kept at 30 °C.", CELSIUS) == []


def test_a_hedge_every_quote_carries_must_stay() -> None:
    assert one("The red comes from iron.", IRON) == [("DROPPED_HEDGE", "may")]
    assert one("The red may come from iron.", IRON) == []
    assert one("The red probably comes from iron.", IRON) == []


def test_a_co_cited_source_whose_quote_is_about_something_else_is_refused() -> None:
    text = "Indigo is reduced by lime and jaggery in the vat."
    vat, market = evidence(1, VAT), evidence(2, MARKET)
    assert kinds(text, (vat, VAT), (market, MARKET)) == [("UNRELATED_SPAN", market.id)]
    sells = evidence(3, MARKET_INDIGO)
    assert kinds(text, (vat, VAT), (sells, MARKET_INDIGO)) == [("UNRELATED_SPAN", sells.id)]
    assert kinds(text, (vat, VAT)) == []


def test_a_sentence_carrying_a_link_or_a_phone_number_is_refused() -> None:
    assert one("Ajrakh is sold at www.example.in to buyers.", SHOP) == [
        ("LINK_OR_MARKUP", "the sentence carries a link or markup")
    ]
    assert one("Call 98250 12345 to order Ajrakh cloth.", PHONE) == [("PERSONAL_DATA", "phone-like number")]
