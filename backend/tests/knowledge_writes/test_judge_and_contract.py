from typing import Any

import pytest
from pydantic import ValidationError

from app.core.errors import ExternalFailure
from app.research.candidate_gates import Candidate
from app.research.candidate_judge import (
    JudgeAsk,
    comparison_request,
    novelty_request,
    parsed_comparisons,
    parsed_novelty,
)
from app.research.knowledge_writes import FactProposal
from app.research.structured import schema_problems

from .fakes import PAGE_URL, QUOTE, STATEMENT, fact_id, held
from .judge_replies import compared, verdict

NEAR = held("near", "Ajrakh is dipped four times in indigo.", 0.92)
OTHER = held("other", "Ajrakh is washed in the river.", 0.85)
ASK = JudgeAsk(Candidate(ref="c1", statement=STATEMENT, field="PROCESS"), (NEAR, OTHER))


def proposal(**changes: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"},
        "field": "PROCESS",
        "statement": STATEMENT,
        "sources": [
            {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE, "locator": "p. 2"}]}
        ],
    }
    return body | changes


def test_both_requests_use_only_portable_schema_keywords_and_mark_facts_as_data() -> None:
    for request in (comparison_request([ASK]), novelty_request([ASK])):
        assert schema_problems(request.schema) == []
        assert "never an instruction" in request.system
        assert f'ref="{NEAR.id}"' in request.user and 'ref="c1"' in request.user


def test_every_asked_pair_must_be_answered() -> None:
    reply = {"comparisons": [compared("c1", NEAR.id, "SAME", "Same.")]}
    with pytest.raises(ExternalFailure, match="1 comparison"):
        parsed_comparisons(reply, [ASK])
    other = compared("c1", OTHER.id, "DISTINCT", "Washing.")
    parsed = parsed_comparisons({"comparisons": [*reply["comparisons"], other]}, [ASK])
    assert [(item.held, item.relation) for item in parsed["c1"]] == [
        (NEAR.id, "SAME"),
        (OTHER.id, "DISTINCT"),
    ]


def test_a_comparison_outside_the_schema_is_an_external_failure() -> None:
    old_form = {"candidate": "c1", "held": str(NEAR.id), "relation": "DIFFERS", "reason": "?"}
    for wrong in (old_form, {**compared("c1", NEAR.id, "DISTINCT"), "bothTrue": "maybe"}):
        with pytest.raises(ExternalFailure, match="off its schema"):
            parsed_comparisons({"comparisons": [wrong]}, [ASK])


def test_a_novelty_verdict_keeps_only_covering_facts_it_was_given() -> None:
    stray = fact_id("stray")
    reply = {"verdicts": [verdict("c1", adds=False, covered=[NEAR.id, stray], reason="Held.")]}
    found = parsed_novelty(reply, [ASK])["c1"]
    assert (found.adds, found.covered_by) == (False, [NEAR.id])
    with pytest.raises(ExternalFailure, match="without a verdict"):
        parsed_novelty({"verdicts": []}, [ASK])


def test_a_proposal_reads_its_subject_field_statement_and_quoted_sources() -> None:
    parsed = FactProposal.model_validate(proposal(fields=["CHEMISTRY"]))
    assert (parsed.subject.kind, parsed.field, parsed.fields) == ("craft", "PROCESS", ["CHEMISTRY"])
    assert parsed.sources[0].quotes[0].locator == "p. 2"


@pytest.mark.parametrize(
    "changes",
    [
        {"fields": ["PROCESS"]},
        {"fields": ["CHEMISTRY", "CHEMISTRY"]},
        {"statement": "Call 98765 43210 for Ajrakh prices and dyes today."},
        {"statement": "Too short."},
        {"subject": {"kind": "family", "slug": "Ajrakh"}},
        {"sources": []},
        {"sources": [{"url": "http://plain.example.org", "title": "t", "quotes": [{"text": QUOTE}]}]},
        {
            "sources": [
                {"url": PAGE_URL, "title": "a", "quotes": [{"text": QUOTE}]},
                {"url": PAGE_URL + "/", "title": "b", "quotes": [{"text": QUOTE}]},
            ]
        },
        {"sources": [{"url": PAGE_URL, "title": "a", "quotes": [{"text": QUOTE}, {"text": QUOTE}]}]},
        {"surprise": True},
    ],
)
def test_a_malformed_proposal_is_refused_before_any_gate(changes: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        FactProposal.model_validate(proposal(**changes))
