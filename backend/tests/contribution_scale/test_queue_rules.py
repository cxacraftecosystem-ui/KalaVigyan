import re
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

from app.core.rate_limit import FACT_PROPOSALS, SlidingWindow, proposal_slots
from app.models import User
from app.research.contribution_queue import (
    IDEMPOTENCY_KEY_PATTERN,
    content_key,
    proposal_fingerprint,
    retry_delay,
    stream_request_id,
    subject_key,
)
from app.research.knowledge_writes import FactProposal
from app.services.candidate_judge_routes import cheapest_judge_models

REQUEST_ID = re.compile(r"^[A-Za-z0-9._-]{8,64}$")
REPO = Path(__file__).resolve().parents[3]
BODY = {
    "subject": {"kind": "craft", "slug": "Kutch-Ajrakh"},
    "field": "PROCESS",
    "statement": "Ajrakh cloth is dipped in the indigo vat four times before it is washed.",
    "sources": [
        {"url": "https://example.org/a", "title": "A", "quotes": [{"text": "dipped in the vat four times"}]}
    ],
}


def person(role: str, number: int) -> User:
    return User(id=uuid.UUID(int=number), name=role, email=f"{number}@example.org", role=role)


def test_the_same_fact_has_the_same_fingerprint_and_a_changed_one_another() -> None:
    first = proposal_fingerprint(FactProposal.model_validate(BODY))
    again = proposal_fingerprint(FactProposal.model_validate({**BODY, "fields": []}))
    changed = proposal_fingerprint(
        FactProposal.model_validate({**BODY, "statement": BODY["statement"] + " Twice."})
    )
    assert first == again and first != changed and len(first) == 64
    key = content_key(first)
    assert key == "fact:" + first[:40] and re.fullmatch(IDEMPOTENCY_KEY_PATTERN, key)


def test_a_subject_key_folds_the_slug_s_case() -> None:
    proposal = FactProposal.model_validate({**BODY, "subject": {"kind": "craft", "slug": "KUTCH-Ajrakh"}})
    assert subject_key(proposal.subject) == "craft:kutch-ajrakh"


@pytest.mark.parametrize(
    ("attempts", "seconds"),
    [(1, 30), (2, 60), (3, 120), (4, 240), (5, 480), (6, 960), (7, 1800), (12, 1800)],
)
def test_a_failed_check_waits_twice_as_long_each_time_up_to_half_an_hour(attempts: int, seconds: int) -> None:
    assert retry_delay(attempts) == timedelta(seconds=seconds)


def test_every_model_call_of_a_proposal_carries_one_request_id_the_router_accepts() -> None:
    proposal_id = uuid.UUID("7c000000-0000-4000-8000-000000000001")
    tag = stream_request_id(proposal_id)
    assert tag == "contribution-7c000000000040008000000000000001"
    assert REQUEST_ID.fullmatch(tag)


def test_a_window_grants_what_is_left_and_says_when_the_oldest_slot_returns() -> None:
    window = SlidingWindow()
    assert window.take("k", 4, 6, 100.0, now=0.0) == (4, 0.0)
    assert window.take("k", 4, 6, 100.0, now=10.0) == (2, 90.0)
    assert window.take("k", 1, 6, 100.0, now=50.0) == (0, 50.0)
    assert window.take("k", 3, 6, 100.0, now=100.5) == (3, 0.0)


def test_a_batch_takes_its_slots_from_the_same_hourly_window_as_single_facts() -> None:
    researcher = person("RESEARCHER", 41)
    assert proposal_slots(FACT_PROPOSALS, researcher, 25)[0] == 25
    granted, wait = proposal_slots(FACT_PROPOSALS, researcher, 10)
    assert granted == 5 and 0 < wait <= 3600
    assert proposal_slots(FACT_PROPOSALS, researcher, 40, limit=60)[0] == 30
    assert proposal_slots(FACT_PROPOSALS, person("ADMIN", 42), 500) == (500, 0.0)


def test_the_cheap_judge_is_each_provider_s_least_priced_model_that_may_judge() -> None:
    assert dict(cheapest_judge_models()) == {
        "OPENAI": "gpt-6-luna",
        "GEMINI": "gemini-3.5-flash-lite",
        "ANTHROPIC": "claude-haiku-5-5",
    }


def test_the_worker_runs_on_the_box_beside_the_other_workers() -> None:
    unit = (REPO / "infra/deploy/units/kv-contributions.service").read_text(encoding="utf-8")
    assert "python -m app.scripts.contribution_worker --concurrency" in unit
    assert (REPO / "backend/app/scripts/contribution_worker.py").is_file()
    switch = (REPO / "infra/deploy/blue_green.sh").read_text(encoding="utf-8")
    assert re.search(r"^WORKERS=\(.*\bkv-contributions\b.*\)$", switch, re.MULTILINE)
