import pytest

from app.composer.drafts import checked_sentence
from app.composer.prompt import SOURCE_RULES, section_system_prompt
from app.research.composition import ComposeCandidate

SHOP_PAGE = ComposeCandidate(
    id="searxng:https://shop.example.org/ajrakh",
    kind="EVIDENCE",
    text="Call 98250 12345 to order Ajrakh cloth from the printers of Ajrakhpur.",
    sourceLabel="A shop page",
    level="PROVISIONAL",
)


def test_a_drafted_sentence_carrying_a_phone_number_fails_its_check() -> None:
    raw = {
        "text": "Call 98250 12345 to order Ajrakh cloth.",
        "quotes": [{"source": SHOP_PAGE.id, "quote": "Call 98250 12345 to order Ajrakh cloth"}],
    }
    drafted = checked_sentence(raw, "Where to buy", {SHOP_PAGE.id: SHOP_PAGE})
    assert drafted.problems == ("PERSONAL_DATA: phone-like number",)
    assert not drafted.passes


@pytest.mark.parametrize("sentences_max", [8, 16])
def test_every_section_depth_asks_for_both_readings_where_sources_differ(sentences_max: int) -> None:
    assert "Where sources differ, give both readings" in section_system_prompt(sentences_max)


def test_the_source_rules_ask_for_negations_hedges_and_units_as_quoted() -> None:
    for words in ("Keep every negation", "every hedge", "keep each unit as the quote gives it"):
        assert words in SOURCE_RULES
