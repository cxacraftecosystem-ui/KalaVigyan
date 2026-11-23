import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.page_refresh import PageRefreshState, cooldown_end
from app.research.review_labels import LABEL_MAX_CHARS, cut_label
from app.research.review_queue import QUEUE_KINDS
from app.research.staged_reviews import (
    MCP_QUEUE_KINDS,
    ConfirmedItem,
    StagedBatchList,
    StagedDecision,
    batch_expiry,
    batch_status,
    day_allowance_problem,
)

from ..contracts.golden import SHARED

NOW = datetime(2026, 11, 23, 9, tzinfo=UTC)
ITEM = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e21")
WHY = "Both quotes say this of the vat."


def golden(name: str) -> Any:
    return json.loads((SHARED / name).read_text(encoding="utf-8"))


def decision(**changes: Any) -> dict[str, Any]:
    return {"kind": "FACTS", "id": str(ITEM), "action": "approve", "reason": WHY} | changes


def test_the_goldens_are_what_the_api_serves_field_for_field() -> None:
    staged = golden("review.staged.golden.json")
    assert StagedBatchList.model_validate(staged).model_dump(mode="json") == staged
    refresh = golden("site.refresh.golden.json")
    assert PageRefreshState.model_validate(refresh).model_dump(mode="json") == refresh


def test_mcp_review_leaves_testimony_and_pictures_to_the_site() -> None:
    assert MCP_QUEUE_KINDS == ("FACTS", "COMPONENTS", "LAYOUTS", "STRUCTURE", "READINGS", "LAYERS", "STAGES")
    assert set(MCP_QUEUE_KINDS) == set(QUEUE_KINDS) - {"TESTIMONY", "IMAGES"}


@pytest.mark.parametrize(
    "refused",
    [
        decision(kind="COMPONENTS", action="raise"),
        decision(kind="SOURCES", action="approve"),
        decision(action="reject", craft="Kutch-Ajrakh"),
        decision(craft="Kutch-Ajrakh", family="Textiles"),
        decision(kind="SOURCES", action="correct"),
        decision(kind="SOURCES", action="correct", source={}),
        decision(source={"title": "Indigo vats and their chemistry"}),
        decision(reason="Too short."),
        decision(kind="TESTIMONY"),
    ],
)
def test_a_staged_decision_takes_only_what_the_review_page_allows(refused: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        StagedDecision.model_validate(refused)


def test_a_person_may_change_a_staged_decision_but_never_its_target() -> None:
    proposed = StagedDecision.model_validate(decision(action="reject"))
    choice = ConfirmedItem.model_validate(
        {"id": str(uuid.uuid4()), "action": "approve", "reason": WHY, "family": "Textiles"}
    )
    changed = proposed.changed_to(choice)
    assert (changed.kind, changed.id, changed.action, changed.family) == (
        "FACTS",
        ITEM,
        "approve",
        "Textiles",
    )
    with pytest.raises(ValidationError):
        ConfirmedItem.model_validate({"id": str(ITEM), "kind": "SOURCES", "action": "approve", "reason": WHY})
    fixed = StagedDecision.model_validate(
        decision(
            kind="SOURCES", action="correct", source={"containerTitle": "Journal of Environmental Biology"}
        )
    )
    assert fixed.source is not None and fixed.source.container_title == "Journal of Environmental Biology"


@pytest.mark.parametrize(
    ("today", "asked", "left"),
    [(0, 20, None), (80, 20, None), (99, 1, None), (99, 2, 1), (100, 1, 0), (0, 0, None), (120, 0, None)],
)
def test_an_admin_stages_at_most_a_hundred_items_a_day(today: int, asked: int, left: int | None) -> None:
    problem = day_allowance_problem(today, asked)
    if left is None:
        assert problem is None
    else:
        assert problem is not None and f"{left} are left" in problem and "100" in problem


def test_a_batch_expires_three_days_after_it_was_staged() -> None:
    expires = batch_expiry(NOW)
    assert expires == datetime(2026, 11, 26, 9, tzinfo=UTC)
    assert batch_status("OPEN", expires, now=expires - timedelta(seconds=1)) == "OPEN"
    assert batch_status("OPEN", expires, now=expires) == "EXPIRED"
    assert batch_status("CONFIRMED", expires, now=expires + timedelta(days=1)) == "CONFIRMED"


def test_a_cooldown_ends_at_its_length_after_the_last_start() -> None:
    assert cooldown_end(None, timedelta(minutes=10), now=NOW) is None
    assert cooldown_end(NOW - timedelta(minutes=4), timedelta(minutes=10), now=NOW) == NOW + timedelta(
        minutes=6
    )
    assert cooldown_end(NOW - timedelta(minutes=10), timedelta(minutes=10), now=NOW) is None


def test_a_label_is_one_line_of_at_most_three_hundred_characters() -> None:
    assert cut_label("An  indigo\nvat") == "An indigo vat"
    cut = cut_label("word " * 100)
    assert len(cut) == LABEL_MAX_CHARS and cut.endswith("…")
