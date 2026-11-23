import pytest

from app.research.front_page import FrontPage, front_page, producer_token

from ..sources.jeb_page import FIRST_PAGE, PAPER_TITLE


def test_the_recorded_first_page_names_its_journal_issue_authors_and_title() -> None:
    assert front_page(FIRST_PAGE) == FrontPage(
        journal="Journal of Environmental Biology",
        published="2007-01",
        authors=("Nupur Mathur", "Pradeep Bhatnagar"),
        title=PAPER_TITLE,
    )


def test_a_title_over_two_lines_and_a_single_author() -> None:
    text = (
        "Journal of Environmental Biology January, 2007\n"
        "Sequential anaerobic and aerobic treatment of pulp and paper mill\n"
        "effluent in pilot scale bioreactor\n"
        "Pratibha Singh*\n"
        "Environmental Biotechnology Laboratory, Department of Environmental Sciences\n"
    )
    assert front_page(text) == FrontPage(
        journal="Journal of Environmental Biology",
        published="2007-01",
        authors=("Pratibha Singh",),
        title="Sequential anaerobic and aerobic treatment of pulp and paper mill effluent in pilot scale bioreactor",
    )


def test_initials_footnote_numbers_a_volume_and_a_short_month() -> None:
    text = "Annals of Botany, Vol. 12, Sept. 2014\nA study of lac\nA. K. Tripathi1, D. Madhavi* 2 and Mukesh Gautam\n"
    assert front_page(text) == FrontPage(
        journal="Annals of Botany",
        published="2014-09",
        authors=("A. K. Tripathi", "D. Madhavi", "Mukesh Gautam"),
        title="A study of lac",
    )


def test_a_page_without_a_journal_line_still_names_its_authors_after_its_title() -> None:
    assert front_page("Report on dyes\nAnita Rao and Vikram Shah\n") == FrontPage(
        authors=("Anita Rao", "Vikram Shah"), title="Report on dyes"
    )


def test_a_title_cased_line_of_ordinary_words_is_not_an_author() -> None:
    text = "Journal of Craft Studies March 2019\nDyes Of The Desert\nAnd Their Makers\nRam Lal\n"
    assert front_page(text) == FrontPage(
        journal="Journal of Craft Studies",
        published="2019-03",
        authors=("Ram Lal",),
        title="Dyes Of The Desert And Their Makers",
    )


def test_without_an_authors_line_the_line_after_the_journal_is_the_title_never_the_journal() -> None:
    text = "Journal of Craft Studies March 2019\nMordants of the western coast\nAbstract: Alum and iron are\n"
    assert front_page(text) == FrontPage(
        journal="Journal of Craft Studies", published="2019-03", title="Mordants of the western coast"
    )


def test_a_dated_line_names_no_journal_without_a_periodical_word_and_a_month_before_the_year() -> None:
    assert front_page("Received: June 1, 2005\nAccepted on dyes\n") == FrontPage()
    assert front_page("Review of dyes, June 1, 2005\n") == FrontPage()
    assert front_page("Notes on dyes, Volume 2007\n") == FrontPage()


@pytest.mark.parametrize(
    "author",
    [
        "sys",
        "user",
        "Admin",
        "Microsoft Office User",
        "PScript5.dll Version 5.2",
        "GPL Ghostscript 8.15",
        "jsmith",
        "  ",
        "123",
    ],
)
def test_a_producer_s_word_is_no_author(author: str) -> None:
    assert producer_token(author)


@pytest.mark.parametrize("author", ["Nupur Mathur", "A. K. Tripathi", "UNESCO", "Wordsworth"])
def test_a_person_or_body_is_an_author(author: str) -> None:
    assert not producer_token(author)
