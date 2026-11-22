import pytest

from app.sources.reference.wikidata_statements import statement_lines, statements_from_bindings
from app.sources.reference.wikidata_times import time_text


def inception(value: str, precision: str) -> dict:
    return {
        "property": {"value": "http://www.wikidata.org/entity/P571"},
        "propertyLabel": {"value": "inception"},
        "type": {"value": "http://wikiba.se/ontology#Time"},
        "value": {"value": value},
        "precision": {"value": precision},
    }


def test_time_values_keep_the_precision_wikidata_states() -> None:
    rows = [
        inception("1640-01-01T00:00:00Z", "9"),
        inception("1856-03-01T00:00:00Z", "10"),
        inception("1856-03-07T00:00:00Z", "11"),
        inception("1600-01-01T00:00:00Z", "7"),
        inception("1600-01-01T00:00:00Z", "5"),
    ]
    assert statement_lines(statements_from_bindings(rows)) == [
        "inception: 1640; 16th century; 1856-03; 1856-03-07"
    ]


@pytest.mark.parametrize(
    ("value", "precision", "words"),
    [
        ("+1850-00-00T00:00:00Z", "7", "19th century"),
        ("1850-01-01T00:00:00Z", "8", "1850s"),
        ("1855-01-01T00:00:00Z", "8", "1850s"),
        ("1850-01-01T00:00:00Z", "7", "19th century"),
        ("1900-01-01T00:00:00Z", "7", "19th century"),
        ("1901-01-01T00:00:00Z", "7", "20th century"),
        ("1001-01-01T00:00:00Z", "7", "11th century"),
        ("2001-01-01T00:00:00Z", "7", "21st century"),
        ("2101-01-01T00:00:00Z", "7", "22nd century"),
        ("1850-01-01T00:00:00Z", "6", "2nd millennium"),
        ("2000-01-01T00:00:00Z", "6", "2nd millennium"),
        ("2001-01-01T00:00:00Z", "6", "3rd millennium"),
    ],
)
def test_a_decade_century_or_millennium_is_named_as_wikibase_names_it(
    value: str, precision: str, words: str
) -> None:
    assert time_text(value, precision) == words


@pytest.mark.parametrize(
    ("value", "precision", "words"),
    [
        ("-0449-01-01T00:00:00Z", "8", "450s BCE"),
        ("-0449-01-01T00:00:00Z", "7", "5th century BCE"),
        ("-0500-01-01T00:00:00Z", "7", "6th century BCE"),
        ("0000-01-01T00:00:00Z", "7", "1st century BCE"),
        ("-0999-01-01T00:00:00Z", "6", "1st millennium BCE"),
    ],
)
def test_a_sparql_year_before_one_counts_back_from_1_bce(value: str, precision: str, words: str) -> None:
    assert time_text(value, precision) == words


def test_a_decade_of_no_years_and_coarser_precisions_are_left_out() -> None:
    assert time_text("0005-01-01T00:00:00Z", "8") is None
    assert time_text("1850-01-01T00:00:00Z", "5") is None
    assert time_text("-13798000000-01-01T00:00:00Z", "0") is None
    assert time_text("1850-01-01T00:00:00Z", None) is None
