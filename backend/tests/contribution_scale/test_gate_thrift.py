import json
from collections.abc import Mapping
from typing import Any

from app.models.crafts import EMBEDDING_DIMENSIONS
from app.research.candidate_gates import Candidate
from app.research.gate_thrift import GateThrift, novel_by_distance, vector_twin
from app.research.structured import StructuredReply
from app.services.candidate_gates import later_gates

from ..knowledge_writes.fakes import JUDGE_MODEL, FakeEmbedder, FakeHeldFacts, FakeJudge, held

VECTOR = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
STATEMENT = "Ajrakh cloth is dipped in the indigo vat four times before it is washed."
CANDIDATE = Candidate(ref="c1", statement=STATEMENT, field="PROCESS")
REWORDED = held("reworded", "Ajrakh cloth is dipped in the indigo vat four times, then washed.", 0.98)
OTHER_COUNT = held("count", "Ajrakh cloth is dipped in the indigo vat 4 times before it is washed.", 0.98)
NEGATED = held(
    "negated", "Ajrakh cloth is not dipped in the indigo vat four times before it is washed.", 0.98
)
FAR = held("far", "Kharad weavers of Kutch spin camel wool on a hand wheel.", 0.41)
NEAR = held("near", "Ajrakh cloth goes into the indigo vat several times.", 0.86)
ADDS = {"verdicts": [{"candidate": "c1", "adds": True, "coveredBy": [], "reason": "It counts the dips."}]}
DISTINCT = {
    "comparisons": [
        {"candidate": "c1", "held": str(NEAR.id), "relation": "DISTINCT", "reason": "Not a count."}
    ]
}


class RawJudge:
    def __init__(self, text: str, model: str) -> None:
        self.text = text
        self.model = model
        self.calls = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        return StructuredReply(text=self.text, degraded=False, model=self.model)


def test_a_vector_twin_needs_the_same_figures_no_new_negation_and_nearly_the_same_words() -> None:
    assert vector_twin(STATEMENT, [REWORDED], at_least=0.97) == REWORDED
    assert vector_twin(STATEMENT, [OTHER_COUNT], at_least=0.97) is None
    assert vector_twin(STATEMENT, [NEGATED], at_least=0.97) is None
    assert vector_twin(STATEMENT, [REWORDED], at_least=0.99) is None


def test_novelty_is_decided_by_distance_only_when_every_held_fact_is_far() -> None:
    assert novel_by_distance([FAR], below=0.75) is True
    assert novel_by_distance([FAR, NEAR], below=0.75) is False
    assert novel_by_distance([], below=0.75) is False


async def test_a_reworded_held_fact_is_refused_without_asking_the_judge() -> None:
    judge = FakeJudge()
    store = FakeHeldFacts(nearest=[REWORDED])
    later = await later_gates(
        store, [CANDIDATE], embed=FakeEmbedder(VECTOR), judge=judge, thrift=GateThrift()
    )
    (duplicate,) = later["c1"].outcomes
    assert (duplicate.gate, duplicate.passed, duplicate.related, duplicate.model) == (
        "DUPLICATE",
        False,
        [REWORDED.id],
        None,
    )
    assert judge.calls == []


async def test_without_thrift_the_same_held_fact_goes_to_the_judge() -> None:
    same = {
        "comparisons": [{"candidate": "c1", "held": str(REWORDED.id), "relation": "SAME", "reason": "Same."}]
    }
    judge = FakeJudge(same)
    later = await later_gates(
        FakeHeldFacts(nearest=[REWORDED]), [CANDIDATE], embed=FakeEmbedder(VECTOR), judge=judge
    )
    assert [(item.gate, item.passed, item.model) for item in later["c1"].outcomes] == [
        ("DUPLICATE", False, JUDGE_MODEL)
    ]
    assert len(judge.calls) == 1


async def test_a_fact_far_from_every_held_fact_passes_novelty_without_the_judge() -> None:
    judge = FakeJudge()
    later = await later_gates(
        FakeHeldFacts(nearest=[FAR]),
        [CANDIDATE],
        embed=FakeEmbedder(VECTOR),
        judge=judge,
        thrift=GateThrift(),
    )
    duplicate, novelty = later["c1"].outcomes
    assert (duplicate.passed, novelty.gate, novelty.passed, novelty.model) == (True, "NOVELTY", True, None)
    assert "similarity 0.41" in novelty.reasons[0]
    assert judge.calls == []


async def test_a_close_fact_still_goes_to_the_judge_under_thrift() -> None:
    judge = FakeJudge(DISTINCT, ADDS)
    later = await later_gates(
        FakeHeldFacts(nearest=[NEAR]),
        [CANDIDATE],
        embed=FakeEmbedder(VECTOR),
        judge=judge,
        thrift=GateThrift(),
    )
    assert [(item.gate, item.passed, item.model) for item in later["c1"].outcomes] == [
        ("DUPLICATE", True, JUDGE_MODEL),
        ("NOVELTY", True, JUDGE_MODEL),
    ]
    assert len(judge.calls) == 2


async def test_a_cheap_judge_whose_reply_fails_the_checks_hands_over_to_the_stronger_one() -> None:
    cheap = RawJudge("not json at all", "cheap-model")
    off_schema = RawJudge(json.dumps({"comparisons": []}), "middle-model")
    strong = RawJudge(json.dumps(DISTINCT), "strong-model")
    vectored = await later_gates(
        FakeHeldFacts(nearest=[NEAR]),
        [CANDIDATE],
        embed=FakeEmbedder(VECTOR),
        judge=cheap,
        escalate=(off_schema, strong),
        thrift=GateThrift(novelty_similarity=0.9),
    )
    (duplicate, novelty) = vectored["c1"].outcomes
    assert (duplicate.model, novelty.model) == ("strong-model", None)
    assert (cheap.calls, off_schema.calls, strong.calls) == (1, 1, 1)
