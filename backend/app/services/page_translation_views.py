from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.research.monograph_page import TextUnit
from app.research.open_work_translation_keys import TRANSLATION_LANGUAGES
from app.research.page_proposals import PageSubject
from app.research.page_translation_views import (
    HELD,
    TO_TRANSLATE,
    TRANSLATED,
    WAITING,
    LanguageOffer,
    PageLanguage,
    PageLanguages,
    PassageView,
    TranslationView,
)
from app.research.page_translations import SERVED_TRANSLATION_STATUSES
from app.research.review_switch import WAITING_STATUS
from app.research.translation_passages import TaskPassage, is_translatable, task_passage
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, text_direction

from .open_work_subjects import WorkSubject
from .page_english import english_page
from .page_text_index import covered_counts, refresh_page_texts, text_counts
from .page_translation_store import TranslationRow, page_rows
from .translation_offers import home_states, page_offers

__all__ = ["PassageWindow", "language_offer", "page_languages", "translation_view"]


@dataclass(frozen=True)
class PassageWindow:
    offset: int = 0
    limit: int = 40
    state: str | None = None


@dataclass(frozen=True)
class _Held:
    served: dict[str, TranslationRow]
    waiting: frozenset[str]
    earlier: dict[str, TranslationRow]


def language_offer(language: str) -> LanguageOffer:
    spec = ANSWER_LANGUAGE_SPECS[language]
    return LanguageOffer(
        code=language,
        label=spec.label,
        autonym=spec.autonym,
        script=spec.script,
        direction=text_direction(language),
    )


async def translation_view(
    session: AsyncSession, subject: WorkSubject, language: str, *, window: PassageWindow, site: str
) -> TranslationView | None:
    page = (subject.kind, subject.slug)
    english = await english_page(session, page)
    if english is None:
        return None
    await refresh_page_texts(session, page, english.tag, english.document.content)
    held = await _held(session, page, language)
    passages = [
        _view(unit, task_passage(key, unit.nodes, unit.claim_ids), held)
        for key, unit in english.document.content.units.items()
        if is_translatable(key, unit.nodes)
    ]
    chosen = [passage for passage in passages if window.state in (None, passage.state)]
    shown = chosen[window.offset : window.offset + window.limit]
    more = window.offset + window.limit
    offers = page_offers(subject.kind, subject.slug, await home_states(session, [subject.slug]))
    return TranslationView(
        subject=PageSubject(kind=subject.kind, slug=subject.slug),
        title=english.document.title,
        language=language_offer(language),
        english_version=english.document.version,
        passages_total=len(passages),
        translated=_count(passages, TRANSLATED),
        held=_count(passages, HELD),
        waiting=_count(passages, WAITING),
        to_translate=_count(passages, TO_TRANSLATE),
        offered=language in offers,
        passages=shown,
        next_offset=more if more < len(chosen) else None,
        page_url=subject.task_subject(site).page_url,
    )


async def _held(session: AsyncSession, page: tuple[str, str], language: str) -> _Held:
    served = await page_rows(session, page, language, SERVED_TRANSLATION_STATUSES)
    waiting = await page_rows(session, page, language, (WAITING_STATUS,))
    return _Held(
        served={row.source_hash: row for row in served},
        waiting=frozenset(row.source_hash for row in waiting),
        earlier={row.unit_key: row for row in served},
    )


def _view(unit: TextUnit, passage: TaskPassage, held: _Held) -> PassageView:
    base = {**passage.model_dump(), "chapter": unit.chapter, "tag": unit.tag}
    current = held.served.get(passage.source_hash)
    if current is not None:
        return PassageView(**base, state=TRANSLATED, translation=list(current.texts))
    if passage.source_hash in held.waiting:
        return PassageView(**base, state=WAITING)
    earlier = held.earlier.get(passage.key)
    if earlier is not None:
        return PassageView(**base, state=HELD, previous=list(earlier.texts))
    return PassageView(**base, state=TO_TRANSLATE)


def _count(passages: Sequence[PassageView], state: str) -> int:
    return sum(passage.state == state for passage in passages)


async def page_languages(session: AsyncSession, subject: WorkSubject) -> PageLanguages:
    totals = await text_counts(session, [subject.slug])
    served = await covered_counts(session, [subject.slug], SERVED_TRANSLATION_STATUSES)
    total = totals.get((subject.kind, subject.slug), 0)
    offers = page_offers(subject.kind, subject.slug, await home_states(session, [subject.slug]))
    languages = []
    for language in TRANSLATION_LANGUAGES:
        translated = served.get((subject.kind, subject.slug, language), 0)
        if translated == 0 and language not in offers:
            continue
        offer = language_offer(language).model_dump()
        languages.append(
            PageLanguage(**offer, passages=total, translated=translated, offered=language in offers)
        )
    return PageLanguages(subject=PageSubject(kind=subject.kind, slug=subject.slug), languages=languages)
