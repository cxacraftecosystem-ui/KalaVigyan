import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime

import pytest

from app.research.explainer import Explainer
from app.research.explainer_versions import VersionMark
from app.research.open_work_gaps import FieldReading, answer_verdict
from app.research.retrieval import ClaimHit, KnowledgeHits
from app.research.sections import AnswerPlans
from app.retrieval.fusion import RRF_K
from app.retrieval.statements import RANKING_DEPTH
from app.services.answer_gaps import ANSWERING_RELEVANCE, SINGLE_RANKING_SCORE, fused_low, retrieval_low

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
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[FieldReading] = (),
        steps: Sequence[object] = (),
    ) -> None:
        self.readings.append(tuple(readings))
        await super().finish(
            answer_id,
            asked_at=asked_at,
            plans=plans,
            claim_ids=claim_ids,
            explainer=explainer,
            version=version,
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


def stored(score: float, relevance: float | None = None) -> ClaimHit:
    return ClaimHit(
        claim_id=uuid.uuid4(),
        text="Alum fixes the red.",
        level="PROVISIONAL",
        subject_type="CONCEPT",
        subject_id=uuid.uuid4(),
        score=score,
        relevance_score=relevance,
    )


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
def test_without_relevance_retrieval_is_low_when_no_stored_fact_beat_one_ranking_alone(
    scores: tuple[float, ...], low: bool
) -> None:
    assert fused_low(scores) is low
    assert retrieval_low([stored(score) for score in scores]) is low


@pytest.mark.parametrize(
    ("relevance", "low"),
    [
        ((0.49,), True),
        ((0.12, 0.3), True),
        ((0.5,), False),
        ((0.2, 0.94), False),
    ],
)
def test_with_relevance_retrieval_is_low_when_no_stored_fact_answers_the_question(
    relevance: tuple[float, ...], low: bool
) -> None:
    assert ANSWERING_RELEVANCE == 0.5
    assert retrieval_low([stored(0.03, score) for score in relevance]) is low


def test_a_fact_ranked_by_several_lists_but_judged_irrelevant_is_still_low() -> None:
    assert fused_low([2 / 61]) is False
    assert retrieval_low([stored(2 / 61, 0.1)]) is True
