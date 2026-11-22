import uuid
from collections.abc import AsyncIterator

import pytest

from app.core.shielded import ShieldedWork
from app.models import Answer
from app.research.explainer import Explainer
from app.services.answer_store import SqlAnswerStore
from app.services.answering import AnswerAsk
from app.services.craft_resolver import CraftIndexStore
from app.services.explainer_history import explainer_history, latest_version
from app.services.follow_ups import AnswerLayout, FollowUp
from app.services.version_race import VersionRace

from ..alerts.test_version_merge import water_and_history
from ..alerts.versions import follow_up_document
from ..craft_fixtures import FixedEmbedder
from .alerts_seed import Seeded, first_answer, reader, seeded
from .test_explainer_versions_db import base_of, second_of, stored_follow_up

pytestmark = pytest.mark.db


@pytest.fixture
async def db() -> AsyncIterator[Seeded]:
    async with seeded() as found:
        yield found


async def answer_row(db: Seeded, user_id: uuid.UUID, follow_up: Explainer) -> None:
    db.session.add(Answer(id=follow_up.answer_id, userId=user_id, question=follow_up.question, mode="DEEP"))
    await db.session.commit()


async def test_a_follow_up_that_lost_the_race_is_stored_after_the_version_saved_meanwhile(db: Seeded) -> None:
    user = await reader(db.session)
    first = await first_answer(db.session, user)
    await stored_follow_up(db, user.id, second_of(first))
    loser = follow_up_document(water_and_history(), answer_id=str(uuid.uuid4()))
    await answer_row(db, user.id, loser)
    store = SqlAnswerStore(db.sessions, embed=FixedEmbedder(), shield=ShieldedWork(), index=CraftIndexStore())
    asker = AnswerAsk(question=loser.question, depth="EXPERT", user_id=user.id)
    layout = AnswerLayout(specs=(), follow_up=FollowUp(base=base_of(first)))
    kept = await VersionRace(store, loser.answer_id, asker, ()).kept(layout, loser, [])
    assert kept.version is not None and (kept.version.version, kept.version.based_on) == (3, 2)
    history = await explainer_history(db.session, first.answer_id, user.id)
    assert [(m.version, m.based_on, m.answer_id) for m in history.versions][-1] == (3, 2, loser.answer_id)
    latest = await latest_version(db.session, first.answer_id, user.id)
    blocks = {section.id: [block.id for block in section.blocks] for section in latest.explainer.sections}
    assert (blocks["s2"], blocks["s4"]) == (["s2.b1", "s2.b2", "s2.b3"], ["s4.b1", "s4.b2"])
