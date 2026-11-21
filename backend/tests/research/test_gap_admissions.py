import pytest

from app.research import coverage_eval
from app.research.gap_admissions import GAP_ADMISSION, admits_gap, gap_admissions

PATINA = (
    "The black patina is credited with protecting the ware from corrosion, but the compounds that form it "
    "have not been identified, so the sources do not say what the black is made of."
)


@pytest.mark.parametrize(
    "text",
    [
        PATINA,
        "The compounds that form the black of bidri have not been identified.",
        "The craft's origins are unknown.",
        "How the alloy reached Bidar remains unclear.",
        "The exact recipe of the fort earth has never been documented.",
        "We don’t know who first inlaid silver in Bidar.",
    ],
)
def test_the_judge_s_gap_admissions_are_found(text: str) -> None:
    assert admits_gap(text)


@pytest.mark.parametrize(
    "text",
    [
        "The cloth is not washed until the resist has dried.",
        "No dye is applied where the resist paste lies.",
        "An unknown number of families moved to Ajrakhpur after 2001.",
        "Bidri ware is cast from an alloy of zinc and copper.",
        "Silver wire is hammered into the engraved grooves.",
    ],
)
def test_an_ordinary_negative_or_fact_is_not_a_gap(text: str) -> None:
    assert not admits_gap(text)


def test_the_answer_and_the_evaluation_read_one_pattern() -> None:
    texts = [PATINA, "Bidri ware is cast from an alloy of zinc and copper."]
    assert gap_admissions(texts) == [PATINA]
    assert coverage_eval.gap_admissions is gap_admissions
    assert not hasattr(coverage_eval, "GAP_ADMISSION")
    assert GAP_ADMISSION.search("THE ORIGINS ARE UNKNOWN") is not None
