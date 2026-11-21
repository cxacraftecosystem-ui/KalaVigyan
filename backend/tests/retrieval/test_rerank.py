import logging
import uuid
from collections.abc import Sequence

import pytest

from app.core.errors import ExternalFailure
from app.providers.router import RouterError
from app.research.reranking import Relevance
from app.research.retrieval import ClaimHit
from app.retrieval.rerank import (
    RERANK_POOL,
    RESTATEMENT_COSINE,
    RerankCandidates,
    claim_title,
    collapsed,
    folded_words,
    pool_size,
    reranked,
)


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-rerank/{name}")


ALUM, ALUM_AGAIN, ALUM_REWORDED = key("alum"), key("alum-again"), key("alum-reworded")
INDIGO, WASH = key("indigo"), key("wash")
TEXTS = {
    ALUM: "Alum fixes the red dye to the cotton.",
    ALUM_AGAIN: "alum fixes the red dye, to the cotton",
    ALUM_REWORDED: "The red dye is fixed to the cotton by alum.",
    INDIGO: "Indigo is reduced in a lime vat before dyeing.",
    WASH: "The printed cloth is washed in the river.",
}


def hit(claim_id: uuid.UUID, rank: int) -> ClaimHit:
    return ClaimHit(
        claim_id=claim_id,
        text=TEXTS[claim_id],
        level="PROVISIONAL",
        subject_type="CONCEPT",
        subject_id=key("concept"),
        score=1 / (60 + rank),
        vector_rank=rank,
    )


FUSED = [hit(claim, rank) for rank, claim in enumerate((ALUM, INDIGO, ALUM_AGAIN, WASH, ALUM_REWORDED), 1)]
DOCUMENTS = RerankCandidates({item.claim_id: f"title: none | text: {item.text}" for item in FUSED})


class Scores:
    def __init__(self, scores: Sequence[float] | None = None, *, failure: Exception | None = None) -> None:
        self.scores = scores
        self.failure = failure
        self.asked: list[tuple[str, list[str]]] = []

    async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
        self.asked.append((query, list(documents)))
        if self.failure is not None:
            raise self.failure
        assert self.scores is not None
        return [Relevance(index=index, score=score) for index, score in enumerate(self.scores)]


async def test_the_candidates_are_sent_once_and_come_back_in_relevance_order_with_their_scores() -> None:
    scores = Scores([0.30, 0.40, 0.95, 0.80, 0.70])
    ordered = await reranked(FUSED, DOCUMENTS, query="Which mordant fixes red?", rerank=scores)
    assert scores.asked == [
        ("Which mordant fixes red?", [DOCUMENTS.documents[item.claim_id] for item in FUSED])
    ]
    assert [(item.claim_id, item.relevance_score) for item in ordered] == [
        (ALUM_AGAIN, 0.95),
        (WASH, 0.80),
        (ALUM_REWORDED, 0.70),
        (INDIGO, 0.40),
        (ALUM, 0.30),
    ]
    assert [item.score for item in ordered] == [1 / 63, 1 / 64, 1 / 65, 1 / 62, 1 / 61]


@pytest.mark.parametrize(
    "failure",
    [
        RouterError("ceiling", "This answer reached the cost limit for its depth."),
        RouterError("no_key", "No enabled rerank route has a key"),
        ExternalFailure("Voyage answered 503 to rerank", kind="unavailable"),
    ],
)
async def test_a_failed_refused_or_keyless_rerank_keeps_the_fused_order_and_logs_once(
    failure: Exception, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="app.retrieval.rerank"):
        ordered = await reranked(FUSED, DOCUMENTS, query="q", rerank=Scores(failure=failure))
    assert ordered == FUSED
    assert all(item.relevance_score is None for item in ordered)
    assert len([record for record in caplog.records if record.name == "app.retrieval.rerank"]) == 1


async def test_without_a_reranker_the_fused_order_stands() -> None:
    assert await reranked(FUSED, DOCUMENTS, query="q", rerank=None) == FUSED


async def test_an_index_outside_the_candidates_is_a_failure_and_keeps_the_fused_order() -> None:
    class Outside(Scores):
        async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
            return [Relevance(index=len(documents), score=0.9)]

    assert await reranked(FUSED, DOCUMENTS, query="q", rerank=Outside()) == FUSED


async def test_candidates_the_reranker_did_not_score_follow_in_their_fused_order() -> None:
    class Two(Scores):
        async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
            return [Relevance(index=3, score=0.6), Relevance(index=1, score=0.9)]

    ordered = await reranked(FUSED, DOCUMENTS, query="q", rerank=Two())
    assert [item.claim_id for item in ordered] == [INDIGO, WASH, ALUM, ALUM_AGAIN, ALUM_REWORDED]


def test_three_restatements_of_one_fact_take_one_slot_and_two_other_facts_keep_theirs() -> None:
    ordered = [
        hit(claim, rank) for rank, claim in enumerate((ALUM_AGAIN, WASH, ALUM, INDIGO, ALUM_REWORDED), 1)
    ]
    by_vector = {frozenset((ALUM, ALUM_REWORDED))}
    kept = collapsed(ordered, by_vector, limit=3)
    assert [item.claim_id for item in kept] == [ALUM_AGAIN, WASH, INDIGO]
    assert [item.corroborating_ids for item in kept] == [(ALUM, ALUM_REWORDED), (), ()]


def test_the_limit_counts_distinct_facts_and_drops_the_rest() -> None:
    ordered = [hit(claim, rank) for rank, claim in enumerate((ALUM, ALUM_AGAIN, INDIGO, WASH), 1)]
    kept = collapsed(ordered, frozenset(), limit=2)
    assert [(item.claim_id, item.corroborating_ids) for item in kept] == [(ALUM, (ALUM_AGAIN,)), (INDIGO, ())]


def test_texts_fold_to_their_words_whatever_their_case_and_punctuation() -> None:
    assert (
        folded_words(TEXTS[ALUM]) == folded_words(TEXTS[ALUM_AGAIN]) == "alum fixes the red dye to the cotton"
    )
    assert folded_words(TEXTS[ALUM]) != folded_words(TEXTS[ALUM_REWORDED])
    assert folded_words("ＡＬＵＭ_mordant") == "alum mordant"


def test_a_candidate_is_titled_by_its_craft_concept_and_field_where_known() -> None:
    assert (
        claim_title("Kutch Ajrakh", "Alum (mordant)", "CHEMISTRY")
        == "Kutch Ajrakh, Alum (mordant), chemistry"
    )
    assert claim_title(None, "Alum (mordant)", None) == "Alum (mordant)"
    assert claim_title(None, None, None) is None


def test_the_pool_is_wide_and_the_restatement_cosine_is_tight() -> None:
    assert (RERANK_POOL, pool_size(12), pool_size(50)) == (60, 60, 60)
    assert RESTATEMENT_COSINE >= 0.95
