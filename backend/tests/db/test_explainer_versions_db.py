import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.core.shielded import ShieldedWork
from app.models import Answer, SavedItem
from app.research.explainer import Explainer
from app.research.explainer_versions import BuildsOn, ExplainerVersionDocument
from app.research.sections import AnswerPlans
from app.services.answer_store import SqlAnswerStore
from app.services.craft_resolver import CraftIndexStore
from app.services.explainer_history import (
    StaleVersion,
    UnknownExplainer,
    explainer_history,
    explainer_version,
    follow_up_of,
    latest_version,
    mark_seen,
)
from app.services.explainer_payload import first_version_mark, version_document
from app.services.saved_explainers import save_explainer, saved_explainers, unsave_explainer
from app.services.version_merge import merged_version

from ..alerts.versions import follow_up_document, latest_golden
from ..craft_fixtures import FixedEmbedder
from .alerts_seed import Seeded, first_answer, reader, seeded

pytestmark = pytest.mark.db

NO_PLANS = AnswerPlans(sections=[])


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


def base_of(explainer: Explainer) -> ExplainerVersionDocument:
    mark = first_version_mark(
        answer_id=explainer.answer_id, question=explainer.question, created_at=explainer.created_at
    )
    return version_document(mark, explainer)


def second_of(explainer: Explainer) -> ExplainerVersionDocument:
    latest = latest_golden()["explainer"]
    water, history = latest["sections"][1], latest["sections"][3]
    sections = [{**water, "blocks": [water["blocks"][1]]}, history]
    return merged_version(base_of(explainer), follow_up_document(sections, answer_id=str(uuid.uuid4())))


async def stored_follow_up(db: Seeded, user_id: uuid.UUID, version: ExplainerVersionDocument) -> None:
    db.session.add(
        Answer(id=version.mark.answer_id, userId=user_id, question=version.mark.question, mode="DEEP")
    )
    await db.session.commit()
    store = SqlAnswerStore(db.sessions, embed=FixedEmbedder(), shield=ShieldedWork(), index=CraftIndexStore())
    await store.finish(
        version.mark.answer_id,
        asked_at=datetime.now(UTC),
        plans=NO_PLANS,
        claim_ids=[],
        explainer=version.explainer,
        version=version.mark,
    )


async def test_a_follow_up_is_stored_as_the_next_version_and_the_first_stays_whole(db: Seeded) -> None:
    user = await reader(db.session)
    first = await first_answer(db.session, user)
    second = second_of(first)
    await stored_follow_up(db, user.id, second)
    history = await explainer_history(db.session, first.answer_id, user.id)
    assert [(m.version, m.based_on, m.answer_id) for m in history.versions] == [
        (1, None, first.answer_id),
        (2, 1, second.mark.answer_id),
    ]
    assert history.versions[1] == second.mark
    older = await explainer_version(db.session, first.answer_id, user.id, 1)
    assert older.explainer == first
    assert (await latest_version(db.session, first.answer_id, user.id)) == second
    row = (
        await db.session.execute(
            select(Answer.explainerId, Answer.explainerVersion).where(Answer.id == second.mark.answer_id)
        )
    ).one()
    assert tuple(row) == (first.answer_id, 2)


async def test_a_second_follow_up_on_the_same_version_is_refused(db: Seeded) -> None:
    user = await reader(db.session)
    first = await first_answer(db.session, user)
    await stored_follow_up(db, user.id, second_of(first))
    with pytest.raises(StaleVersion):
        await stored_follow_up(db, user.id, second_of(first))
    with pytest.raises(StaleVersion):
        await follow_up_of(db.session, user.id, BuildsOn(explainer_id=first.answer_id, version=1, facets=[]))
    found = await follow_up_of(
        db.session, user.id, BuildsOn(explainer_id=first.answer_id, version=2, facets=[])
    )
    assert found.base.mark.version == 2


async def test_an_explainer_answers_only_its_asker(db: Seeded) -> None:
    user, stranger = await reader(db.session), await reader(db.session)
    first = await first_answer(db.session, user)
    for read in (
        explainer_history(db.session, first.answer_id, stranger.id),
        latest_version(db.session, first.answer_id, stranger.id),
        explainer_version(db.session, first.answer_id, stranger.id, 1),
        save_explainer(db.session, stranger.id, first.answer_id),
    ):
        with pytest.raises(UnknownExplainer):
            await read
    with pytest.raises(UnknownExplainer):
        await explainer_version(db.session, first.answer_id, user.id, 2)


async def test_a_saved_explainer_follows_its_latest_version(db: Seeded) -> None:
    user = await reader(db.session)
    first = await first_answer(db.session, user)
    saved = await save_explainer(db.session, user.id, first.answer_id)
    await db.session.commit()
    assert (saved.latest_version, saved.seen_version, saved.facets) == (
        1,
        1,
        ["PROCESS", "GEOGRAPHY", "CHEMISTRY"],
    )
    await stored_follow_up(db, user.id, second_of(first))
    await mark_seen(db.session, user.id, first.answer_id, 2)
    await mark_seen(db.session, user.id, first.answer_id, 1)
    await db.session.commit()
    (item,) = (await saved_explainers(db.session, user.id)).items
    expected = latest_golden()
    assert item.question == first.question and item.craft == first.understood.crafts[0]
    assert item.facets == [section["discipline"] for section in expected["explainer"]["sections"]]
    assert (item.latest_version, item.seen_version, item.depth, item.language) == (2, 2, "EXPERT", "en")
    again = await save_explainer(db.session, user.id, first.answer_id)
    assert again.saved_at == saved.saved_at


async def test_an_unsaved_explainer_leaves_the_list(db: Seeded) -> None:
    user = await reader(db.session)
    first = await first_answer(db.session, user)
    await save_explainer(db.session, user.id, first.answer_id)
    assert await unsave_explainer(db.session, user.id, first.answer_id)
    assert not await unsave_explainer(db.session, user.id, first.answer_id)
    left = await db.session.scalar(select(SavedItem.id).where(SavedItem.userId == user.id))
    assert left is None
