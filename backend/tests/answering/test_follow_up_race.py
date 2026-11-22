import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.research.explainer import Explainer
from app.research.explainer_versions import ExplainerVersionDocument, VersionMark
from app.research.sections import AnswerPlans
from app.services.explainer_history import STALE_VERSION_DETAIL, StaleVersion
from app.services.explainer_payload import version_document

from ..composer.fixtures import section_reply
from .fakes import WRITTEN_IDS, WRITTEN_LAKE_ID, FakeStore, pipeline, streamed
from .test_follow_up_flow import ALUM, BATH, KUTCH_BATH_TEXT, SECOND_ID, events, first_version, follow_up_of

THIRD_ID = uuid.UUID("7f8e9d0c-1b2a-4c3d-9e4f-5a6b7c8d9e0f")
WRITTEN = {**WRITTEN_IDS, KUTCH_BATH_TEXT: WRITTEN_LAKE_ID}


@dataclass
class RacingStore(FakeStore):
    taken: int = 1
    newer: ExplainerVersionDocument | None = None
    raced: list[int] = field(default_factory=list)
    looked_up: list[uuid.UUID] = field(default_factory=list)

    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[Any] = (),
        steps: Sequence[Any] = (),
    ) -> None:
        if version is not None and version.version <= self.taken:
            self.raced.append(version.version)
            raise StaleVersion(version.explainer_id, version.version - 1, self.taken)
        await super().finish(
            answer_id,
            asked_at=asked_at,
            plans=plans,
            claim_ids=claim_ids,
            explainer=explainer,
            version=version,
            readings=readings,
        )

    async def latest(self, explainer_id: uuid.UUID, user_id: uuid.UUID | None) -> ExplainerVersionDocument:
        self.looked_up.append(explainer_id)
        if self.newer is None:
            raise AssertionError("no newer version was saved in this test")
        return self.newer


async def second_version(first: Explainer) -> ExplainerVersionDocument:
    store = FakeStore(answer_id=SECOND_ID, written=dict(WRITTEN))
    await streamed(
        follow_up_of(first, "CHEMISTRY"), pipeline(replies=[section_reply(ALUM, BATH)], store=store)
    )
    (finished,) = store.finished
    return version_document(finished["version"], finished["explainer"])


async def raced(store: RacingStore, first: Explainer) -> list[tuple[str, Any]]:
    text = await streamed(
        follow_up_of(first, "CHEMISTRY"), pipeline(replies=[section_reply(ALUM, BATH)], store=store)
    )
    return events(text)


async def test_a_follow_up_that_lost_the_race_is_kept_after_the_version_saved_meanwhile() -> None:
    first = await first_version()
    newer = await second_version(first)
    store = RacingStore(answer_id=THIRD_ID, written=dict(WRITTEN), taken=2, newer=newer)
    found = await raced(store, first)
    assert (store.raced, store.looked_up) == ([2], [first.answer_id])
    assert [payload["block"]["id"] for name, payload in found if name == "block"] == ["s1.b2"]
    (finished,) = store.finished
    mark = finished["version"]
    assert (mark.version, mark.based_on, mark.answer_id) == (3, 2, THIRD_ID)
    assert [block.id for block in finished["explainer"].sections[0].blocks] == ["s1.b1", "s1.b2", "s1.b3"]
    name, shown = found[-2]
    assert (name, shown["version"], shown["basedOn"]) == ("version", 3, 2)
    assert shown["changes"] == [{"sectionId": "s1", "change": "DEEPENED", "blockIds": ["s1.b3"]}]
    assert found[-1] == ("done", {"answerId": str(THIRD_ID)})


async def test_a_follow_up_refused_without_a_newer_version_still_says_it_was_not_kept() -> None:
    first = await first_version()
    builds_on = follow_up_of(first, "CHEMISTRY").builds_on
    assert builds_on is not None
    store = RacingStore(answer_id=THIRD_ID, written=dict(WRITTEN), taken=2, newer=builds_on.base)
    found = await raced(store, first)
    assert (store.raced, store.finished) == ([2], [])
    assert ("error", {"message": STALE_VERSION_DETAIL}) in found
    assert found[-1] == ("done", {"answerId": None})
