import json
from pathlib import Path

from app.research.explainer import Explainer
from app.services.answer_rows import shown_sentences

REPO = Path(__file__).resolve().parents[3]
DOCUMENT = REPO / "shared" / "explainer.document.golden.json"


def golden() -> Explainer:
    return Explainer.model_validate(json.loads(DOCUMENT.read_text(encoding="utf-8")))


def test_every_shown_sentence_becomes_a_row_numbered_within_its_section() -> None:
    rows = shown_sentences(golden())
    assert [(row.section_ordinal, row.ordinal) for row in rows] == [
        *((1, n) for n in range(1, 7)),
        *((2, n) for n in range(1, 4)),
        *((3, n) for n in range(1, 4)),
    ]
    assert {row.heading for row in rows} == {
        "How it is made",
        "Why the water matters",
        "The chemistry of the colours",
    }
    assert sum(len(row.sentence.citations) for row in rows) == 16
    assert not any(row.open_question for row in rows)
    assert rows[6].sentence.text.startswith("Presence of iron in the water supply")
