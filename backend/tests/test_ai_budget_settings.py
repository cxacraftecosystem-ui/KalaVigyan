from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.core.roles import ROLE_RANK
from app.providers import spend_settings
from app.schemas.admin import AppSettingsUpdate
from app.services import app_settings

from .ai_caps import CAPS_AN_OWNER_MIGHT_SET, ceilings, unlimited


def test_the_defaults_cap_nothing() -> None:
    c = unlimited()
    assert (c.monthly_usd, c.media_usd, c.degrade_at) == (None, None, None)
    assert c.role_daily_usd == dict.fromkeys(ROLE_RANK)
    assert c.answer_usd == {"BASIC": None, "DETAILED": None, "EXPERT": None}
    view = app_settings.public_view(dict(app_settings.DEFAULTS))
    assert (view["monthlyCeilingUsd"], view["mediaCapUsd"], view["degradeAtFraction"]) == (None, None, None)
    assert view["roleDailyUsd"] == dict.fromkeys(ROLE_RANK)
    assert view["answerCapUsd"] == {"BASIC": None, "DETAILED": None, "EXPERT": None}


def test_the_answer_caps_per_depth_are_ai_budget_settings() -> None:
    assert ceilings().answer_usd == {
        "BASIC": Decimal("0.25"),
        "DETAILED": Decimal("1"),
        "EXPERT": Decimal("2.5"),
    }
    view = app_settings.public_view({**app_settings.DEFAULTS, **CAPS_AN_OWNER_MIGHT_SET})
    assert view["answerCapUsd"] == {"BASIC": 0.25, "DETAILED": 1.0, "EXPERT": 2.5}


def test_budget_changes_merge_answer_caps_by_depth() -> None:
    current = {**app_settings.DEFAULTS, **CAPS_AN_OWNER_MIGHT_SET}
    changes = app_settings.budget_changes({"answerCapUsd": {"EXPERT": 3.0}}, current)
    assert changes == {app_settings.ANSWER_CAP_USD: {"BASIC": 0.25, "DETAILED": 1.0, "EXPERT": 3.0}}
    lifted = app_settings.budget_changes({"answerCapUsd": {"BASIC": None}}, current)
    assert lifted == {app_settings.ANSWER_CAP_USD: {"BASIC": None, "DETAILED": 1.0, "EXPERT": 2.5}}


def test_a_cap_can_return_as_a_setting_and_be_lifted_again() -> None:
    current = dict(app_settings.DEFAULTS)
    assert app_settings.budget_changes({"monthlyCeilingUsd": 500.0, "mediaCapUsd": 50.0}, current) == {
        app_settings.MONTHLY_CEILING_USD: 500.0,
        app_settings.MEDIA_CAP_USD: 50.0,
    }
    assert app_settings.budget_changes({"monthlyCeilingUsd": None, "degradeAtFraction": None}, current) == {
        app_settings.MONTHLY_CEILING_USD: None,
        app_settings.DEGRADE_AT_FRACTION: None,
    }


def test_budget_changes_refuse_a_master_admin_cap() -> None:
    current = dict(app_settings.DEFAULTS)
    with pytest.raises(InvalidInput, match="Master Admins have no caps"):
        app_settings.budget_changes({"roleDailyUsd": {"MASTER_ADMIN": 5.0}}, current)
    allowed = app_settings.budget_changes({"roleDailyUsd": {"MASTER_ADMIN": None, "ADMIN": 12.0}}, current)
    assert allowed == {app_settings.ROLE_DAILY_USD: {**dict.fromkeys(ROLE_RANK), "ADMIN": 12.0}}


def test_a_student_cap_set_alone_leaves_every_other_role_uncapped() -> None:
    current = dict(app_settings.DEFAULTS)
    changes = app_settings.budget_changes({"roleDailyUsd": {"STUDENT": 0.5}}, current)
    assert changes == {app_settings.ROLE_DAILY_USD: {**dict.fromkeys(ROLE_RANK), "STUDENT": 0.5}}
    capped = unlimited(**changes)
    assert capped.role_cap("STUDENT") == Decimal("0.5")
    for role in set(ROLE_RANK) - {"STUDENT"}:
        assert capped.role_cap(role) is None, role


def test_a_role_cap_update_merges_with_the_caps_already_set() -> None:
    current = {**app_settings.DEFAULTS, **CAPS_AN_OWNER_MIGHT_SET}
    changes = app_settings.budget_changes({"roleDailyUsd": {"RESEARCHER": None}}, current)
    assert changes == {
        app_settings.ROLE_DAILY_USD: {
            **CAPS_AN_OWNER_MIGHT_SET[app_settings.ROLE_DAILY_USD],
            "RESEARCHER": None,
        }
    }


def test_budget_changes_refuse_unknown_roles_and_a_media_cap_over_the_ceiling() -> None:
    current = {**app_settings.DEFAULTS, **CAPS_AN_OWNER_MIGHT_SET}
    with pytest.raises(InvalidInput, match="Unknown roles: GUEST"):
        app_settings.budget_changes({"roleDailyUsd": {"GUEST": 1.0}}, current)
    with pytest.raises(InvalidInput, match="media cap"):
        app_settings.budget_changes({"monthlyCeilingUsd": 100.0}, current)
    assert app_settings.budget_changes({"mediaCapUsd": 5000.0}, dict(app_settings.DEFAULTS)) == {
        app_settings.MEDIA_CAP_USD: 5000.0
    }
    assert app_settings.budget_changes({"domainAllowlist": [" IITB.ac.in", "iitb.ac.in", " "]}, current) == {
        app_settings.DOMAIN_ALLOWLIST: ["iitb.ac.in"]
    }


def test_a_sent_null_lifts_a_cap_and_an_unsent_field_changes_nothing() -> None:
    body = AppSettingsUpdate.model_validate(
        {"monthlyCeilingUsd": None, "signUpMode": None, "mediaCapUsd": 20}
    )
    sent = app_settings.sent_budget_fields(body.model_dump(), body.model_fields_set)
    assert sent == {"mediaCapUsd": 20.0, "monthlyCeilingUsd": None}


def test_the_budget_update_body_takes_answer_caps_for_the_three_depths_only() -> None:
    assert AppSettingsUpdate(answerCapUsd={"BASIC": 0.1}).answerCapUsd == {"BASIC": 0.1}
    assert AppSettingsUpdate(answerCapUsd={"EXPERT": None}).answerCapUsd == {"EXPERT": None}
    with pytest.raises(ValidationError):
        AppSettingsUpdate(answerCapUsd={"DEEP": 0.1})
    with pytest.raises(ValidationError):
        AppSettingsUpdate(answerCapUsd={"EXPERT": -1})


def test_a_role_left_out_of_a_stored_cap_map_reads_its_own_default() -> None:
    saved_before_two_roles = {"STUDENT": 0.5, "RESEARCHER": 3.0}
    assert spend_settings.stored_spend_value(app_settings.ROLE_DAILY_USD, saved_before_two_roles) == {
        "MASTER_ADMIN": None,
        "ADMIN": None,
        "PROFESSOR": None,
        "RESEARCHER": 3.0,
        "ARTISAN": None,
        "STUDENT": 0.5,
    }
    assert spend_settings.stored_spend_value(app_settings.MONTHLY_CEILING_USD, 800.0) == 800.0
    capped = unlimited(**{app_settings.ROLE_DAILY_USD: saved_before_two_roles})
    assert (capped.role_cap("STUDENT"), capped.role_cap("RESEARCHER")) == (Decimal("0.5"), Decimal("3"))
    assert (capped.role_cap("ARTISAN"), capped.role_cap("ADMIN"), capped.role_cap("PROFESSOR")) == (
        None,
        None,
        None,
    )


def test_a_partial_role_cap_update_over_an_old_stored_map_names_every_role() -> None:
    stored = spend_settings.stored_spend_value(app_settings.ROLE_DAILY_USD, {"STUDENT": 0.5})
    current = {**app_settings.DEFAULTS, app_settings.ROLE_DAILY_USD: stored}
    changes = app_settings.budget_changes({"roleDailyUsd": {"PROFESSOR": 2.0}}, current)
    assert changes == {
        app_settings.ROLE_DAILY_USD: {**dict.fromkeys(ROLE_RANK), "STUDENT": 0.5, "PROFESSOR": 2.0}
    }
