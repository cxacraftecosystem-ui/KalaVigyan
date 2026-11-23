import uuid
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

import app.research.review_queue as contract
from app.core.errors import InvalidInput
from app.core.roles import Capability
from app.research.component_proposals import ComponentProposalDraft
from app.research.knowledge_api import ComponentSummary
from app.research.review_queue import (
    APPROVE,
    COMPONENTS,
    FACTS,
    IMAGES,
    LAYOUTS,
    RAISE,
    REJECT,
    RETRACT,
    STAGES,
    STRUCTURE,
    TESTIMONY,
    FactRetraction,
    QueueApproval,
    QueueEntry,
    QueueKey,
    QueueRejection,
    ReviewFilters,
    cursor_text,
    decision_capability,
    fact_move_problem,
    fact_origin,
    newest_first,
    parsed_cursor,
    reviewed_kinds,
    sees_proposer,
    selected_kinds,
)
from app.research.review_queue_components import closest_components
from app.services.claim_writer import HELD_NOTE, held_note
from app.services.write_back_crafts import HELD_OTHER_PLACE

ALL_KINDS = ("FACTS", "TESTIMONY", "IMAGES", "COMPONENTS", "LAYOUTS", "STRUCTURE", "STAGES")
NOON = datetime(2026, 11, 19, 12, 0, 0, 123456, tzinfo=UTC)


@pytest.mark.parametrize(
    ("role", "kinds"),
    [
        ("STUDENT", ()),
        ("ARTISAN", ()),
        ("RESEARCHER", ()),
        ("PROFESSOR", ("FACTS", "TESTIMONY", "STRUCTURE", "STAGES")),
        ("ADMIN", ALL_KINDS),
        ("MASTER_ADMIN", ALL_KINDS),
    ],
)
def test_each_role_reviews_the_kinds_its_capabilities_name(role: str, kinds: tuple[str, ...]) -> None:
    assert reviewed_kinds(role) == kinds


@pytest.mark.parametrize(("role", "shown"), [("PROFESSOR", False), ("ADMIN", True), ("MASTER_ADMIN", True)])
def test_only_admins_and_master_admins_see_who_proposed(role: str, shown: bool) -> None:
    assert sees_proposer(role) is shown


@pytest.mark.parametrize(
    ("origin", "kinds"),
    [
        ("RESEARCH", ("FACTS", "STAGES")),
        ("CONTRIBUTION", ("FACTS", "IMAGES", "LAYOUTS", "STRUCTURE")),
        ("AGENT", ("FACTS", "COMPONENTS", "LAYOUTS", "STRUCTURE")),
        ("TESTIMONY", ("TESTIMONY",)),
        (None, ALL_KINDS),
    ],
)
def test_an_origin_keeps_only_the_kinds_that_arrive_by_it(origin: str | None, kinds: tuple[str, ...]) -> None:
    assert selected_kinds(ALL_KINDS, kind=None, origin=origin) == kinds


def test_a_kind_filter_never_reaches_past_the_viewers_kinds() -> None:
    assert selected_kinds(("FACTS", "TESTIMONY"), kind="IMAGES", origin=None) == ()
    assert selected_kinds(ALL_KINDS, kind="IMAGES", origin="AGENT") == ()
    assert selected_kinds(ALL_KINDS, kind="COMPONENTS", origin="AGENT") == ("COMPONENTS",)


@pytest.mark.parametrize(
    ("kind", "action", "capability"),
    [
        (FACTS, APPROVE, Capability.MARK_CLAIM_LEVEL),
        (FACTS, REJECT, Capability.MARK_CLAIM_LEVEL),
        (FACTS, RAISE, Capability.MARK_CLAIM_LEVEL),
        (FACTS, RETRACT, Capability.RETRACT_CLAIM),
        (TESTIMONY, APPROVE, Capability.REVIEW_TESTIMONY),
        (IMAGES, REJECT, Capability.REVIEW_CONTRIBUTIONS),
        (COMPONENTS, APPROVE, Capability.REVIEW_CONTRIBUTIONS),
        (LAYOUTS, APPROVE, Capability.REVIEW_CONTRIBUTIONS),
        (LAYOUTS, REJECT, Capability.REVIEW_CONTRIBUTIONS),
        (STRUCTURE, APPROVE, Capability.MARK_CLAIM_LEVEL),
        (STRUCTURE, REJECT, Capability.MARK_CLAIM_LEVEL),
        (STAGES, APPROVE, Capability.MARK_CLAIM_LEVEL),
        (STAGES, REJECT, Capability.MARK_CLAIM_LEVEL),
    ],
)
def test_each_decision_needs_its_kinds_capability(kind: str, action: str, capability: Capability) -> None:
    assert decision_capability(kind, action) == capability


@pytest.mark.parametrize(
    ("kind", "action"),
    [
        (IMAGES, RAISE),
        (TESTIMONY, RETRACT),
        (COMPONENTS, RAISE),
        (LAYOUTS, RETRACT),
        (STRUCTURE, RAISE),
        (STAGES, RAISE),
    ],
)
def test_only_a_fact_is_raised_or_retracted(kind: str, action: str) -> None:
    with pytest.raises(InvalidInput):
        decision_capability(kind, action)


@pytest.mark.parametrize(
    ("action", "status", "level", "problem"),
    [
        (APPROVE, "DRAFT", "PROVISIONAL", None),
        (APPROVE, "IN_REVIEW", "PROVISIONAL", None),
        (APPROVE, "APPROVED", "PROVISIONAL", "A fact that is approved cannot be approved."),
        (REJECT, "IN_REVIEW", "PROVISIONAL", None),
        (REJECT, "REJECTED", "PROVISIONAL", "A fact that is rejected cannot be rejected."),
        (RAISE, "APPROVED", "PROVISIONAL", None),
        (RAISE, "DRAFT", "PROVISIONAL", None),
        (
            RAISE,
            "IN_REVIEW",
            "HYPOTHESIS",
            "Only a quoted fact at provisional can be raised; this one is hypothesis.",
        ),
        (
            RAISE,
            "APPROVED",
            "REVIEWED",
            "Only a quoted fact at provisional can be raised; this one is reviewed.",
        ),
        (RETRACT, "APPROVED", "REVIEWED", None),
        (RETRACT, "IN_REVIEW", "PROVISIONAL", None),
        (RETRACT, "DRAFT", "PROVISIONAL", "A fact that is draft cannot be retracted."),
    ],
)
def test_a_fact_moves_only_from_the_statuses_its_decision_names(
    action: str, status: str, level: str, problem: str | None
) -> None:
    assert fact_move_problem(action, status, level) == problem


@pytest.mark.parametrize(
    ("claim_origin", "found_by", "origin"),
    [
        ("LIVE_RESEARCH", {"ANSWER"}, "RESEARCH"),
        ("LIVE_RESEARCH", {"BACKGROUND"}, "RESEARCH"),
        ("RESEARCHER", {"AGENT"}, "AGENT"),
        ("RESEARCHER", {"CONTRIBUTION"}, "CONTRIBUTION"),
        ("RESEARCHER", set(), "CONTRIBUTION"),
    ],
)
def test_a_facts_origin_follows_its_writer_and_its_sources(
    claim_origin: str, found_by: set[str], origin: str
) -> None:
    assert fact_origin(claim_origin, found_by) == origin


def test_a_cursor_names_the_microsecond_and_the_item() -> None:
    key = QueueKey(NOON, uuid.UUID(int=5))
    text = cursor_text(key)
    assert text == "1795089600123456~00000000000000000000000000000005"
    assert parsed_cursor(text) == key


@pytest.mark.parametrize("text", ["abc", "123~xyz", "1~" + "g" * 32, "~" + "0" * 32, "12-" + "0" * 32])
def test_a_malformed_cursor_is_refused(text: str) -> None:
    with pytest.raises(InvalidInput):
        parsed_cursor(text)


def _entry(second: int, item: int, kind: str) -> QueueEntry:
    return QueueEntry(QueueKey(datetime(2026, 11, 19, 12, 0, second, tzinfo=UTC), uuid.UUID(int=item)), kind)


def test_the_page_is_newest_first_across_kinds_and_names_where_to_go_on() -> None:
    facts = [_entry(50, 1, FACTS), _entry(10, 2, FACTS)]
    pictures = [_entry(40, 3, IMAGES), _entry(40, 4, IMAGES)]
    testimony = [_entry(30, 5, TESTIMONY)]
    kept, following = newest_first([facts, pictures, testimony], 3)
    assert [entry.key.item_id.int for entry in kept] == [1, 4, 3]
    assert following == cursor_text(QueueKey(datetime(2026, 11, 19, 12, 0, 40, tzinfo=UTC), uuid.UUID(int=3)))


def test_a_page_that_holds_everything_names_no_next_page() -> None:
    kept, following = newest_first([[_entry(5, 1, FACTS)], [_entry(9, 2, COMPONENTS)]], 2)
    assert ([entry.kind for entry in kept], following) == ([COMPONENTS, FACTS], None)


def _summary(label: str, kind: str, title: str, description: str) -> ComponentSummary:
    return ComponentSummary.model_validate(
        {
            "label": label,
            "title": title,
            "description": description,
            "kind": kind,
            "field": "CHEMISTRY",
            "fields": [],
            "craftSlug": None,
            "subjects": [],
        }
    )


DRAFT: dict[str, Any] = {
    "label": "kutch-ajrakh/chemistry/mordant-bath",
    "title": "Alum mordant bath",
    "description": "How alum binds madder dye to cotton fibre in the mordant bath of ajrakh printing.",
    "kind": "mordant_bath",
    "field": "CHEMISTRY",
    "subjects": [{"kind": "CRAFT", "key": "Kutch-Ajrakh"}],
    "extends": "shared/chemistry/old-bath",
    "extension": "VARIANT",
}


def test_the_closest_components_lead_with_the_most_reasons_then_the_most_shared_words() -> None:
    draft = ComponentProposalDraft.model_validate(DRAFT)
    same_label = _summary(DRAFT["label"], "images", "Mordant pictures", "Photographs of cloth.")
    near = _summary(
        "shared/chemistry/alum-mordant",
        "mordant_bath",
        "Alum mordant bath player",
        "Alum binds madder dye to cotton.",
    )
    far = _summary(
        "shared/geography/kachchh-map", "map_layer", "Kachchh districts", "A map of the districts of Kachchh."
    )
    extended = _summary(
        "shared/chemistry/old-bath", "mordant_bath", "Alum mordant bath", DRAFT["description"]
    )
    found = closest_components(draft, [far, same_label, extended, near, far])
    assert [match.component.label for match in found] == [near.label, same_label.label, far.label]
    assert [match.overlap for match in found] == [0.7, 0.077, 0.0]
    assert [len(match.reasons) for match in found] == [2, 1, 0]
    assert found[1].reasons == ["it already has this label"]
    assert [match.component.label for match in closest_components(draft, [far, near], limit=1)] == [
        near.label
    ]


@pytest.mark.parametrize("reason", ["no", "x" * 501])
def test_a_rejection_or_retraction_needs_a_reason_of_three_to_five_hundred_characters(reason: str) -> None:
    with pytest.raises(ValidationError):
        QueueRejection.model_validate({"reason": reason})
    with pytest.raises(ValidationError):
        FactRetraction.model_validate({"reason": reason})


def test_a_rejection_names_its_reason_in_words_unless_testimony_gives_its_reason() -> None:
    with pytest.raises(ValidationError, match="in words, or a testimony reason"):
        QueueRejection.model_validate({})
    misheard = QueueRejection.model_validate({"testimonyReason": "MISHEARD", "version": 2})
    assert (misheard.reason, misheard.testimony_reason) == (None, "MISHEARD")
    with pytest.raises(InvalidInput, match="reason in words"):
        misheard.stated()
    assert QueueRejection.model_validate({"reason": "Blurred."}).stated() == "Blurred."


def test_a_testimony_approval_names_at_most_five_corroborating_facts() -> None:
    five = [str(uuid.UUID(int=n)) for n in range(1, 6)]
    assert len(QueueApproval.model_validate({"corroboratingClaimIds": five}).corroborating_claim_ids) == 5
    with pytest.raises(ValidationError):
        QueueApproval.model_validate({"corroboratingClaimIds": [*five, str(uuid.UUID(int=6))]})


def test_a_reason_at_the_limits_is_kept() -> None:
    assert QueueRejection.model_validate({"reason": "abc"}).reason == "abc"
    assert FactRetraction.model_validate({"reason": "y" * 500}).reason == "y" * 500


@pytest.mark.parametrize("limit", [0, 51])
def test_a_page_holds_one_to_fifty_items(limit: int) -> None:
    with pytest.raises(ValidationError):
        ReviewFilters(limit=limit)


def test_each_item_names_its_kind_by_the_queue_it_belongs_to() -> None:
    kinds = [
        model.model_fields["kind"].default
        for model in (
            contract.FactItem,
            contract.TestimonyItem,
            contract.PictureItem,
            contract.ComponentItem,
            contract.LayoutItem,
            contract.StructureQueueItem,
            contract.StageQueueItem,
        )
    ]
    assert kinds == list(ALL_KINDS)


def test_an_approval_that_files_a_fact_elsewhere_also_moves_an_approved_fact() -> None:
    assert fact_move_problem(APPROVE, "APPROVED", "PROVISIONAL", refiled=True) is None
    assert fact_move_problem(APPROVE, "IN_REVIEW", "PROVISIONAL", refiled=True) is None
    assert (
        fact_move_problem(APPROVE, "APPROVED", "PROVISIONAL") == "A fact that is approved cannot be approved."
    )
    assert fact_move_problem(APPROVE, "RETRACTED", "PROVISIONAL", refiled=True) == (
        "A fact that is retracted cannot be approved."
    )
    assert QueueApproval(family="Mud-Based-Craft-Category").filed_under == "Mud-Based-Craft-Category"
    assert QueueApproval(craft="Khurja-Pottery").filed_under == "Khurja-Pottery"
    assert QueueApproval().filed_under is None


def test_a_held_write_back_s_note_gives_its_reason_and_suggested_craft() -> None:
    reason = HELD_OTHER_PLACE.format(places="Afghanistan")
    note = "ANSWER write-back, answer 1" + HELD_NOTE.format(reason=reason, craft="Ajanta-Painting")
    assert held_note(note) == (reason, "Ajanta-Painting")
    assert held_note("ANSWER write-back, answer 1") is None
    assert held_note(None) is None
