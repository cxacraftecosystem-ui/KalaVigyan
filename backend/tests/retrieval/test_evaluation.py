import json
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import ExternalFailure, InvalidInput
from app.models.enums import DISCIPLINES
from app.research.reranking import Relevance
from app.research.retrieval import ClaimHit, KnowledgeHits, KnowledgeQuery
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.retrieval.deadline import Deadline
from app.retrieval.evaluation import (
    EvalPace,
    GoldenQuestion,
    evaluate_golden,
    hit_claims,
    kept_fused_order,
    measures,
    recall_at,
    reciprocal_rank,
)
from app.retrieval.golden import GOLDEN_FILE, golden_questions, parse_golden
from app.retrieval.rerank import RerankCandidates, collapsed, reranked
from app.scripts.eval_retrieval import golden_claim_id

SEED_FILE = Path(__file__).resolve().parents[2] / "app" / "data" / "seed_claims.json"
QUESTIONS_FLOOR = 60
CRAFTS_FLOOR = 12


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-evaluation/{name}")


def claim_hit(found: uuid.UUID, rank: int, **changes: Any) -> ClaimHit:
    return ClaimHit(
        claim_id=found,
        text="A stored claim.",
        level="PROVISIONAL",
        subject_type="CONCEPT",
        subject_id=found,
        score=1.0 / rank,
        **changes,
    )


class RankedRetriever:
    def __init__(
        self,
        ranked: Mapping[str, Sequence[uuid.UUID]],
        *,
        reranked: Mapping[str, Sequence[uuid.UUID]] | None = None,
        folded: Mapping[uuid.UUID, tuple[uuid.UUID, ...]] | None = None,
        reranks: bool = True,
    ) -> None:
        self.ranked = ranked
        self.reranked = reranked if reranked is not None else ranked
        self.folded = folded or {}
        self.reranks = reranks
        self.queries: list[KnowledgeQuery] = []

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        order = self.reranked if query.rerank else self.ranked
        hits = tuple(
            self.hit(found, rank, query.rerank) for rank, found in enumerate(order[query.text], start=1)
        )
        return KnowledgeHits(craft_slug=query.craft_slug, claims=hits)

    def hit(self, found: uuid.UUID, rank: int, rerank: bool) -> ClaimHit:
        if not rerank:
            return claim_hit(found, rank)
        scored = 1.0 / rank if self.reranks else None
        return claim_hit(found, rank, relevance_score=scored, corroborating_ids=self.folded.get(found, ()))


def test_recall_counts_the_facts_any_of_whose_claims_is_within_the_depth() -> None:
    ranked = [{"a"}, {"b"}, {"c"}, {"d"}, {"e"}, {"f"}]
    assert recall_at(ranked, [{"b"}, {"f"}], 5) == 0.5
    assert recall_at(ranked, [{"a"}, {"e"}], 5) == 1.0
    assert recall_at(ranked, [{"f", "c"}, {"z", "y"}], 5) == 0.5
    assert recall_at(ranked, [{"z"}], 5) == 0.0
    with pytest.raises(InvalidInput):
        recall_at(ranked, [], 5)
    with pytest.raises(InvalidInput):
        recall_at(ranked, [{"a"}, set()], 5)


def test_the_reciprocal_rank_is_that_of_the_first_claim_of_any_fact() -> None:
    ranked = [{"a"}, {"b"}, {"c"}, {"d"}]
    assert reciprocal_rank(ranked, [{"c"}, {"d"}]) == pytest.approx(1 / 3)
    assert reciprocal_rank(ranked, [{"z", "b"}]) == pytest.approx(1 / 2)
    assert reciprocal_rank(ranked, [{"a"}]) == 1.0
    assert reciprocal_rank(ranked, [{"z"}]) == 0.0


def test_a_claim_folded_into_a_hit_as_a_restatement_is_found_at_that_hit() -> None:
    ranked = [{"a"}, {"b", "x"}, {"c"}, {"d"}, {"e"}, {"f", "y"}]
    assert recall_at(ranked, [{"x"}, {"y"}], 5) == 0.5
    assert recall_at(ranked, [{"x"}, {"y"}], 6) == 1.0
    assert reciprocal_rank(ranked, [{"x"}]) == pytest.approx(1 / 2)
    assert reciprocal_rank(ranked, [{"y"}]) == pytest.approx(1 / 6)


async def test_the_report_averages_recall_and_reciprocal_rank_over_the_questions() -> None:
    golden = (
        GoldenQuestion(
            key="first", craft_slug="Kutch-Ajrakh", question="q1", expected=("x", ("y", "w")), field="HISTORY"
        ),
        GoldenQuestion(key="second", craft_slug=None, question="q2", expected=("z",), fields=("CHEMISTRY",)),
    )
    ids = {name: key(name) for name in ("x", "y", "w", "z")}
    noise = [key(f"noise-{n}") for n in range(6)]
    retriever = RankedRetriever({"q1": [noise[0], ids["x"], *noise[1:5], ids["y"]], "q2": [ids["z"]]})
    report = (await evaluate_golden(retriever, golden, claim_id=ids.__getitem__)).fused
    assert report.recall_at_depth == pytest.approx((0.5 + 1.0) / 2)
    assert report.mean_reciprocal_rank == pytest.approx((1 / 2 + 1) / 2)
    assert report.as_dict()["misses"] == {"first": ["y or w"]}
    assert report.as_dict()["byField"] == {
        "HISTORY": {"questions": 1, "recallAt5": 0.5, "meanReciprocalRank": 0.5, "recallAt20": 1.0}
    }
    assert report.as_dict()["byCraft"] == {
        "Kutch-Ajrakh": {"questions": 1, "recallAt5": 0.5, "meanReciprocalRank": 0.5, "recallAt20": 1.0}
    }
    assert [(q.mode, q.limit, q.fields, q.rerank) for q in retriever.queries] == [
        ("HYBRID", 20, (), False),
        ("HYBRID", 20, (), True),
        ("HYBRID", 20, ("CHEMISTRY",), False),
        ("HYBRID", 20, ("CHEMISTRY",), True),
    ]


async def test_both_orders_are_scored_and_a_restatement_folded_into_a_hit_counts_as_found() -> None:
    golden = (GoldenQuestion(key="folded", craft_slug=None, question="q", expected=("x",)),)
    ids = {"x": key("x")}
    noise = [key(f"noise-{n}") for n in range(8)]
    retriever = RankedRetriever(
        {"q": [*noise[:6], ids["x"]]}, reranked={"q": [noise[6], noise[7]]}, folded={noise[7]: (ids["x"],)}
    )
    report = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__)
    assert (report.reranked.recall_at_depth, report.reranked.mean_reciprocal_rank) == (1.0, 0.5)
    assert (report.fused.recall_at_depth, report.fused.recall_wide) == (0.0, 1.0)
    assert report.fused.mean_reciprocal_rank == pytest.approx(1 / 7)
    assert report.fell_back == () and set(report.compared()) == {"reranked", "fused"}
    shown = report.as_dict()
    assert (shown["reranked"]["recallAt5"], shown["reranked"]["meanReciprocalRank"]) == (1.0, 0.5)
    assert shown["reranked"]["fellBackToFused"] == []
    assert (shown["fused"]["recallAt5"], shown["fused"]["misses"]) == (0.0, {"folded": ["x"]})
    assert report.summary()["fused"] == {
        "questions": 1,
        "recallAt5": 0.0,
        "meanReciprocalRank": round(1 / 7, 4),
        "recallAt20": 1.0,
        "skipped": 0,
    }


async def test_a_rerank_that_kept_the_fused_order_is_reported_and_its_floors_are_not_compared() -> None:
    golden = tuple(
        GoldenQuestion(key=f"k{n}", craft_slug=None, question=f"q{n}", expected=("x",)) for n in range(2)
    )
    ids = {"x": key("x")}
    retriever = RankedRetriever({"q0": [ids["x"]], "q1": []}, reranks=False)
    report = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__)
    assert report.fell_back == ("k0",)
    assert list(report.compared()) == ["fused"]
    assert report.as_dict()["reranked"]["fellBackToFused"] == ["k0"]


async def test_a_failed_rerank_leaves_hits_the_evaluation_reads_as_the_fused_order() -> None:
    hits = [claim_hit(key("first"), 1), claim_hit(key("second"), 2)]

    async def failing(query: str, documents: Sequence[str]) -> list[Relevance]:
        raise ExternalFailure("the rerank route is down", service="rerank")

    async def ordering(query: str, documents: Sequence[str]) -> list[Relevance]:
        return [Relevance(index=1, score=0.9), Relevance(index=0, score=0.2)]

    kept = await reranked(hits, RerankCandidates(), query="q", rerank=failing)
    ordered = await reranked(hits, RerankCandidates(), query="q", rerank=ordering)
    assert kept_fused_order(KnowledgeHits(craft_slug=None, claims=tuple(kept)))
    assert not kept_fused_order(KnowledgeHits(craft_slug=None, claims=tuple(ordered)))
    assert not kept_fused_order(KnowledgeHits(craft_slug=None))
    folded = collapsed(ordered, (), limit=20)
    assert [hit_claims(hit) for hit in folded] == [(key("second"), key("first"))]


async def test_a_fact_is_found_through_any_claim_that_states_it() -> None:
    golden = (GoldenQuestion(key="same", craft_slug=None, question="q", expected=(("x", "y", "w"),)),)
    ids = {name: key(name) for name in ("x", "y", "w")}
    noise = [key(f"noise-{n}") for n in range(5)]
    report = await evaluate_golden(
        RankedRetriever({"q": [*noise[:3], ids["w"], *noise[3:]]}), golden, claim_id=ids.__getitem__
    )
    assert (report.fused.recall_at_depth, report.fused.mean_reciprocal_rank) == (1.0, 0.25)
    assert report.fused.as_dict()["misses"] == {}


async def test_expected_hits_missing_from_the_database_are_reported_not_scored() -> None:
    golden = (
        GoldenQuestion(key="kept", craft_slug=None, question="q1", expected=("x", ("gone", "y"))),
        GoldenQuestion(key="lost", craft_slug=None, question="q2", expected=("lost",)),
    )
    ids = {name: key(name) for name in ("x", "gone", "y", "lost")}
    retriever = RankedRetriever({"q1": [ids["x"], ids["y"]], "q2": []})
    found = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__, present={ids["x"], ids["y"]})
    for report in (found.reranked, found.fused):
        assert report.absent == ("gone", "lost")
        assert [result.key for result in report.results] == ["kept"]
        assert report.recall_at_depth == 1.0 and report.mean_reciprocal_rank == 1.0
    assert [query.text for query in retriever.queries] == ["q1", "q1"]


def test_a_golden_question_lists_each_expected_hit_once() -> None:
    with pytest.raises(ValidationError):
        GoldenQuestion(key="twice", craft_slug=None, question="q", expected=("x", "x"))
    with pytest.raises(ValidationError):
        GoldenQuestion(key="across", craft_slug=None, question="q", expected=("x", ("y", "x")))
    with pytest.raises(ValidationError):
        GoldenQuestion(key="none", craft_slug=None, question="q", expected=())
    with pytest.raises(ValidationError):
        GoldenQuestion(key="hollow", craft_slug=None, question="q", expected=((),))


def test_the_questions_file_is_versioned_and_each_key_is_its_own() -> None:
    one = {"key": "a", "craftSlug": None, "question": "q", "expected": ["x"]}
    assert [q.key for q in parse_golden({"version": 1, "questions": [one]})] == ["a"]
    with pytest.raises(InvalidInput, match="version 1"):
        parse_golden({"version": 2, "questions": [one]})
    with pytest.raises(InvalidInput, match="key of its own"):
        parse_golden({"version": 1, "questions": [one, one]})
    with pytest.raises(InvalidInput, match="malformed"):
        parse_golden({"version": 1, "questions": [{**one, "expected": []}]})


def test_the_golden_set_spans_sixty_questions_twelve_crafts_and_all_sixteen_fields() -> None:
    golden = golden_questions()
    assert len(golden) >= QUESTIONS_FLOOR
    assert len({question.craft_slug for question in golden if question.craft_slug}) >= CRAFTS_FLOOR
    assert all(question.field is not None for question in golden)
    assert {question.field for question in golden} == set(DISCIPLINES)
    assert len(DISCIPLINES) == 16
    assert json.loads(GOLDEN_FILE.read_text(encoding="utf-8"))["version"] == 1


def test_every_golden_claim_is_a_seed_of_the_named_craft_or_a_claim_id() -> None:
    data = json.loads(SEED_FILE.read_text(encoding="utf-8"))
    claims = {row["id"]: row for row in data["claims"]}
    types = {row["key"]: row["type"] for row in data["concepts"]}
    for question in golden_questions():
        for fact in question.facts:
            for name in fact:
                assert isinstance(golden_claim_id(name), uuid.UUID), name
                if not name.startswith("seed-"):
                    continue
                claim = claims[name]
                field = CONCEPT_TYPE_DISCIPLINES.get(types[claim["subjectKey"]])
                assert claim["subjectType"] == "CONCEPT" and claim["evidenceLevel"] == "PROVISIONAL", name
                assert claim["craftSlug"] == question.craft_slug, name
                assert not question.fields or field is None or field in question.fields, name


async def test_recall_at_twenty_counts_a_fact_found_below_the_first_five() -> None:
    golden = (GoldenQuestion(key="deep", craft_slug="A", question="q", expected=("x", "y")),)
    ids = {name: key(name) for name in ("x", "y")}
    noise = [key(f"noise-{n}") for n in range(20)]
    ranked = [*noise[:12], ids["x"], *noise[12:]]
    report = await evaluate_golden(RankedRetriever({"q": ranked}), golden, claim_id=ids.__getitem__)
    for overall in report.as_dict().values():
        assert (overall["recallAt5"], overall["recallAt20"]) == (0.0, 0.5)
        assert overall["meanReciprocalRank"] == round(1 / 13, 4)


def test_measures_of_no_questions_are_empty() -> None:
    assert measures([]).as_dict() == {
        "questions": 0,
        "recallAt5": None,
        "meanReciprocalRank": None,
        "recallAt20": None,
    }


class TickingRetriever(RankedRetriever):
    def __init__(self, ranked: Mapping[str, Sequence[uuid.UUID]], now: list[float]) -> None:
        super().__init__(ranked)
        self.now = now

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.now[0] += 1.0
        return await super().search(query)


async def test_a_spent_time_budget_asks_no_more_questions_and_says_so() -> None:
    golden = tuple(
        GoldenQuestion(key=f"k{n}", craft_slug=None, question=f"q{n}", expected=("x",)) for n in range(3)
    )
    ids = {"x": key("x")}
    now = [0.0]
    retriever = TickingRetriever({f"q{n}": [ids["x"]] for n in range(3)}, now)
    pace = EvalPace(deadline=Deadline(at=1.0, clock=lambda: now[0]))
    found = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__, pace=pace)
    for report in (found.reranked, found.fused):
        assert [result.key for result in report.results] == ["k0"]
        assert (report.skipped, report.complete) == (2, False)
        assert report.as_dict()["skipped"] == 2
    assert not found.complete and found.summary()["reranked"]["skipped"] == 2


async def test_questions_asked_side_by_side_keep_their_order() -> None:
    golden = tuple(
        GoldenQuestion(key=f"k{n}", craft_slug=None, question=f"q{n}", expected=("x",)) for n in range(6)
    )
    ids = {"x": key("x")}
    retriever = RankedRetriever({f"q{n}": [ids["x"]] for n in range(6)})
    found = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__, pace=EvalPace(concurrency=4))
    for report in (found.reranked, found.fused):
        assert [result.key for result in report.results] == [f"k{n}" for n in range(6)]
        assert report.complete and report.recall_at_depth == 1.0


async def test_a_claim_judged_to_answer_widens_the_fact_it_was_asked_for() -> None:
    golden = (GoldenQuestion(key="judged", craft_slug=None, question="q", expected=("x",)),)
    ids = {"x": key("x")}
    other = key("other")
    report = await evaluate_golden(
        RankedRetriever({"q": [other, ids["x"]]}), golden, claim_id=ids.__getitem__
    )
    (result,) = report.reranked.results
    assert (result.first, result.other_first, result.recall, result.reciprocal_rank) == (
        other,
        other,
        1.0,
        0.5,
    )
    widened = result.answered_by(other, "other")
    assert (widened.recall, widened.reciprocal_rank) == (1.0, 1.0)
    assert widened.expected_claims == {ids["x"], other}


def test_an_evaluation_asks_at_least_one_question_at_a_time() -> None:
    with pytest.raises(InvalidInput):
        EvalPace(concurrency=0)
