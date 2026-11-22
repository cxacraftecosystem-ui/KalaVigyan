import pytest

from app.research.candidate_gates import CitedSource, publication_figures, quote_gate, source_gate
from app.research.source_titles import first_heading, junk_title, usable_title

STUDY_URL = "https://www.jeb.co.in/journal_issues/200701_jan07/paper_14.pdf"
METALS = (
    "A 2014 study says heavy metals from Sanganer's dyeing and printing wastewater decreased downstream through "
    "accumulation in soil and crops."
)
METALS_QUOTE = "the concentration of heavy metals decreased downstream due to accumulation in soil and crops"
STUDY_TEXT = f"Results show that {METALS_QUOTE} irrigated by the wastewater."
PAPER_TITLE = "Genotoxicity of textile dyes used in Sanganer"


def study(published: str | None, quotes: tuple[str, ...] = (METALS_QUOTE,)) -> CitedSource:
    return CitedSource(url=STUDY_URL, quotes=list(quotes), text=STUDY_TEXT, grade="A", published=published)


def test_a_year_that_is_the_cited_study_s_own_publication_year_passes_the_quotes_gate() -> None:
    outcome = quote_gate(METALS, [study("2014")])
    assert outcome.passed, outcome.reasons
    refused = quote_gate(METALS, [study(None)])
    assert (refused.passed, refused.reasons) == (
        False,
        ["2014 in the statement appears in none of its quotes"],
    )
    other_year = quote_gate(METALS.replace("2014", "2015"), [study("2014")])
    assert (other_year.passed, other_year.reasons) == (
        False,
        ["2015 in the statement appears in none of its quotes"],
    )


def test_a_full_publication_date_passes_as_the_statement_writes_it_and_no_other_number_does() -> None:
    assert publication_figures("2014-02-03") == {"2014", "03.02.2014", "3.02.2014", "03.2.2014", "3.2.2014"}
    assert publication_figures("2014-02") == {"2014"}
    assert publication_figures(None) == set()
    dated = "A study published online on 03.02.2014 found eleven polluted samples among 20 wells."
    outcome = quote_gate(dated, [study("2014-02-03")])
    assert (outcome.passed, outcome.reasons) == (False, ["20 in the statement appears in none of its quotes"])


@pytest.mark.parametrize(
    "title", ["aa.MDI", "paper_14.pdf", "Ajrakh", "Textile dyes", "  ", None, "J. Environ. Biol."]
)
def test_a_file_name_or_a_title_under_three_words_of_letters_is_no_title(title: str | None) -> None:
    assert junk_title(title)


def test_a_work_s_own_title_is_kept_and_a_junk_one_gives_way_in_order() -> None:
    assert not junk_title(PAPER_TITLE)
    assert usable_title("aa.MDI", PAPER_TITLE, "Another heading of the paper") == PAPER_TITLE
    assert usable_title("aa.MDI", "Dyes", "Genotoxicity of Sanganer dyes") == "Genotoxicity of Sanganer dyes"
    assert usable_title("aa.MDI", None, None) is None
    text = "J. Environ. Biol. 28(1)\n\n Genotoxicity of textile dyes used in Sanganer \nAbstract"
    assert first_heading(text) == PAPER_TITLE


def test_a_source_that_names_no_title_of_its_own_is_refused_by_the_source_gate() -> None:
    untitled = CitedSource(url=STUDY_URL, quotes=[], grade="A", untitled="aa.MDI")
    outcome = source_gate(METALS, "GEOLOGY", [untitled])
    assert not outcome.passed
    assert outcome.reasons == [
        f"{STUDY_URL} names no title of its own (its file says 'aa.MDI'); give the work's title as the source's title"
    ]
