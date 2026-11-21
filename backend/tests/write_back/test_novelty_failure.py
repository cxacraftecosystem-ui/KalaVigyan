from collections.abc import Mapping
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.models.crafts import EMBEDDING_DIMENSIONS
from app.research.candidate_gates import Candidate
from app.research.structured import StructuredReply
from app.services.candidate_gates import later_gates
from app.services.write_back_gates import write_back_later_gates

from ..knowledge_writes.fakes import JUDGE_MODEL, STATEMENT, FakeEmbedder, FakeHeldFacts, FakeJudge, held

VECTOR = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
KNOWN = Candidate(ref="c1", statement=STATEMENT, field="PROCESS")
NEW = Candidate(ref="c2", statement="Ajrakh printers wash the cloth in running water.", field="PROCESS")
NEAR = held("near", "Ajrakh cloth goes into the vat four times.", 0.95)
COMPARED = {
    "comparisons": [
        {"candidate": "c1", "held": str(NEAR.id), "relation": "SAME", "reason": "Both count four dips."},
        {"candidate": "c2", "held": str(NEAR.id), "relation": "DISTINCT", "reason": "Washing is not dyeing."},
    ]
}


class NoveltyFails(FakeJudge):
    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        if not self.replies:
            self.calls.append({"system": system, "user": user, "schema": dict(schema)})
            raise ExternalFailure("the judge route timed out", kind="unavailable", service="model")
        return await super().__call__(system=system, user=user, schema=schema)


async def test_a_failed_novelty_call_leaves_novelty_unjudged_and_keeps_the_duplicate_verdicts() -> None:
    judge = NoveltyFails(COMPARED)
    later = await write_back_later_gates(
        FakeHeldFacts(nearest=[NEAR]), [KNOWN, NEW], embed=FakeEmbedder(VECTOR), judge=judge
    )
    assert len(judge.calls) == 2
    (refused,) = later["c1"].outcomes
    assert (refused.gate, refused.passed, refused.related, refused.model) == (
        "DUPLICATE",
        False,
        [NEAR.id],
        JUDGE_MODEL,
    )
    (kept,) = later["c2"].outcomes
    assert (kept.gate, kept.passed, kept.model) == ("DUPLICATE", True, JUDGE_MODEL)
    assert later["c2"].vector == VECTOR


async def test_a_proposal_s_gates_still_refuse_to_go_on_when_the_novelty_call_fails() -> None:
    with pytest.raises(ExternalFailure):
        await later_gates(
            FakeHeldFacts(nearest=[NEAR]),
            [KNOWN, NEW],
            embed=FakeEmbedder(VECTOR),
            judge=NoveltyFails(COMPARED),
        )
