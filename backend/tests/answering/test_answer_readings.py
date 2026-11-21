import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

from app.research.explainer import Explainer
from app.research.explainer_versions import VersionMark
from app.research.open_work_gaps import FieldReading, answer_verdict
from app.research.retrieval import KnowledgeHits
from app.research.sections import AnswerPlans
from app.retrieval.fusion import RRF_K
from app.retrieval.statements import RANKING_DEPTH
from app.services.answer_gaps import SINGLE_RANKING_SCORE, retrieval_low

from ..composer.fixtures import pack
from ..research.fixtures import AJRAKH
from .fakes import ALUM_CLAIM_ID, FakeResearch, FakeStore, pipeline, streamed
from .test_answer_flow import REPLY, detailed


@dataclass
class ReadingStore(FakeStore):
    readings: list[tuple[FieldReading, ...]] = field(default_factory=list)

    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[FieldReading] = (),
    ) -> None:
        self.readings.append(tuple(readings))
        await super().finish(
            answer_id, plans=plans, claim_ids=claim_ids, explainer=explainer, version=version
        )


async def test_a_researched_answer_is_read_field_by_field_and_judged_answered() -> None:
    store = ReadingStore()
    await streamed(detailed(), pipeline(replies=[REPLY], store=store))
    ((reading,),) = store.readings
    assert (reading.field, reading.sentences, reading.retrieval_low) == ("CHEMISTRY", 3, False)
    assert ALUM_CLAIM_ID in reading.claim_ids
    verdict = answer_verdict([reading])
    assert (verdict.verdict, verdict.fields, verdict.lacks, verdict.sentences) == (
        "ANSWERED",
        ("CHEMISTRY",),
        (),
        3,
    )


async def test_research_that_found_nothing_is_read_as_unanswered_with_a_low_retrieval() -> None:
    empty = pack(stored=KnowledgeHits(craft_slug=AJRAKH.slug), evidence=(), documents=())
    research = FakeResearch(pack=empty, steps=(("SEARCHING_STORED", 1), ("RESEARCHING", 2)))
    store = ReadingStore()
    await streamed(detailed(), pipeline(research=research, store=store))
    ((reading,),) = store.readings
    assert (reading.field, reading.sentences, reading.retrieval_low, reading.claim_ids) == (
        "CHEMISTRY",
        0,
        True,
        (),
    )
    verdict = answer_verdict([reading])
    assert (verdict.verdict, verdict.lacking, verdict.lacks) == (
        "UNANSWERED",
        ("CHEMISTRY",),
        ("NO_CITED_EVIDENCE",),
    )


def test_one_ranking_alone_scores_at_most_one_over_sixty_one() -> None:
    assert SINGLE_RANKING_SCORE == 1 / 61
    assert 2 / (RRF_K + RANKING_DEPTH) > SINGLE_RANKING_SCORE


@pytest.mark.parametrize(
    ("scores", "low"),
    [
        ((), True),
        ((1 / 61,), True),
        ((0.01, 1 / 61), True),
        ((1 / 61, 1 / 61 + 1 / 90), False),
        ((0.03,), False),
    ],
)
def test_retrieval_is_low_when_no_stored_fact_beat_one_ranking_alone(
    scores: tuple[float, ...], low: bool
) -> None:
    assert retrieval_low(scores) is low
