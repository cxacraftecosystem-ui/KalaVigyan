import uuid

import pytest

from app.research.sentence_names import sentence_name, upper_first
from app.services.term_sentence_names import named_in_sentences

ALUM_ID = uuid.UUID(int=1)
KUTCH_ID = uuid.UUID(int=2)
MADDER_ID = uuid.UUID(int=3)


@pytest.mark.parametrize(
    ("label", "texts", "name"),
    [
        ("Alum", ["Alum binds the red.", "The cloth is printed with alum paste."], "alum"),
        ("Kutch", ["Kutch is dry.", "Printers in Kutch dye with indigo."], "Kutch"),
        ("Turkey Red Oil", ["Cloth is soaked in Turkey red oil before mordanting."], "Turkey red oil"),
        (
            "Alum",
            ["Alum binds the red.", "It is cheap. Alum is sold in Bhuj.", '"Alum fixes it," he said.'],
            None,
        ),
        ("Alum", ["The aluminium salt is not used."], None),
        ("Indigo", ["It is dyed in indigo, then indigo again, and Indigo once."], "indigo"),
        ("", ["anything"], None),
    ],
)
def test_a_name_is_written_as_sentences_write_it_away_from_their_start(
    label: str, texts: list[str], name: str | None
) -> None:
    assert sentence_name(label, texts) == name


def test_a_name_at_the_start_of_a_line_is_written_with_a_capital() -> None:
    assert (upper_first("alum"), upper_first("Kutch"), upper_first("")) == ("Alum", "Kutch", "")


def test_each_term_s_name_is_read_from_its_meaning_and_its_concepts_claims() -> None:
    rows = [
        (ALUM_ID, "Alum", "A salt; potash alum is used as a mordant.", "Alum binds the red."),
        (ALUM_ID, "Alum", "A salt; potash alum is used as a mordant.", "Printers boil alum in water."),
        (KUTCH_ID, "Kutch", None, "Kutch is dry."),
        (MADDER_ID, "Madder", None, "Cloth is boiled with madder roots."),
    ]
    assert named_in_sentences(rows) == {ALUM_ID: "alum", MADDER_ID: "madder"}
