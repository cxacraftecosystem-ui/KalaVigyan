from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN
from pptx.slide import Slide as DeckSlide
from pptx.text.text import TextFrame, _Paragraph
from pptx.util import Emu, Inches, Pt

from app.core.clock import INDIA_TZ
from app.research.citation_export import CitationEntry
from app.research.export_text import CREDIT_SEPARATOR, References, picture_credit, reference_link
from app.research.lesson_words import lesson_words
from app.research.lessons import LessonPack, Slide
from app.research.media_refs import MediaRef
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, RIGHT_TO_LEFT_SCRIPTS

from .export_pictures import Picture
from .slide_text import SPACE_AFTER_RATIO, Ladder, SlideText, TextFrameSize

__all__ = ["BLANK_LAYOUT", "BODY", "REFERENCES", "lesson_pptx"]

BLANK_LAYOUT = 6
SLIDE_WIDTH = Inches(13.333)
SLIDE_HEIGHT = Inches(7.5)
MARGIN = Inches(0.6)
TITLE_TOP = Inches(0.4)
TITLE_HEIGHT = Inches(1.1)
BODY_TOP = Inches(1.6)
BODY_HEIGHT = Emu(SLIDE_HEIGHT - BODY_TOP - MARGIN)
PICTURE_WIDTH = Inches(4.4)
CREDIT_HEIGHT = Inches(0.9)
GAP = Inches(0.3)
OPENING_TITLE_TOP = Inches(2.4)
LEDE_TITLE_TOP = Inches(0.8)
OPENING_TITLE_HEIGHT = Inches(2.0)
META_HEIGHT = Inches(0.8)
INK = RGBColor(0x11, 0x18, 0x27)
MUTED = RGBColor(0x4B, 0x55, 0x63)
ACCENT = RGBColor(0x5B, 0x21, 0xB6)
OPENING_TITLE = Ladder((40, 36, 32, 28, 24), bold=True)
TITLE = Ladder((30, 26, 22, 20), bold=True)
BODY = Ladder((20, 18, 16, 14, 13, 12, 11))
QUESTION = Ladder((22, 20, 18, 16, 15, 14, 13))
REFERENCES = Ladder((18, 16, 14, 12, 11, 10, 9))
META_SIZE = 18
CREDIT_SIZE = 10
BULLET = "• "
PART = "{title} ({number}/{total})"

AddSlide = Callable[[], DeckSlide]


@dataclass(frozen=True)
class _Box:
    frame: TextFrame
    size: TextFrameSize


@dataclass(frozen=True)
class _Deck:
    pack: LessonPack
    refs: References
    pictures: Mapping[uuid.UUID, Picture]
    right_to_left: bool
    text: SlideText


def lesson_pptx(pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> bytes:
    script = ANSWER_LANGUAGE_SPECS[pack.language].script
    deck = _Deck(pack, refs, pictures, script in RIGHT_TO_LEFT_SCRIPTS, SlideText(pack.language))
    presentation = Presentation()
    presentation.slide_width = SLIDE_WIDTH
    presentation.slide_height = SLIDE_HEIGHT
    layout = presentation.slide_layouts[BLANK_LAYOUT]
    for slide in pack.slides:
        _draw(lambda: presentation.slides.add_slide(layout), slide, deck)
    out = BytesIO()
    presentation.save(out)
    return out.getvalue()


def _draw(add: AddSlide, slide: Slide, deck: _Deck) -> None:
    if slide.kind == "TITLE":
        _opening(add(), slide, deck)
    elif slide.kind == "SECTION":
        _section(add, slide, deck)
    elif slide.kind == "QUIZ":
        _question(_titled(add(), slide.title, deck), slide, deck)
    elif slide.kind == "READING":
        _references(
            add, slide.title, [deck.refs.of_source(item.source.id) for item in deck.pack.reading_list], deck
        )
    else:
        _references(add, slide.title, [deck.refs.of_source(source.id) for source in deck.pack.sources], deck)


def _opening(page: DeckSlide, slide: Slide, deck: _Deck) -> None:
    pack = deck.pack
    made = pack.created_at.astimezone(INDIA_TZ).date().isoformat()
    meta = CREDIT_SEPARATOR.join(part for part in (pack.craft.name if pack.craft else None, made) if part)
    top = LEDE_TITLE_TOP if slide.bullets else OPENING_TITLE_TOP
    _fitted(_box(page, top, OPENING_TITLE_HEIGHT), [slide.title], deck, OPENING_TITLE, colour=ACCENT)
    meta_top = Emu(top + OPENING_TITLE_HEIGHT + Inches(0.2))
    _write(_box(page, meta_top, META_HEIGHT).frame, [meta], deck, size=META_SIZE, colour=MUTED)
    if not slide.bullets:
        return
    lede_top = Emu(meta_top + META_HEIGHT)
    lines = [f"{BULLET}{s.text} {deck.refs.sentence_marker(s)}" for s in slide.bullets]
    _fitted(_box(page, lede_top, Emu(SLIDE_HEIGHT - lede_top - MARGIN)), lines, deck, BODY)


def _section(add: AddSlide, slide: Slide, deck: _Deck) -> None:
    picture = deck.pictures.get(slide.image.id) if slide.image is not None else None
    width = Emu(SLIDE_WIDTH - 2 * MARGIN - ((PICTURE_WIDTH + GAP) if picture is not None else 0))
    lines = [f"{BULLET}{s.text} {deck.refs.sentence_marker(s)}" for s in slide.bullets]
    parts = deck.text.pages(lines, TextFrameSize(width, BODY_HEIGHT), BODY)
    for number, part in enumerate(parts, 1):
        page = _titled(add(), _part_title(slide.title, number, len(parts)), deck)
        _write(_box(page, BODY_TOP, BODY_HEIGHT, width=width).frame, part.lines, deck, size=part.size)
        if number == 1 and slide.image is not None and picture is not None:
            _picture(page, slide.image, picture, deck)


def _picture(page: DeckSlide, media: MediaRef, picture: Picture, deck: _Deck) -> None:
    left = SLIDE_WIDTH - MARGIN - PICTURE_WIDTH
    room = SLIDE_HEIGHT - BODY_TOP - MARGIN - CREDIT_HEIGHT
    height = min(Emu(int(PICTURE_WIDTH * picture.height / picture.width)), room)
    shown_width = Emu(int(height * picture.width / picture.height))
    page.shapes.add_picture(BytesIO(picture.data), left, BODY_TOP, width=shown_width, height=height)
    credit = _box(page, Emu(BODY_TOP + height + Inches(0.1)), CREDIT_HEIGHT, left=left, width=PICTURE_WIDTH)
    _write(credit.frame, [picture_credit(media)], deck, size=CREDIT_SIZE, colour=MUTED)


def _question(page: DeckSlide, slide: Slide, deck: _Deck) -> None:
    quiz = deck.pack.quiz
    if quiz is None or slide.question is None:
        raise ValueError(f"slide {slide.number} asks a question the lesson does not hold")
    question = quiz.questions[slide.question]
    options = [f"{chr(ord('A') + n)}. {option.text}" for n, option in enumerate(question.options)]
    _fitted(_box(page, BODY_TOP, BODY_HEIGHT), [question.prompt, *options], deck, QUESTION)
    key = question.options[question.answer]
    words = lesson_words(deck.pack.language)
    page.notes_slide.notes_text_frame.text = (
        f"{words.answers}: {chr(ord('A') + question.answer)}. {key.text}\n"
        f"{key.sentence.text} {deck.refs.sentence_marker(key.sentence)}"
    )


def _references(add: AddSlide, title: str, entries: Sequence[CitationEntry], deck: _Deck) -> None:
    lines = [f"[{entry.number}] {entry.apa}" for entry in entries]
    links = [reference_link(entry) for entry in entries]
    parts = deck.text.pages(lines, TextFrameSize(Emu(SLIDE_WIDTH - 2 * MARGIN), BODY_HEIGHT), REFERENCES)
    for number, part in enumerate(parts, 1):
        page = _titled(add(), _part_title(title, number, len(parts)), deck)
        shown = links[part.start : part.start + len(part.lines)]
        _write(_box(page, BODY_TOP, BODY_HEIGHT).frame, part.lines, deck, size=part.size, links=shown)


def _titled(page: DeckSlide, title: str, deck: _Deck) -> DeckSlide:
    _fitted(_box(page, TITLE_TOP, TITLE_HEIGHT), [title], deck, TITLE, colour=ACCENT)
    return page


def _part_title(title: str, number: int, total: int) -> str:
    return title if total == 1 else PART.format(title=title, number=number, total=total)


def _box(page: DeckSlide, top: int, height: int, *, left: int = MARGIN, width: int | None = None) -> _Box:
    shown_width = width or Emu(SLIDE_WIDTH - 2 * MARGIN)
    shape = page.shapes.add_textbox(left, top, shown_width, height)
    frame = shape.text_frame
    frame.word_wrap = True
    return _Box(frame, TextFrameSize(int(shown_width), int(height)))


def _fitted(box: _Box, lines: Sequence[str], deck: _Deck, ladder: Ladder, *, colour: RGBColor = INK) -> None:
    size = deck.text.sized(lines, box.size, ladder)
    _write(box.frame, lines, deck, size=size, colour=colour, bold=ladder.bold)


def _write(
    frame: TextFrame,
    lines: Sequence[str],
    deck: _Deck,
    *,
    size: int,
    colour: RGBColor = INK,
    bold: bool = False,
    links: Sequence[str | None] = (),
) -> None:
    for index, line in enumerate(lines):
        paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
        _direct(paragraph, deck.right_to_left)
        paragraph.space_after = Pt(size * SPACE_AFTER_RATIO)
        run = paragraph.add_run()
        run.text = line
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = colour
        link = links[index] if index < len(links) else None
        if link:
            run.hyperlink.address = link


def _direct(paragraph: _Paragraph, right_to_left: bool) -> None:
    if not right_to_left:
        return
    paragraph.alignment = PP_ALIGN.RIGHT
    paragraph._p.get_or_add_pPr().set("rtl", "1")
