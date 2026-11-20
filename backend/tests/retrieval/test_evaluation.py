import json
import uuid
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.models.enums import DISCIPLINES
from app.research.retrieval import ClaimHit, KnowledgeHits, KnowledgeQuery
from app.research.vocabulary import CONCEPT_TYPE_DISCIPLINES
from app.retrieval.evaluation import (
    GoldenQuestion,
    evaluate_golden,
    recall_at,
    reciprocal_rank,
)
from app.retrieval.golden import GOLDEN_FILE, golden_questions, parse_golden
from app.scripts.eval_retrieval import golden_claim_id

SEED_FILE = Path(__file__).resolve().parents[2] / "app" / "data" / "seed_claims.json"
QUESTIONS_FLOOR = 60
CRAFTS_FLOOR = 12


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-evaluation/{name}")


class RankedRetriever:
    def __init__(self, ranked: Mapping[str, Sequence[uuid.UUID]]) -> None:
        self.ranked = ranked
        self.queries: list[KnowledgeQuery] = []

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        self.queries.append(query)
        hits = tuple(
            ClaimHit(
                claim_id=found,
                text="A stored claim.",
                level="PROVISIONAL",
                subject_type="CONCEPT",
                subject_id=found,
                score=1.0 / rank,
            )
            for rank, found in enumerate(self.ranked[query.text], start=1)
        )
        return KnowledgeHits(craft_slug=query.craft_slug, claims=hits)


def test_recall_counts_the_facts_any_of_whose_claims_is_within_the_depth() -> None:
    ranked = ["a", "b", "c", "d", "e", "f"]
    assert recall_at(ranked, [{"b"}, {"f"}], 5) == 0.5
    assert recall_at(ranked, [{"a"}, {"e"}], 5) == 1.0
    assert recall_at(ranked, [{"f", "c"}, {"z", "y"}], 5) == 0.5
    assert recall_at(ranked, [{"z"}], 5) == 0.0
    with pytest.raises(InvalidInput):
        recall_at(ranked, [], 5)
    with pytest.raises(InvalidInput):
        recall_at(ranked, [{"a"}, set()], 5)


def test_the_reciprocal_rank_is_that_of_the_first_claim_of_any_fact() -> None:
    ranked = ["a", "b", "c", "d"]
    assert reciprocal_rank(ranked, [{"c"}, {"d"}]) == pytest.approx(1 / 3)
    assert reciprocal_rank(ranked, [{"z", "b"}]) == pytest.approx(1 / 2)
    assert reciprocal_rank(ranked, [{"a"}]) == 1.0
    assert reciprocal_rank(ranked, [{"z"}]) == 0.0


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
    report = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__)
    assert report.recall_at_depth == pytest.approx((0.5 + 1.0) / 2)
    assert report.mean_reciprocal_rank == pytest.approx((1 / 2 + 1) / 2)
    assert report.as_dict()["misses"] == {"first": ["y or w"]}
    assert report.as_dict()["recallByField"] == {"HISTORY": 0.5}
    assert [(q.mode, q.limit, q.fields) for q in retriever.queries] == [
        ("HYBRID", 10, ()),
        ("HYBRID", 10, ("CHEMISTRY",)),
    ]


async def test_a_fact_is_found_through_any_claim_that_states_it() -> None:
    golden = (GoldenQuestion(key="same", craft_slug=None, question="q", expected=(("x", "y", "w"),)),)
    ids = {name: key(name) for name in ("x", "y", "w")}
    noise = [key(f"noise-{n}") for n in range(5)]
    report = await evaluate_golden(
        RankedRetriever({"q": [*noise[:3], ids["w"], *noise[3:]]}), golden, claim_id=ids.__getitem__
    )
    assert (report.recall_at_depth, report.mean_reciprocal_rank) == (1.0, 0.25)
    assert report.as_dict()["misses"] == {}


async def test_expected_hits_missing_from_the_database_are_reported_not_scored() -> None:
    golden = (
        GoldenQuestion(key="kept", craft_slug=None, question="q1", expected=("x", ("gone", "y"))),
        GoldenQuestion(key="lost", craft_slug=None, question="q2", expected=("lost",)),
    )
    ids = {name: key(name) for name in ("x", "gone", "y", "lost")}
    retriever = RankedRetriever({"q1": [ids["x"], ids["y"]], "q2": []})
    report = await evaluate_golden(retriever, golden, claim_id=ids.__getitem__, present={ids["x"], ids["y"]})
    assert report.absent == ("gone", "lost")
    assert [result.key for result in report.results] == ["kept"]
    assert report.recall_at_depth == 1.0 and report.mean_reciprocal_rank == 1.0
    assert [query.text for query in retriever.queries] == ["q1"]


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
