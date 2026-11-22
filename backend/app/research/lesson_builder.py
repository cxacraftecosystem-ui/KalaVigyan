from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import datetime

from app.core.errors import AppError

from .blocks import ExplainerSentence, ImagesBlock
from .blocks_learning import QuizBlock
from .blocks_lede import LEDE_BLOCK_ID, LedeBlock
from .blocks_play import hidden_block
from .citations import AnswerSentence, cited_source_ids
from .explainer import ExplainerSection
from .explainer_versions import ExplainerVersionDocument
from .lesson_words import lesson_words
from .lessons import (
    INLINE,
    LESSON_BULLETS_MAX,
    LESSON_SCHEMA_VERSION,
    LESSON_SLIDES_MAX,
    LESSON_TITLE_MAX_CHARS,
    LessonPack,
    LessonRequest,
    Slide,
    reading_list,
)
from .media_refs import MediaRef
from .quiz import quiz_block, still_cited
from .vocabulary import FACT_LEVELS

__all__ = [
    "LESSON_QUIZ_BLOCK_ID",
    "SECTION_NOT_READY_DETAIL",
    "TOO_MANY_SLIDES_DETAIL",
    "LessonNotBuildable",
    "UnknownLessonSection",
    "first_picture",
    "lede_bullets",
    "lesson_pack",
    "lesson_title",
    "section_bullets",
    "section_picture",
]

LESSON_QUIZ_BLOCK_ID = "lesson.quiz"
UNTAUGHT_KINDS = frozenset({"quiz"})
TITLE_ELLIPSIS = "…"
SECTION_NOT_READY_DETAIL = "Choose finished sections of this explainer."
NOTHING_LEFT_DETAIL = "None of these sections has a cited sentence left to teach."
TOO_MANY_SLIDES_DETAIL = f"This lesson would run past {LESSON_SLIDES_MAX} slides. Choose fewer sections."


class UnknownLessonSection(AppError):
    def __init__(self, section_id: str) -> None:
        super().__init__(f"the explainer has no section {section_id}")


class LessonNotBuildable(AppError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


@dataclass(frozen=True)
class Bullet:
    block_id: str
    sentence: ExplainerSentence


@dataclass(frozen=True)
class _Draft:
    kind: str
    title: str
    section_id: str | None = None
    block_ids: tuple[str, ...] = ()
    bullets: tuple[ExplainerSentence, ...] = ()
    image: MediaRef | None = None
    question: int | None = None

    def slide(self, number: int) -> Slide:
        return Slide(
            number=number,
            kind=self.kind,
            title=self.title,
            section_id=self.section_id,
            block_ids=list(self.block_ids),
            bullets=list(self.bullets),
            image=self.image,
            question=self.question,
        )


def lesson_pack(
    version: ExplainerVersionDocument,
    request: LessonRequest,
    *,
    visible_claim_ids: frozenset[str],
    pack_id: uuid.UUID,
    created_at: datetime,
) -> LessonPack:
    explainer = version.explainer
    sections = _chosen_sections(version, request.section_ids)
    taught = [section_bullets(section, visible_claim_ids) for section in sections]
    quiz = _lesson_quiz(taught) if request.quiz else None
    title = request.title or lesson_title(version.mark.question)
    section_slides = [
        draft
        for section, bullets in zip(sections, taught, strict=True)
        for draft in _slides_of(section, bullets, visible_claim_ids)
    ]
    opening = _title_draft(title, lede_bullets(explainer.lede, visible_claim_ids))
    slides = _numbered(opening, section_slides, quiz, explainer.understood.language)
    shown = _shown(slides, quiz)
    known = {source.id: source for source in explainer.sources}
    sources = [known[source_id] for source_id in cited_source_ids(shown)]
    return LessonPack(
        schema_version=LESSON_SCHEMA_VERSION,
        id=pack_id,
        explainer_id=version.mark.explainer_id,
        version=version.mark.version,
        title=title,
        craft=explainer.understood.crafts[0] if explainer.understood.crafts else None,
        language=explainer.understood.language,
        created_at=created_at,
        slides=slides,
        reading_list=reading_list(sources, shown),
        quiz=quiz,
        sources=sources,
    )


def lesson_title(question: str) -> str:
    if len(question) <= LESSON_TITLE_MAX_CHARS:
        return question
    cut = question[: LESSON_TITLE_MAX_CHARS - len(TITLE_ELLIPSIS)]
    words = cut.rsplit(" ", 1)[0] if " " in cut else cut
    return words.rstrip(" ,;:") + TITLE_ELLIPSIS


def section_bullets(section: ExplainerSection, visible_claim_ids: frozenset[str]) -> list[Bullet]:
    return [
        Bullet(block.id, sentence)
        for block in section.blocks
        if block.kind not in UNTAUGHT_KINDS and not hidden_block(block)
        for sentence in block.cited_sentences()
        if isinstance(sentence, ExplainerSentence)
        and sentence.level in FACT_LEVELS
        and still_cited(sentence, visible_claim_ids)
    ]


def lede_bullets(lede: LedeBlock | None, visible_claim_ids: frozenset[str]) -> list[ExplainerSentence]:
    if lede is None:
        return []
    taught = [s for s in lede.sentences if s.level in FACT_LEVELS and still_cited(s, visible_claim_ids)]
    return taught[:LESSON_BULLETS_MAX]


def section_picture(
    section: ExplainerSection, visible_claim_ids: frozenset[str]
) -> tuple[str, MediaRef] | None:
    for block in section.blocks:
        if not isinstance(block, ImagesBlock):
            continue
        for item in block.items:
            if item.media.display == INLINE and {str(c) for c in item.claim_ids} <= visible_claim_ids:
                return block.id, item.media
    return None


def first_picture(section: ExplainerSection) -> MediaRef | None:
    claims = frozenset(
        claim for block in section.blocks for claim in block.cited_claim_ids() | block.illustrated_claim_ids()
    )
    found = section_picture(section, claims)
    return found[1] if found is not None else None


def _chosen_sections(version: ExplainerVersionDocument, section_ids: Sequence[str]) -> list[ExplainerSection]:
    by_id = {section.id: section for section in version.explainer.sections}
    chosen = []
    for section_id in section_ids:
        section = by_id.get(section_id)
        if section is None:
            raise UnknownLessonSection(section_id)
        if section.state != "READY":
            raise LessonNotBuildable(SECTION_NOT_READY_DETAIL)
        chosen.append(section)
    return chosen


def _slides_of(
    section: ExplainerSection, bullets: Sequence[Bullet], visible_claim_ids: frozenset[str]
) -> Iterator[_Draft]:
    picture = section_picture(section, visible_claim_ids)
    for start in range(0, len(bullets), LESSON_BULLETS_MAX):
        shown = bullets[start : start + LESSON_BULLETS_MAX]
        block_ids = [bullet.block_id for bullet in shown]
        image = None
        if start == 0 and picture is not None:
            block_ids.append(picture[0])
            image = picture[1]
        yield _Draft(
            kind="SECTION",
            title=section.title,
            section_id=section.id,
            block_ids=tuple(dict.fromkeys(block_ids)),
            bullets=tuple(bullet.sentence for bullet in shown),
            image=image,
        )


def _numbered(
    opening: _Draft, sections: Sequence[_Draft], quiz: QuizBlock | None, language: str
) -> list[Slide]:
    if not sections:
        raise LessonNotBuildable(NOTHING_LEFT_DETAIL)
    words = lesson_words(language)
    drafts = [
        opening,
        *sections,
        *(_fixed("QUIZ", words.question_title(n + 1), question=n) for n in range(_asked(quiz))),
        _fixed("READING", words.reading),
        _fixed("SOURCES", words.sources),
    ]
    if len(drafts) > LESSON_SLIDES_MAX:
        raise LessonNotBuildable(TOO_MANY_SLIDES_DETAIL)
    return [draft.slide(number) for number, draft in enumerate(drafts, 1)]


def _title_draft(title: str, lede: Sequence[ExplainerSentence]) -> _Draft:
    if not lede:
        return _fixed("TITLE", title)
    return _Draft(kind="TITLE", title=title, block_ids=(LEDE_BLOCK_ID,), bullets=tuple(lede))


def _lesson_quiz(taught: Sequence[Sequence[Bullet]]) -> QuizBlock | None:
    return quiz_block([[b.sentence for b in bullets] for bullets in taught], block_id=LESSON_QUIZ_BLOCK_ID)


def _fixed(kind: str, title: str, *, question: int | None = None) -> _Draft:
    return _Draft(kind=kind, title=title, question=question)


def _asked(quiz: QuizBlock | None) -> int:
    return len(quiz.questions) if quiz is not None else 0


def _shown(slides: Sequence[Slide], quiz: QuizBlock | None) -> list[AnswerSentence]:
    bullets: list[AnswerSentence] = [sentence for slide in slides for sentence in slide.bullets]
    return bullets + (list(quiz.cited_sentences()) if quiz is not None else [])
