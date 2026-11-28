import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from pydantic import ValidationError

from app.api.mcp_page_arguments import bundle_parts
from app.core.errors import InvalidInput
from app.research.component_proposals import ComponentProposalDraft, close_matches
from app.research.knowledge_api import ComponentSummary
from app.research.own_proposals import ComponentProposalBody
from app.research.page_drafts import (
    DraftAddition,
    DraftParts,
    draft_bundle,
    part_summaries,
    with_added,
    without,
)
from app.research.page_holds import HoldDecision, hold_expiry, hold_state
from app.research.page_layout import PageLayoutEntry
from app.research.page_proposals import PageBundle, PageSubject
from app.research.staged_reviews import STAGED_KIND_ACTIONS, ConfirmedItem, StagedDecision
from app.services.component_layout_swaps import swapped_entries

from .test_page_proposals import COMPONENT, SUBJECT

OLD = "kutch-ajrakh/history/plain-timeline"
NEW = "kutch-ajrakh/history/dated-timeline"
WHY = "It cites only Ajrakh's facts on this page."
PIECE = uuid.UUID("6f1c2a4e-8d3b-4c5a-9e7f-0a1b2c3d4e31")
NOW = datetime(2026, 11, 24, 9, tzinfo=UTC)


def draft(**changes: Any) -> ComponentProposalDraft:
    return ComponentProposalBody.model_validate(COMPONENT | changes)


def summary(label: str) -> ComponentSummary:
    return ComponentSummary(
        label=label,
        title=COMPONENT["title"],
        description=COMPONENT["description"],
        kind=COMPONENT["kind"],
        field="CHEMISTRY",
        fields=[],
        craft_slug="Kutch-Ajrakh",
        subjects=[],
    )


def removal(**changes: Any) -> dict[str, Any]:
    return {"kind": "COMPONENTS", "id": str(PIECE), "action": "remove", "reason": WHY} | changes


def entry(ref: str, order: int) -> PageLayoutEntry:
    role = "FIGURE" if "/" in ref else "BODY"
    return PageLayoutEntry(ref=ref, chapter="history", order=order, role=role)


def test_a_replacement_takes_a_label_of_its_own_and_is_never_a_link() -> None:
    assert draft(replaces=OLD).replaces == OLD
    with pytest.raises(ValidationError, match="a replacement takes a label of its own"):
        draft(replaces=COMPONENT["label"])
    with pytest.raises(ValidationError, match="never a SUBJECT_LINK"):
        draft(replaces=OLD, extends=COMPONENT["label"], extension="SUBJECT_LINK", spec=None, units={})


def test_the_component_a_proposal_replaces_is_never_its_close_match() -> None:
    same = [summary(OLD)]
    assert [match.component.label for match in close_matches(draft(), same, {})] == [OLD]
    assert close_matches(draft(replaces=OLD), same, {}) == []


def test_a_bundle_may_hold_withdrawals_alone_each_once_and_counts_them_as_parts() -> None:
    alone = PageBundle.model_validate({"subject": SUBJECT, "withdrawals": [{"label": OLD, "reason": WHY}]})
    assert [withdrawal.label for withdrawal in alone.withdrawals] == [OLD] and bundle_parts(alone) == 1
    with pytest.raises(ValidationError, match="withdraws each component once"):
        PageBundle.model_validate({"subject": SUBJECT, "withdrawals": [{"label": OLD}, {"label": OLD}]})
    plain = PageBundle.model_validate({"subject": SUBJECT, "components": [{"proposal": COMPONENT}]})
    assert "withdrawals" not in plain.model_dump() and bundle_parts(plain) == 1


def test_a_draft_keeps_one_withdrawal_a_label_lists_it_and_carries_it_into_the_bundle() -> None:
    held = with_added(DraftParts(), DraftAddition.model_validate({"withdrawals": [{"label": OLD}]}))
    again = with_added(held, DraftAddition.model_validate({"withdrawals": [{"label": OLD, "reason": WHY}]}))
    assert [(gone.label, gone.reason) for gone in again.withdrawals] == [(OLD, WHY)]
    assert [(part.part, part.summary) for part in part_summaries(again)] == [
        ("withdrawal", f"withdraw {OLD}")
    ]
    bundle = draft_bundle(PageSubject(kind="craft", slug="Kutch-Ajrakh"), again)
    assert [withdrawal.label for withdrawal in bundle.withdrawals] == [OLD]
    assert without(again, "withdrawal", 0).withdrawals == []


def test_a_replacement_takes_the_old_component_s_place_in_a_layout() -> None:
    laid = [entry("u0001", 1), entry(OLD, 2), entry("u0002", 3)]
    swapped = swapped_entries(laid, OLD, NEW)
    assert [(e.ref, e.chapter, e.order, e.role) for e in swapped] == [
        ("u0001", "history", 1, "BODY"),
        (NEW, "history", 2, "FIGURE"),
        ("u0002", "history", 3, "BODY"),
    ]
    assert [e.ref for e in swapped_entries([*laid, entry(NEW, 4)], OLD, NEW)] == ["u0001", "u0002", NEW]


def test_a_held_page_waits_three_days_then_expires_unconfirmed() -> None:
    expires = hold_expiry(NOW)
    assert expires == NOW + timedelta(days=3)
    assert hold_state("WAITING", expires, now=expires - timedelta(seconds=1)) == "WAITING"
    assert hold_state("WAITING", expires, now=expires) == "EXPIRED"
    assert hold_state("CONFIRMED", expires, now=expires + timedelta(days=1)) == "CONFIRMED"
    assert HoldDecision.model_validate({"decision": "DISCARD"}).decision == "DISCARD"
    with pytest.raises(ValidationError):
        HoldDecision.model_validate({"decision": "PUBLISH"})


def test_a_component_removal_names_at_most_one_page_and_no_other_removal_names_one() -> None:
    assert STAGED_KIND_ACTIONS["COMPONENTS"] == ("approve", "reject", "remove", "edit")
    assert StagedDecision.model_validate(removal()).craft is None
    assert StagedDecision.model_validate(removal(craft="Sanganeri-Hand-Block-Printing")).family is None
    for refused in (
        removal(kind="LAYOUTS", craft="Bagh-Print"),
        removal(craft="Bagh-Print", family="Textiles"),
    ):
        with pytest.raises(ValidationError):
            StagedDecision.model_validate(refused)
    with pytest.raises(ValidationError, match="Only an approved fact is filed"):
        StagedDecision.model_validate(removal(action="approve", craft="Bagh-Print"))


def test_a_person_may_change_a_removal_s_reason_and_page_but_never_turn_it_into_a_queue_decision() -> None:
    proposed = StagedDecision.model_validate(removal())
    narrowed = proposed.changed_to(
        ConfirmedItem.model_validate(
            {"id": str(uuid.uuid4()), "action": "remove", "reason": WHY, "craft": "Bagh-Print"}
        )
    )
    assert (narrowed.kind, narrowed.id, narrowed.action, narrowed.craft) == (
        "COMPONENTS",
        PIECE,
        "remove",
        "Bagh-Print",
    )
    approval = ConfirmedItem.model_validate({"id": str(PIECE), "action": "approve", "reason": WHY})
    with pytest.raises(InvalidInput, match="stays one"):
        proposed.changed_to(approval)
