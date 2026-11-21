from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PageTranslation
from app.research.page_proposals import ACCEPTED, REFUSED, SHOWN
from app.research.page_translation_views import HELD, TRANSLATED
from app.services.monograph_document import document_body, store_document
from app.services.open_work_subjects import subject_by_key
from app.services.page_english import english_page
from app.services.page_preview import preview_page
from app.services.page_preview_links import preview_document
from app.services.page_translation_serving import ServedPage, page_in_language
from app.services.page_translation_views import PassageWindow, translation_view
from app.services.page_translations import translation_reports

from .translation_seed import (
    HINDI_LEDE,
    HINDI_PLANT,
    LEDE,
    NOW,
    PLANT,
    SITE,
    SLUG,
    bundle,
    document,
    hindi,
    opened_session,
    person,
)

pytestmark = pytest.mark.db

PAGE = ("craft", SLUG)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in opened_session():
        yield opened


async def proposed(session: AsyncSession, user: Any, *passages: dict[str, Any]) -> list[Any]:
    subject = await subject_by_key(session, "craft", SLUG)
    part = bundle(*passages).translation
    assert part is not None
    return await translation_reports(session, user, subject, part, origin="CONTRIBUTION", now=NOW)


async def shown(session: AsyncSession, language: str = "hi") -> ServedPage:
    english = await english_page(session, PAGE)
    assert english is not None
    body = document_body(english.document)
    served = ServedPage(etag=english.tag, language="en", body=body)
    return (await page_in_language(session, PAGE, served, tag=english.tag, language=language)).page


async def statuses(session: AsyncSession) -> list[tuple[str, str]]:
    rows = await session.execute(
        select(PageTranslation.unitKey, PageTranslation.status).order_by(PageTranslation.unitKey)
    )
    return [tuple(row) for row in rows.all()]


async def test_a_newcomer_s_translation_waits_for_review_and_a_refused_one_keeps_its_reasons(
    session: AsyncSession,
) -> None:
    newcomer = await person(session, "RESEARCHER")
    renamed = ["रंग ", "नील का पौधा", " से आता है, जो एक ", "झाड़ी है।"]
    reports = await proposed(session, newcomer, hindi(LEDE, HINDI_LEDE), hindi(PLANT, renamed))
    assert [(report.outcome, report.status) for report in reports] == [
        (ACCEPTED, "DRAFT"),
        (REFUSED, "REJECTED"),
    ]
    assert "SHAPE check" in reports[1].message and "Indigofera tinctoria" in reports[1].message
    assert await statuses(session) == [(LEDE, "DRAFT"), (PLANT, "REJECTED")]
    page = await shown(session)
    assert page.language == "en" and "translation" not in page.body


async def test_a_reviewer_who_reads_the_language_publishes_at_once_and_the_rest_stays_marked_english(
    session: AsyncSession,
) -> None:
    reviewer = await person(session, "PROFESSOR", reads=("hi",))
    reports = await proposed(session, reviewer, hindi(LEDE, HINDI_LEDE))
    assert [(report.outcome, report.status) for report in reports] == [(ACCEPTED, "APPROVED")]
    page = await shown(session)
    units = page.body["content"]["units"]
    assert page.language == "hi" and page.body["language"] == "hi"
    cite = {"m": "cite", "key": "c1", "g": ["g1"], "c": ["रंगा जाता है।"]}
    assert units[LEDE]["nodes"] == [{"m": "s", "c": ["कपड़े को नील के घोल में 3 बार ", cite]}]
    assert units[LEDE]["lang"] == "hi" and units[PLANT]["lang"] == "en"
    assert "lang" not in units["masthead-title"] and "lang" not in units["u-year"]
    assert page.body["translation"] == {
        "sourceLanguage": "en",
        "sourceVersion": 1,
        "script": "Deva",
        "direction": "ltr",
        "passages": 2,
        "translated": 1,
        "held": 0,
    }
    english = await shown(session, "en")
    assert english.language == "en" and "lang" not in english.body["content"]["units"][LEDE]


async def test_a_changed_english_sentence_holds_its_translation_until_it_is_translated_again(
    session: AsyncSession,
) -> None:
    reviewer = await person(session, "PROFESSOR", reads=("hi",))
    await proposed(session, reviewer, hindi(LEDE, HINDI_LEDE), hindi(PLANT, HINDI_PLANT))
    assert await store_document(session, document(times="4")) == 2
    page = await shown(session)
    units = page.body["content"]["units"]
    assert units[LEDE]["lang"] == "en" and units[LEDE]["nodes"][0]["c"][0].startswith("The cloth is dyed 4")
    assert units[PLANT]["lang"] == "hi"
    assert (page.body["translation"]["translated"], page.body["translation"]["held"]) == (1, 1)
    stale = await proposed(session, reviewer, hindi(LEDE, HINDI_LEDE))
    assert stale[0].outcome == REFUSED and "CURRENT check" in stale[0].message
    subject = await subject_by_key(session, "craft", SLUG)
    view = await translation_view(session, subject, "hi", window=PassageWindow(), site=SITE)
    assert view is not None
    states = {passage.key: passage.state for passage in view.passages}
    assert states == {LEDE: HELD, PLANT: TRANSLATED}
    held = next(passage for passage in view.passages if passage.key == LEDE)
    assert held.previous == HINDI_LEDE and held.english.startswith("The cloth is dyed 4 times")
    again = await proposed(session, reviewer, hindi(LEDE, ["कपड़े को नील के घोल में 4 बार ", "रंगा जाता है।"], "4"))
    assert again[0].outcome == ACCEPTED
    assert (await shown(session)).body["translation"]["held"] == 0


async def test_a_translation_is_seen_on_its_page_before_it_is_proposed_and_nothing_is_stored(
    session: AsyncSession,
) -> None:
    translator = await person(session, "RESEARCHER")
    wrong = ["रंग ", "Indigofera tinctoria", " से आता है", ""]
    work = bundle(hindi(LEDE, HINDI_LEDE), hindi(PLANT, wrong))
    previewed = await preview_page(session, translator, work, site=SITE, now=NOW)
    assert [part.outcome for part in previewed.parts] == [SHOWN, REFUSED]
    assert "SHAPE check" in previewed.parts[1].message
    token = previewed.preview_url.rsplit("/", 1)[1]
    drawn = await preview_document(session, translator, token, now=NOW)
    assert drawn["language"] == "hi" and drawn["translation"]["translated"] == 1
    assert (
        drawn["content"]["units"][LEDE]["lang"] == "hi" and drawn["content"]["units"][PLANT]["lang"] == "en"
    )
    assert await statuses(session) == []


async def test_a_translation_that_drops_a_number_or_stays_in_english_is_refused(
    session: AsyncSession,
) -> None:
    newcomer = await person(session, "RESEARCHER")
    dropped = ["कपड़े को नील के घोल में कई बार ", "रंगा जाता है।"]
    latin = ["The cloth is dyed 3 times in an indigo ", "vat."]
    reports = await proposed(session, newcomer, hindi(LEDE, dropped))
    reports += await proposed(session, newcomer, hindi(LEDE, latin))
    assert [report.outcome for report in reports] == [REFUSED, REFUSED]
    assert "number 3 is missing" in reports[0].message
    assert "Deva script" in reports[1].message
