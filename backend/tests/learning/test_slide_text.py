import re
from io import BytesIO

from pptx import Presentation

from app.research.citation_formats import citation_entries
from app.research.export_text import References
from app.services.lesson_pptx import lesson_pptx
from app.services.slide_text import Ladder, SizedText, SlideText, TextFrameSize

from .lesson_fixtures import golden_pack

WIDE = 12 * 914400
EMU_PER_POINT = 12700
SHORT = "[1] A."
LONG_REFERENCE = "Indigo vat records of the Kutch dyers and their river water " * 28


def frame_with_room(points: float) -> TextFrameSize:
    return TextFrameSize(width=WIDE, height=round((points + 2 * 3.6) * EMU_PER_POINT))


def test_a_text_takes_the_largest_size_whose_measured_lines_fit() -> None:
    text = SlideText("en")
    ten = [SHORT] * 10
    assert text.fitted(ten, frame_with_room(200), Ladder((18, 9))) == 9
    assert text.fitted(ten, frame_with_room(343), Ladder((18, 9))) == 18
    assert text.fitted(ten, frame_with_room(170), Ladder((18, 9))) is None


def test_lines_that_fit_at_no_size_are_split_into_parts_that_do() -> None:
    parts = SlideText("en").pages([SHORT] * 30, frame_with_room(200), Ladder((18, 9)))
    assert parts == [
        SizedText(tuple([SHORT] * 11), 9, 0),
        SizedText(tuple([SHORT] * 11), 9, 11),
        SizedText(tuple([SHORT] * 8), 9, 22),
    ]


def test_long_references_run_onto_numbered_slides_without_losing_one() -> None:
    pack = golden_pack()
    entries = citation_entries(
        pack.sources, accessed={}, apa=lambda items: [LONG_REFERENCE.strip()] * len(items)
    )
    deck = Presentation(BytesIO(lesson_pptx(pack, References(tuple(entries)), {})))
    texts = [
        [shape.text_frame.text for shape in slide.shapes if shape.has_text_frame] for slide in deck.slides
    ]
    parts = [shown for shown in texts if re.fullmatch(r"Sources \(\d+/\d+\)", shown[0])]
    assert len(parts) >= 2
    assert [part[0] for part in parts] == [f"Sources ({n}/{len(parts)})" for n in range(1, len(parts) + 1)]
    numbers = [line.split(" ", 1)[0] for part in parts for line in part[1].split("\n")]
    assert numbers == [f"[{n}]" for n in range(1, len(pack.sources) + 1)]
