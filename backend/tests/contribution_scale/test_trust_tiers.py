import uuid

import pytest

from app.research.trust_tiers import (
    ESTABLISHED,
    NEW,
    PROVEN,
    REVIEW_SAMPLE_PERCENT,
    TIER_FACTS_PER_HOUR,
    TIER_TASKS_HELD,
    TierRecord,
    drawn_for_review,
    earned_tier,
    tier_placement,
)


@pytest.mark.parametrize(
    ("accepted", "refused", "tier"),
    [
        (0, 0, NEW),
        (4, 0, NEW),
        (5, 0, ESTABLISHED),
        (6, 2, ESTABLISHED),
        (6, 3, NEW),
        (24, 0, ESTABLISHED),
        (25, 2, PROVEN),
        (25, 3, ESTABLISHED),
        (90, 10, PROVEN),
        (80, 30, NEW),
    ],
)
def test_an_account_s_tier_comes_from_its_accepted_and_refused_proposals(
    accepted: int, refused: int, tier: str
) -> None:
    assert earned_tier(TierRecord(accepted=accepted, refused=refused, waiting=7)) == tier


def test_waiting_proposals_never_raise_a_tier() -> None:
    assert earned_tier(TierRecord(accepted=0, refused=0, waiting=500)) == NEW


def test_the_caps_grow_with_the_tier_and_start_where_one_account_started() -> None:
    assert [TIER_TASKS_HELD[tier] for tier in (NEW, ESTABLISHED, PROVEN)] == [5, 10, 20]
    assert [TIER_FACTS_PER_HOUR[tier] for tier in (NEW, ESTABLISHED, PROVEN)] == [30, 60, 150]


def test_about_one_in_five_of_a_proven_contributor_s_facts_is_drawn_for_review() -> None:
    tokens = [uuid.uuid5(uuid.NAMESPACE_URL, f"sample/{number}") for number in range(2000)]
    drawn = sum(drawn_for_review(token) for token in tokens)
    assert REVIEW_SAMPLE_PERCENT == 20
    assert 340 <= drawn <= 460
    assert [drawn_for_review(token) for token in tokens[:50]] == [
        drawn_for_review(token) for token in tokens[:50]
    ]


@pytest.mark.parametrize(
    ("mode", "reviews", "tier", "drawn", "expected"),
    [
        ("APPROVAL", True, NEW, False, ("PUBLISHED", "APPROVED", True, False, "ROLE")),
        ("APPROVAL", False, PROVEN, False, ("PUBLISHED", "APPROVED", True, False, "TRUSTED")),
        ("APPROVAL", False, PROVEN, True, ("PUBLISHED", "IN_REVIEW", False, True, "DRAWN")),
        ("AUTO", False, NEW, False, ("WAITING", "DRAFT", False, True, "NEWCOMER")),
        ("APPROVAL", False, ESTABLISHED, False, ("WAITING", "DRAFT", False, True, "SWITCH")),
        ("AUTO", False, ESTABLISHED, True, ("PUBLISHED", "IN_REVIEW", False, True, "SWITCH")),
    ],
)
def test_proven_contributors_publish_new_ones_wait_and_the_switch_decides_between(
    mode: str, reviews: bool, tier: str, drawn: bool, expected: tuple[str, str, bool, bool, str]
) -> None:
    tiered = tier_placement(mode, proposer_reviews=reviews, tier=tier, drawn=drawn)
    placed = tiered.placed
    assert (placed.outcome, placed.status, placed.approved_at_once, placed.queued, tiered.why) == expected
