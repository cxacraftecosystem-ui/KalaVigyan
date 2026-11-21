import ast
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from app.core.errors import InvalidInput
from app.models import answer_gaps as gap_rows
from app.models.enums import DISCIPLINES
from app.research.open_work import TASK_KINDS, TASK_PROMPTS, parse_task_key
from app.research.open_work_gap_keys import gap_detail, gap_id, is_gap_detail
from app.research.open_work_gaps import (
    Asked,
    FieldReading,
    accepted,
    answer_verdict,
    found_facts,
    gap_count,
    gap_priority,
    nearest_gap,
)
from app.research.retrieval import ClaimHit, KnowledgeHits

REPO = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
ALUM = uuid.UUID("0f000000-0000-4000-8000-000000000001")
LAKE = uuid.UUID("0f000000-0000-4000-8000-000000000002")
WASH = uuid.UUID("0f000000-0000-4000-8000-000000000003")
GAP = uuid.UUID("0f000000-0000-4000-8000-0000000000aa")
NEAR = uuid.UUID("0f000000-0000-4000-8000-0000000000bb")


def test_an_answer_with_three_cited_sentences_in_each_asked_field_is_answered() -> None:
    verdict = answer_verdict(
        [FieldReading("HISTORY", 4, claim_ids=(ALUM,)), FieldReading("CHEMISTRY", 3, claim_ids=(LAKE,))]
    )
    assert (verdict.verdict, verdict.fields, verdict.lacking, verdict.lacks, verdict.sentences) == (
        "ANSWERED",
        ("CHEMISTRY", "HISTORY"),
        (),
        (),
        7,
    )


def test_an_answer_with_no_cited_sentence_could_not_answer_from_cited_evidence() -> None:
    verdict = answer_verdict([FieldReading("PROCESS", 0, retrieval_low=True), FieldReading("OVERVIEW", 0)])
    assert (verdict.verdict, verdict.fields, verdict.lacking, verdict.lacks, verdict.sentences) == (
        "UNANSWERED",
        ("OVERVIEW", "PROCESS"),
        ("OVERVIEW", "PROCESS"),
        ("NO_CITED_EVIDENCE",),
        0,
    )


def test_a_thin_answer_names_each_field_that_lacked_and_what_it_lacked() -> None:
    readings = [
        FieldReading("CHEMISTRY", 5, claim_ids=(ALUM, LAKE)),
        FieldReading("HISTORY", 2, claim_ids=(WASH,)),
        FieldReading("GEOGRAPHY", 0),
        FieldReading("PROCESS", 4, retrieval_low=True),
    ]
    verdict = answer_verdict(readings, frozenset({LAKE}))
    assert verdict.verdict == "THIN"
    assert verdict.fields == ("PROCESS", "CHEMISTRY", "GEOGRAPHY", "HISTORY")
    assert verdict.lacking == ("PROCESS", "CHEMISTRY", "GEOGRAPHY", "HISTORY")
    assert verdict.lacks == ("MISSING_FIELD", "FEW_SENTENCES", "LOW_RETRIEVAL", "FAILED_QUOTE")
    assert verdict.sentences == 11


@pytest.mark.parametrize(
    ("sentences", "lacks"),
    [(1, ("FEW_SENTENCES",)), (2, ("FEW_SENTENCES",)), (3, ()), (8, ())],
)
def test_a_field_is_thin_below_three_cited_sentences(sentences: int, lacks: tuple[str, ...]) -> None:
    assert answer_verdict([FieldReading("BOTANY", sentences)]).lacks == lacks


def test_a_field_answered_twice_is_judged_once_on_both_readings() -> None:
    verdict = answer_verdict(
        [FieldReading("HISTORY", 2, retrieval_low=True), FieldReading("HISTORY", 1, retrieval_low=False)]
    )
    assert (verdict.verdict, verdict.fields, verdict.sentences) == ("ANSWERED", ("HISTORY",), 3)


def test_an_answer_is_judged_only_on_known_fields() -> None:
    with pytest.raises(InvalidInput, match="sixteen fields"):
        answer_verdict([FieldReading("ALCHEMY", 3)])
    with pytest.raises(InvalidInput, match="none were given"):
        answer_verdict([])


def asked(who: str, days_ago: float, lacking: tuple[str, ...], lacks: tuple[str, ...]) -> Asked:
    return Asked(asker=who, asked_at=NOW - timedelta(days=days_ago), lacking=lacking, lacks=lacks)


def test_a_group_counts_each_reader_once_within_ninety_days() -> None:
    members = [
        asked("reader-a", 2, ("CHEMISTRY",), ("FEW_SENTENCES",)),
        asked("reader-a", 9, ("CHEMISTRY",), ("FEW_SENTENCES",)),
        asked("reader-b", 1, ("HISTORY", "CHEMISTRY"), ("NO_CITED_EVIDENCE",)),
        asked("reader-c", 90, ("BOTANY",), ("LOW_RETRIEVAL",)),
        asked("reader-d", 91, ("POLICY",), ("FAILED_QUOTE",)),
    ]
    count = gap_count(members, now=NOW)
    assert count.askers == 3
    assert count.last_asked == NOW - timedelta(days=1)
    assert count.fields == ("CHEMISTRY", "BOTANY", "HISTORY")
    assert count.lacks == ("NO_CITED_EVIDENCE", "FEW_SENTENCES", "LOW_RETRIEVAL")


def test_a_group_no_one_asked_within_ninety_days_has_no_askers() -> None:
    count = gap_count([asked("reader-a", 120, ("HISTORY",), ("FEW_SENTENCES",))], now=NOW)
    assert (count.askers, count.last_asked, count.fields, count.lacks) == (0, None, (), ())


@pytest.mark.parametrize(
    ("askers", "days_ago", "priority"),
    [
        (5, 30, "HIGH"),
        (12, 3, "HIGH"),
        (5, 31, "MEDIUM"),
        (4, 0, "MEDIUM"),
        (2, 30, "MEDIUM"),
        (2, 31, "LOW"),
        (1, 0, "LOW"),
        (4, 60, "LOW"),
    ],
)
def test_priority_follows_how_many_asked_and_how_recently(askers: int, days_ago: int, priority: str) -> None:
    assert gap_priority(askers, NOW - timedelta(days=days_ago), now=NOW) == priority


def test_a_question_joins_the_nearest_group_within_the_distance() -> None:
    assert nearest_gap({GAP: 0.15, NEAR: 0.04}) == NEAR
    assert nearest_gap({GAP: 0.15}) == GAP
    assert nearest_gap({GAP: 0.151}) is None
    assert nearest_gap({}) is None


def hit(level: str, **ranks: int) -> ClaimHit:
    return ClaimHit(
        claim_id=uuid.uuid4(),
        text="A stored fact.",
        level=level,
        subject_type="CONCEPT",
        subject_id=ALUM,
        score=0.02,
        **ranks,
    )


def test_acceptance_counts_facts_the_retrieval_finds_by_the_question_s_words_or_names() -> None:
    hits = KnowledgeHits(
        craft_slug="Kutch-Ajrakh",
        claims=(
            hit("REVIEWED", lexical_rank=1, vector_rank=2),
            hit("PROVISIONAL", entity_rank=1),
            hit("VERIFIED", vector_rank=1),
            hit("HYPOTHESIS", lexical_rank=2, vector_rank=3),
        ),
    )
    assert found_facts(hits, by_meaning=False) == 2
    assert found_facts(hits, by_meaning=True) == 3


def test_a_gap_is_accepted_when_every_field_holds_two_found_facts() -> None:
    assert accepted({"CHEMISTRY": 2, "HISTORY": 5})
    assert not accepted({"CHEMISTRY": 2, "HISTORY": 1})
    assert not accepted({})


def test_a_gap_key_names_its_group_and_parses_as_an_open_work_key() -> None:
    detail = gap_detail(GAP)
    assert detail == "gap-0f0000000000400080000000000000aa"
    assert is_gap_detail(detail) and gap_id(detail) == GAP
    parsed = parse_task_key(f"ANSWER_GAP:craft:Kutch-Ajrakh:{detail}")
    assert (parsed.kind, parsed.subject_kind, parsed.slug, parsed.detail) == (
        "ANSWER_GAP",
        "craft",
        "Kutch-Ajrakh",
        detail,
    )
    assert gap_id("gap-123") is None and not is_gap_detail(f"gap-{GAP.hex.upper()}")
    with pytest.raises(InvalidInput):
        parse_task_key("ANSWER_GAP:craft:Kutch-Ajrakh:gap-123")


def test_the_new_kind_is_researched_as_a_field() -> None:
    assert TASK_KINDS[-1] == "ANSWER_GAP"
    assert TASK_PROMPTS["ANSWER_GAP"] == "research_field"


def test_the_site_parses_every_task_kind_and_offers_the_new_one_with_the_fact_tasks() -> None:
    source = (REPO / "frontend" / "lib" / "ownProposalsContract.ts").read_text(encoding="utf-8")
    kinds = re.search(r"export const TASK_KINDS = \[(.*?)\] as const;", source)
    facts = re.search(r"export const FACT_TASK_KINDS: readonly TaskKind\[\] = \[(.*?)\];", source)
    assert kinds is not None and facts is not None
    assert tuple(ast.literal_eval(f"[{kinds.group(1)}]")) == TASK_KINDS
    assert ast.literal_eval(f"[{facts.group(1)}]") == ["ANSWER_GAP", "MISSING_FIELD", "THIN_FIELD"]


def migration_tuples() -> dict[str, object]:
    tree = ast.parse(
        (REPO / "backend" / "migrations" / "versions" / "0055_answer_gaps.py").read_text("utf-8")
    )
    found: dict[str, object] = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Tuple):
            continue
        target = node.targets[0]
        if isinstance(target, ast.Name):
            found[target.id] = ast.literal_eval(node.value)
    return found


def test_the_migration_checks_the_values_the_models_hold() -> None:
    constants = migration_tuples()
    assert constants["ANSWER_VERDICTS"] == gap_rows.ANSWER_VERDICTS == ("ANSWERED", "THIN", "UNANSWERED")
    assert constants["GAP_STATES"] == gap_rows.GAP_STATES == ("OPEN", "ANSWERED", "LAPSED")
    assert constants["GAP_PRIORITIES"] == gap_rows.GAP_PRIORITIES
    assert constants["GAP_LACKS"] == gap_rows.GAP_LACKS
    assert constants["DISCIPLINES"] == DISCIPLINES
