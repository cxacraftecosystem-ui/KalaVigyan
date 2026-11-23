import pytest

from source_authors import split_authors


@pytest.mark.parametrize(
    ("author", "authors"),
    [
        ("Victoria and Albert Museum", ["Victoria and Albert Museum"]),
        (
            "All India Artisans and Craftworkers Welfare Association (AIACA)",
            ["All India Artisans and Craftworkers Welfare Association (AIACA)"],
        ),
        (
            "Office of the Controller General of Patents, Designs & Trade Marks (applicant: Ajarakhpur Hastkala"
            " Vikas Sangathan; facilitated by Textiles Committee, Ministry of Textiles)",
            [
                "Office of the Controller General of Patents, Designs & Trade Marks (applicant: Ajarakhpur Hastkala"
                " Vikas Sangathan; facilitated by Textiles Committee, Ministry of Textiles)"
            ],
        ),
        (
            "Reddy, Renuka (guest post; posted by Avalon Fotheringham)",
            ["Reddy, Renuka (guest post; posted by Avalon Fotheringham)"],
        ),
        ("Registry; Textiles Committee", ["Registry", "Textiles Committee"]),
        ("Gauri Kathju and Radha Kashyap", ["Gauri Kathju", "Radha Kashyap"]),
        (
            "Ruby Jain and Meetu Rani Hada (Dept. of Home Science, University of Rajasthan)",
            ["Ruby Jain", "Meetu Rani Hada (Dept. of Home Science, University of Rajasthan)"],
        ),
        ("  Judy   Frater ", ["Judy Frater"]),
        (None, []),
        ("", []),
    ],
)
def test_organisations_stay_whole_and_people_are_split_outside_brackets(author: str | None, authors: list[str]) -> None:
    assert split_authors(author) == authors
