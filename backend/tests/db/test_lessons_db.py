import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest

from app.research.lessons import LessonRequest
from app.services.citation_dates import accessed_dates
from app.services.explainer_history import UnknownExplainer
from app.services.lesson_packs import build_lesson, delete_lesson, lesson_list, lesson_of

from ..contracts.learning_golden import LESSON, learning
from .alerts_seed import NOW, Seeded, first_answer, reader, seeded

pytestmark = pytest.mark.db

SEED_RETRIEVED = date(2026, 10, 14)


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


def request_for(explainer_id: uuid.UUID) -> LessonRequest:
    return LessonRequest.model_validate(learning(LESSON)["request"] | {"explainerId": str(explainer_id)})


async def test_a_pack_is_built_from_the_stored_version_and_kept_for_its_builder_alone(db: Seeded) -> None:
    builder, stranger = await reader(db.session), await reader(db.session)
    explainer = await first_answer(db.session, builder)
    pack = await build_lesson(db.session, builder.id, request_for(explainer.answer_id), now=NOW)
    golden = learning(LESSON)["pack"]
    assert [slide.kind for slide in pack.slides] == [slide["kind"] for slide in golden["slides"]]
    assert pack.explainer_id == explainer.answer_id and pack.version == 1
    listed = await lesson_list(db.session, builder.id)
    assert [(item.id, item.slide_count, item.craft.slug) for item in listed.items] == [
        (pack.id, len(golden["slides"]), "Kutch-Ajrakh")
    ]
    assert await lesson_of(db.session, builder.id, pack.id) == pack
    assert await lesson_of(db.session, stranger.id, pack.id) is None
    assert (await lesson_list(db.session, stranger.id)).items == []
    assert await delete_lesson(db.session, stranger.id, pack.id, objects=None) is False
    assert await delete_lesson(db.session, builder.id, pack.id, objects=None) is True
    assert (await lesson_list(db.session, builder.id)).items == []


async def test_no_one_builds_a_lesson_from_another_reader_s_explainer(db: Seeded) -> None:
    owner, stranger = await reader(db.session), await reader(db.session)
    explainer = await first_answer(db.session, owner)
    with pytest.raises(UnknownExplainer):
        await build_lesson(db.session, stranger.id, request_for(explainer.answer_id), now=NOW)


async def test_sources_are_cited_as_read_on_the_day_they_were_retrieved(db: Seeded) -> None:
    owner = await reader(db.session)
    explainer = await first_answer(db.session, owner)
    accessed = await accessed_dates(db.session, explainer.sources)
    assert accessed == {source.id: SEED_RETRIEVED for source in explainer.sources}
