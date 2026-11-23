import copy
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.research.blocks_climate import ClimateTrend
from app.research.blocks_insight import PriceRange, UnitConversion
from app.research.blocks_learning import QUIZ_BLANK, quiz_prompt
from app.research.explainer import Block
from app.research.measures import UNIT_DEFINITIONS, metric_value

from ..contracts.phase_d_golden import phase_d_blocks

BLOCK = TypeAdapter(Block)
KUT_QUOTE = "a seer of kut weighed 0.933 kg in Kachchh"


def block(block_id: str) -> dict[str, Any]:
    return copy.deepcopy(phase_d_blocks()[block_id])


def refused(payload: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        BLOCK.validate_python(payload)


def sentence(text: str, quote: str, claim: str = "c1", source: str = "s1") -> dict[str, Any]:
    return {
        "id": f"t.{claim}",
        "text": text,
        "level": "PROVISIONAL",
        "citations": [
            {
                "id": f"cite-{claim}",
                "claimId": claim,
                "sourceId": source,
                "quote": quote,
                "locator": "p. 1",
                "context": None,
                "evidence": "QUOTED",
                "level": "PROVISIONAL",
            }
        ],
        "translated": False,
        "terms": [],
    }


def test_a_quiz_prompt_blanks_the_first_occurrence_of_the_key() -> None:
    assert quiz_prompt("Alum fixes alum.", "alum") == f"Alum fixes {QUIZ_BLANK}."
    with pytest.raises(ValueError, match="not in the keyed sentence"):
        quiz_prompt("Kut is black.", "alum")


def test_a_quiz_question_is_its_keyed_sentence_with_the_key_blanked() -> None:
    quiz = block("s1.b1")
    quiz["questions"][0]["prompt"] = "Which material fastens the colours?"
    refused(quiz, "keyed sentence with the key blanked")


def test_a_quiz_option_is_a_term_its_sentence_marks() -> None:
    quiz = block("s1.b1")
    quiz["questions"][0]["options"][1]["text"] = "Iron"
    refused(quiz, "is a term its cited sentence marks")


def test_a_distractor_comes_from_another_claim_and_is_not_stated_by_the_key() -> None:
    quiz = block("s1.b1")
    question = quiz["questions"][2]
    question["options"][1]["sentence"]["citations"] = question["options"][0]["sentence"]["citations"]
    refused(quiz, "drawn from a claim other than the key's")
    quiz = block("s1.b1")
    keyed = quiz["questions"][0]["options"][0]["sentence"]
    keyed["citations"][0]["quote"] += " Kut is not a mordant."
    refused(quiz, "stated by the keyed sentence")


def test_a_compare_row_sets_two_crafts_side_by_side_and_names_its_term() -> None:
    compare = block("s3.b1")
    compare["rows"][0]["cells"][1] = None
    refused(compare, "at least two crafts side by side")
    compare = block("s3.b1")
    compare["rows"][0]["term"] = {"key": "kut", "label": "Kut"}
    refused(compare, "named by every sentence it shows")
    compare = block("s3.b1")
    compare["rows"][4] = copy.deepcopy(compare["rows"][3])
    refused(compare, "compares each aspect once")


def test_a_concept_is_shared_by_its_focus_craft_and_named_by_every_craft() -> None:
    graph = block("s2.b1")
    graph["nodes"][0]["crafts"] = graph["nodes"][0]["crafts"][1:]
    refused(graph, "concepts its focus craft shares")
    graph = block("s2.b1")
    graph["nodes"][1]["label"] = "Madder"
    refused(graph, "named by each craft's cited sentence")
    graph = block("s2.b1")
    graph["nodes"][0]["crafts"] = graph["nodes"][0]["crafts"][:1]
    refused(graph, "at least 2")


def test_metric_values_keep_three_significant_figures_rounding_half_up() -> None:
    assert metric_value(10.0, 0.3048) == 3.05
    assert metric_value(15.0, 0.3048) == 4.57
    assert metric_value(2.0, 0.0254) == 0.0508
    assert metric_value(125.0, 1.0) == 125.0
    assert metric_value(1.0, 0.0125) == 0.0125
    assert metric_value(1.0, 0.00125) == 0.00125


def test_a_measure_shows_the_metric_value_of_what_its_sentence_states() -> None:
    measure = block("s4.b1")
    measure["rows"][0]["metric"]["high"] = 4.6
    refused(measure, "is 3.05 to 4.57 m")
    measure = block("s4.b1")
    measure["rows"][0]["stated"] = "10-16 feet"
    refused(measure, "is what its sentence or quotes state")
    measure = block("s4.b1")
    measure["rows"][0]["high"] = 16.0
    refused(measure, "carries the numbers it states")
    measure = block("s4.b1")
    measure["rows"][0]["conversion"]["factor"] = 0.305
    refused(measure, "exact definition")


def test_a_regional_conversion_is_a_value_its_cited_quote_states_for_a_named_region() -> None:
    region = {"stateLgd": 24, "stateName": "Gujarat", "districtLgd": 449, "districtName": "Kachchh"}
    citation = sentence("A seer of kut weighed 0.933 kg.", KUT_QUOTE)["citations"][0]
    regional = {"unit": "seer", "metricUnit": "kg", "factor": 0.933, "basis": "REGIONAL", "dataset": None}
    kept = UnitConversion.model_validate(regional | {"region": region, "citation": citation})
    assert kept.region is not None and kept.region.district_name == "Kachchh"
    for changes, message in (
        ({"region": None, "citation": citation}, "named region"),
        ({"region": region, "citation": citation, "factor": 0.93}, "does not state"),
        ({"region": region, "citation": citation, "unit": "foot"}, "named region"),
        ({"region": region, "citation": citation, "dataset": UNIT_DEFINITIONS}, "named region"),
    ):
        with pytest.raises(ValidationError, match=message):
            UnitConversion.model_validate(regional | changes)


def test_a_gi_record_states_only_what_its_sentences_state() -> None:
    market = block("s5.b1")
    market["gi"]["journalIssue"] = "189"
    refused(market, "states 189, which its sentences do not")
    market = block("s5.b1")
    market["gi"]["proprietors"] = ["Khamir"]
    refused(market, "only proprietors its sentences state")
    market = block("s5.b1")
    market["gi"]["status"] = "APPLIED"
    refused(market, "APPLIED GI record carries what makes it so")
    market = block("s5.b1")
    market["gi"] = None
    assert [price.stated for price in BLOCK.validate_python(market).prices] == ["Rs. 7"]
    market["prices"] = []
    refused(market, "cites nothing")


def price(**changes: Any) -> dict[str, Any]:
    text = "In Barmer an ajrakh piece was valued at Rs. 7 in 1975."
    quote = "While in 1975 the value of an Ajrakh piece was Rs. 7"
    return {
        "stated": "Rs. 7",
        "low": 7.0,
        "high": None,
        "currency": "INR",
        "scale": None,
        "per": "piece",
        "pricedOn": "1975",
        "place": "Barmer",
        "districtLgd": None,
        "sentence": sentence(text, quote),
    } | changes


def test_a_price_carries_its_stated_amount_currency_date_and_place() -> None:
    kept = PriceRange.model_validate(price())
    assert (kept.low, kept.currency, kept.priced_on, kept.place) == (7.0, "INR", "1975", "Barmer")
    for changes, message in (
        ({"low": 8.0}, "low then high"),
        ({"currency": "USD"}, "states its currency USD"),
        ({"scale": "LAKH"}, "carries the scale it states"),
        ({"place": "Bhuj"}, "names 'Bhuj' only as its sentence states it"),
        ({"pricedOn": "1976"}, "dated only as precisely"),
        ({"pricedOn": "1975-03"}, "dated only as precisely"),
    ):
        with pytest.raises(ValidationError, match=message):
            PriceRange.model_validate(price(**changes))


def trend(**changes: Any) -> dict[str, Any]:
    climate = block("s6.b1")
    return climate["trends"][0] | changes


def test_a_trend_spans_thirty_years_in_its_variable_s_units_and_says_if_it_is_significant() -> None:
    assert ClimateTrend.model_validate(trend()).significant is True
    assert ClimateTrend.model_validate(trend(pValue=0.2, significant=False)).significant is False
    for changes, message in (
        ({"period": "2000-2025"}, "at least 30 years"),
        ({"slopeUnit": "mm/month per decade"}, "is given in mm/year and mm/year per decade"),
        ({"pValue": 0.2}, "significant exactly when"),
        ({"significant": False}, "significant exactly when"),
    ):
        with pytest.raises(ValidationError, match=message):
            ClimateTrend.model_validate(trend(**changes))


def test_a_climate_block_cites_exactly_the_dataset_rows_it_reads_over_their_period() -> None:
    climate = block("s6.b1")
    climate["datasets"][0]["period"] = "2016-2025"
    refused(climate, "over its dataset row's period")
    climate = block("s6.b1")
    climate["datasets"].append(UNIT_DEFINITIONS.model_dump(mode="json", by_alias=True))
    refused(climate, "only the dataset rows it draws")
    climate = block("s6.b1")
    climate["trends"] = []
    refused(climate, "a trend or a groundwater value")
