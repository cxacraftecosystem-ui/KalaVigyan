from types import SimpleNamespace
from typing import Any

import pytest

from app.core.config import get_settings
from app.services import access_guards

NONE = {"update": False, "suspend": False, "admit": False, "refuse": False}


def person(role: str) -> Any:
    return SimpleNamespace(role=role)


def entry(admit_role: str | None, status: str, email: str = "entry@example.org") -> Any:
    return SimpleNamespace(email=email, admitRole=admit_role, status=status)


@pytest.mark.parametrize(
    ("viewer", "admit_role", "status", "offers"),
    [
        ("ADMIN", "ADMIN", "ACTIVE", NONE),
        ("ADMIN", "MASTER_ADMIN", "ACTIVE", NONE),
        ("ADMIN", "PROFESSOR", "ACTIVE", {"update": True, "suspend": True, "admit": False, "refuse": False}),
        (
            "ADMIN",
            "PROFESSOR",
            "SUSPENDED",
            {"update": True, "suspend": False, "admit": True, "refuse": False},
        ),
        ("ADMIN", None, "PENDING", {"update": True, "suspend": False, "admit": True, "refuse": True}),
        (
            "PROFESSOR",
            "STUDENT",
            "SUSPENDED",
            {"update": True, "suspend": False, "admit": False, "refuse": False},
        ),
        ("PROFESSOR", "PROFESSOR", "ACTIVE", NONE),
        (
            "MASTER_ADMIN",
            "ADMIN",
            "ACTIVE",
            {"update": True, "suspend": True, "admit": False, "refuse": False},
        ),
    ],
)
def test_an_entry_offers_what_the_routes_allow_by_its_role(
    viewer: str, admit_role: str | None, status: str, offers: dict[str, bool]
) -> None:
    assert access_guards.entry_offers(person(viewer), entry(admit_role, status), None) == offers


def test_an_entry_whose_account_ranks_at_or_above_the_viewer_offers_nothing() -> None:
    row = entry("PROFESSOR", "ACTIVE")
    assert access_guards.entry_offers(person("ADMIN"), row, person("ADMIN")) == NONE
    assert access_guards.bar_refusal(person("ADMIN"), row, person("ADMIN")) == (
        "You can't change access for an account at or above your role."
    )
    pending = entry(None, "PENDING")
    assert access_guards.entry_offers(person("PROFESSOR"), pending, person("PROFESSOR")) == NONE
    assert access_guards.entry_offers(person("ADMIN"), row, person("PROFESSOR")) == {
        "update": True,
        "suspend": True,
        "admit": False,
        "refuse": False,
    }


def test_the_master_admin_entry_is_never_barred_but_its_owner_may_correct_it() -> None:
    row = entry("MASTER_ADMIN", "ACTIVE", email=get_settings().master_admin_email.upper())
    assert access_guards.bar_refusal(person("MASTER_ADMIN"), row, None) == (
        "The master admin's access can't be withdrawn."
    )
    assert (
        access_guards.change_refusal(person("ADMIN"), row, None)
        == "The master admin's access can't be changed."
    )
    assert access_guards.entry_offers(person("MASTER_ADMIN"), row, None) == {
        "update": True,
        "suspend": False,
        "admit": False,
        "refuse": False,
    }


def test_only_an_admin_restores_a_barred_entry() -> None:
    barred = entry("STUDENT", "REJECTED")
    assert access_guards.reinstate_refusal(person("PROFESSOR"), barred, None) == (
        "Only admins can restore access that was suspended or refused."
    )
    assert access_guards.reinstate_refusal(person("ADMIN"), barred, None) is None
