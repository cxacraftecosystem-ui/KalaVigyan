from __future__ import annotations

import uuid

from app.services.sources_differ import HeldScope, live_pair

CRAFT, OTHER_CRAFT, FAMILY = uuid.UUID(int=1), uuid.UUID(int=2), uuid.UUID(int=3)


def on_craft(status: str, craft: uuid.UUID = CRAFT) -> HeldScope:
    return HeldScope(status, craft, FAMILY)


def on_family(status: str) -> HeldScope:
    return HeldScope(status, None, FAMILY)


def shared(status: str) -> HeldScope:
    return HeldScope(status, None, None)


def test_a_live_fact_and_a_waiting_fact_of_one_craft_differ_live() -> None:
    assert live_pair(on_craft("IN_REVIEW"), on_craft("DRAFT")) is True


def test_two_waiting_facts_do_not_differ_live_until_one_is_shown() -> None:
    assert live_pair(on_craft("DRAFT"), on_craft("DRAFT")) is False


def test_a_retracted_rejected_or_superseded_fact_differs_from_nothing() -> None:
    closed = ("RETRACTED", "REJECTED", "SUPERSEDED")
    assert [live_pair(on_craft("APPROVED"), on_craft(status)) for status in closed] == [False, False, False]


def test_facts_filed_under_two_crafts_do_not_differ_live() -> None:
    assert live_pair(on_craft("APPROVED"), on_craft("APPROVED", OTHER_CRAFT)) is False


def test_a_craft_s_fact_differs_live_from_its_family_s_fact_but_not_from_a_shared_one() -> None:
    assert (
        live_pair(on_craft("APPROVED"), on_family("APPROVED")),
        live_pair(shared("APPROVED"), on_craft("APPROVED")),
        live_pair(shared("APPROVED"), shared("PROPOSED")),
    ) == (True, False, True)
