import json
import uuid
from dataclasses import dataclass, field, replace
from decimal import Decimal

from app.core.logging import current_request_id, request_id_scope
from app.providers.answer_routes import depth_follower
from app.providers.budget import AnswerSpend, Ceilings
from app.providers.router import Principal
from app.research.understanding import Understanding
from app.services.answering import AnswerAsk

from ..planner.fakes import FakeModel
from .fakes import UNDERSTOOD_REPLY, FakeStore, enriched, pipeline, streamed
from .test_answer_flow import REPLY, detailed

ANSWER_CAPS = Ceilings(
    monthly_usd=None,
    media_usd=None,
    role_daily_usd={},
    degrade_at=None,
    answer_usd={"BASIC": Decimal("0.25"), "DETAILED": Decimal("1.0"), "EXPERT": Decimal("2.5")},
)


@dataclass
class RequestStore(FakeStore):
    requests: list[str | None] = field(default_factory=list)

    async def begin(self, ask: AnswerAsk, understanding: Understanding) -> uuid.UUID:
        self.requests.append(current_request_id())
        return await super().begin(ask, understanding)


async def test_an_answer_asked_outside_a_request_is_given_its_own_request_id() -> None:
    store = RequestStore()
    await streamed(detailed(), pipeline(replies=[REPLY], store=store))
    (request_id,) = store.requests
    assert (
        request_id is not None and request_id.startswith("answer-") and len(request_id) == len("answer-") + 24
    )


async def test_an_answer_inside_a_request_keeps_that_request_id() -> None:
    store = RequestStore()
    with request_id_scope("http-request-0001"):
        await streamed(detailed(), pipeline(replies=[REPLY], store=store))
    assert store.requests == ["http-request-0001"]


async def test_a_degraded_expert_answer_is_held_to_the_detailed_cap() -> None:
    spend = AnswerSpend(depth="EXPERT")
    model = FakeModel([json.dumps(UNDERSTOOD_REPLY)], degraded=True)
    degraded = replace(
        pipeline(understand_model=model, replies=[REPLY]),
        follow_depth=depth_follower(Principal(answer=spend)),
    )
    await streamed(detailed(depth="EXPERT", role="STUDENT"), degraded)
    assert spend.depth == "DETAILED"
    assert spend.left(ANSWER_CAPS) == Decimal("1.0")


async def test_an_answer_keeps_the_steps_it_streamed() -> None:
    store = FakeStore()
    await streamed(detailed(), pipeline(replies=[REPLY], store=store, enrichment=enriched()))
    (finished,) = store.finished
    steps = finished["steps"]
    shown = [step.detail["step"] for step in steps if step.step == "status"]
    assert shown == ["PLANNING", "SEARCHING_STORED", "RESEARCHING", "READING", "COMPOSING", "WRITING_BACK"]
    assert {step.step for step in steps} == {"status", "trail"}
    assert [step.ms for step in steps] == sorted(step.ms for step in steps)
