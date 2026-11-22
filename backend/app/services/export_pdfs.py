from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from datetime import datetime

from app.core.clock import INDIA_TZ
from app.research.blocks import BlockBase, ImagesBlock
from app.research.blocks_play import hidden_block
from app.research.citation_export import CitationEntry
from app.research.citation_formats import cited_datasets
from app.research.explainer_versions import ExplainerVersionDocument
from app.research.export_text import CREDIT_SEPARATOR, References, picture_credit, reference_link
from app.research.lesson_builder import first_picture
from app.research.lesson_words import LessonWords, lesson_words
from app.research.lessons import LessonPack, Slide

from .export_pdf_figures import draw_figure
from .export_pictures import Picture
from .pdf_writer import ACCENT, MUTED, PdfWriter, TextStyle

__all__ = ["explainer_pdf", "lesson_pdf"]

TITLE = TextStyle(size=24, bold=True, colour=ACCENT, gap_after=3)
HEADING = TextStyle(size=16, bold=True, colour=ACCENT, gap_after=3)
META = TextStyle(size=11, colour=MUTED, gap_after=6)
BODY = TextStyle(size=11)
SLIDE_BODY = TextStyle(size=15, gap_after=3)
SMALL = TextStyle(size=8.5, colour=MUTED)
REFERENCE = TextStyle(size=9)
BULLET = "•"
SLIDE_TEXT_SHARE = 0.6
SLIDE_PICTURE_SHARE = 0.36
EXPLAINER_PICTURE_MM = 80.0


def lesson_pdf(pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]) -> bytes:
    writer = PdfWriter(pack.language, orientation="landscape", title=pack.title)
    words = lesson_words(pack.language)
    for slide in pack.slides:
        writer.new_page()
        _lesson_page(writer, slide, pack, refs, pictures)
    if pack.quiz is not None:
        writer.new_page()
        _answers(writer, pack, refs, words)
    return writer.output()


def explainer_pdf(
    document: ExplainerVersionDocument, refs: References, pictures: Mapping[uuid.UUID, Picture]
) -> bytes:
    explainer = document.explainer
    writer = PdfWriter(explainer.understood.language, orientation="portrait", title=explainer.question)
    writer.new_page()
    writer.text(explainer.question, TITLE)
    writer.text(
        _meta(
            explainer.understood.crafts[0].name if explainer.understood.crafts else None,
            document.mark.created_at,
            f"v{document.mark.version}",
        ),
        META,
    )
    if explainer.lede is not None:
        _block(writer, explainer.lede, refs)
    for section in explainer.sections:
        if section.state != "READY":
            continue
        writer.text(section.title, HEADING)
        media = first_picture(section)
        picture = pictures.get(media.id) if media is not None else None
        if media is not None and picture is not None:
            bottom = writer.picture(
                picture,
                picture_credit(media),
                x=writer.left,
                width=writer.width,
                max_height=EXPLAINER_PICTURE_MM,
            )
            writer.go_to(bottom + 3)
        for block in section.blocks:
            _block(writer, block, refs)
    writer.text(lesson_words(explainer.understood.language).sources, HEADING)
    _reference_list(writer, refs.entries)
    return writer.output()


def _lesson_page(
    writer: PdfWriter, slide: Slide, pack: LessonPack, refs: References, pictures: Mapping[uuid.UUID, Picture]
) -> None:
    if slide.kind == "TITLE":
        writer.go_to(writer.bottom / 3)
        writer.text(slide.title, TITLE)
        writer.text(_meta(pack.craft.name if pack.craft else None, pack.created_at, None), META)
        _bullet_items(writer, slide, refs, writer.width)
        return
    writer.text(slide.title, HEADING)
    if slide.kind == "SECTION":
        _section_page(writer, slide, refs, pictures)
    elif slide.kind == "QUIZ":
        _question_page(writer, slide, pack)
    elif slide.kind == "READING":
        _reference_list(writer, (refs.of_source(item.source.id) for item in pack.reading_list))
    else:
        _reference_list(writer, (refs.of_source(source.id) for source in pack.sources))


def _section_page(
    writer: PdfWriter, slide: Slide, refs: References, pictures: Mapping[uuid.UUID, Picture]
) -> None:
    top = writer.y
    picture = pictures.get(slide.image.id) if slide.image is not None else None
    text_width = writer.width * (SLIDE_TEXT_SHARE if picture is not None else 1.0)
    if slide.image is not None and picture is not None:
        writer.picture(
            picture,
            picture_credit(slide.image),
            x=writer.left + writer.width * (1 - SLIDE_PICTURE_SHARE),
            width=writer.width * SLIDE_PICTURE_SHARE,
            max_height=writer.bottom - top,
        )
        writer.go_to(top)
    _bullet_items(writer, slide, refs, text_width)


def _bullet_items(writer: PdfWriter, slide: Slide, refs: References, width: float) -> None:
    for sentence in slide.bullets:
        writer.item(BULLET, f"{sentence.text} {refs.sentence_marker(sentence)}", SLIDE_BODY, width=width)


def _question_page(writer: PdfWriter, slide: Slide, pack: LessonPack) -> None:
    if pack.quiz is None or slide.question is None:
        raise ValueError(f"slide {slide.number} asks a question the lesson does not hold")
    question = pack.quiz.questions[slide.question]
    writer.text(question.prompt, SLIDE_BODY)
    for number, option in enumerate(question.options):
        writer.item(f"{chr(ord('A') + number)}.", option.text, SLIDE_BODY)


def _answers(writer: PdfWriter, pack: LessonPack, refs: References, words: LessonWords) -> None:
    writer.text(words.answers, HEADING)
    for number, question in enumerate(pack.quiz.questions if pack.quiz else [], 1):
        key = question.options[question.answer]
        letter = chr(ord("A") + question.answer)
        writer.item(f"{number}.", f"{letter}. {key.text}", BODY)
        writer.text(f"{key.sentence.text} {refs.sentence_marker(key.sentence)}", SMALL)


def _block(writer: PdfWriter, block: BlockBase, refs: References) -> None:
    if isinstance(block, ImagesBlock) or hidden_block(block):
        return
    draw_figure(writer, block)
    for sentence in block.cited_sentences():
        writer.text(f"{sentence.text} {refs.sentence_marker(sentence)}", BODY)
    for dataset in cited_datasets([block]):
        parts = (dataset.title, dataset.edition, dataset.period, dataset.native_resolution, dataset.licence)
        writer.text(f"{CREDIT_SEPARATOR.join(parts)} {refs.dataset_marker([dataset.code])}", SMALL)


def _reference_list(writer: PdfWriter, entries: Iterable[CitationEntry]) -> None:
    for entry in entries:
        writer.item(f"[{entry.number}]", entry.apa, REFERENCE, link=reference_link(entry))


def _meta(craft: str | None, made_at: datetime, version: str | None) -> str:
    made = made_at.astimezone(INDIA_TZ).date().isoformat()
    return CREDIT_SEPARATOR.join(part for part in (craft, version, made) if part)
