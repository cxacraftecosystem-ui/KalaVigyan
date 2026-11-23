import json
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.auth_session import role_for_email
from app.core.config import get_settings
from app.core.daily_allowances import daily_allowance
from app.core.deps import MANAGE_TARGET_REFUSAL, refuse_unless_assignable, refuse_unless_manageable
from app.core.roles import (
    ADMIN,
    ARTISAN,
    CAPABILITY_MIN_ROLE,
    LOWEST_ROLE,
    MASTER_ADMIN,
    PROFESSOR,
    RESEARCHER,
    ROLE_LABELS,
    ROLE_ONLY_CAPABILITIES,
    ROLE_RANK,
    STUDENT,
    Capability,
    assignable_roles,
    can,
    capabilities_of,
    may_assign,
    may_manage_target,
    requires_two_factor,
    role_rank,
)
from app.services.app_settings import DEFAULTS, ROLE_DAILY_USD

SHARED_ROLES = Path(__file__).resolve().parents[2] / "shared" / "roles.json"

LADDER = (STUDENT, ARTISAN, RESEARCHER, PROFESSOR, ADMIN, MASTER_ADMIN)


def test_role_ranks_match_plan() -> None:
    assert ROLE_RANK == {
        MASTER_ADMIN: 60,
        ADMIN: 50,
        PROFESSOR: 40,
        RESEARCHER: 30,
        ARTISAN: 18,
        STUDENT: 15,
    }


def test_role_labels() -> None:
    assert ROLE_LABELS == {
        MASTER_ADMIN: "Master Admin",
        ADMIN: "Admin",
        PROFESSOR: "Professor",
        RESEARCHER: "Researcher",
        ARTISAN: "Artisan",
        STUDENT: "Student",
    }


def test_unknown_role_has_no_rank() -> None:
    assert role_rank("VISITOR") == 0
    assert role_rank({"role": "PROFESSOR"}) == 40
    assert role_rank({"role": "ADMIN"}) == 50
    assert not can("VISITOR", Capability.ASK_STANDARD)


def test_shared_roles_file_agrees() -> None:
    data = json.loads(SHARED_ROLES.read_text(encoding="utf-8"))
    assert {k: int(v) for k, v in data["ranks"].items()} == ROLE_RANK
    assert data["labels"] == ROLE_LABELS


MATRIX = {
    Capability.ASK_STANDARD: (True, True, True, True, True, True),
    Capability.VOICE: (True, True, True, True, True, True),
    Capability.GENERATE_IMAGE: (True, True, True, True, True, True),
    Capability.GENERATE_VIDEO: (False, False, True, True, True, True),
    Capability.SAVE_EXPORT: (True, True, True, True, True, True),
    Capability.READ_RESEARCHER_QUOTES: (False, False, True, True, True, True),
    Capability.PROPOSE_KNOWLEDGE: (False, False, True, True, True, True),
    Capability.RUN_ENRICHMENT: (False, False, True, True, True, True),
    Capability.ACCEPT_ALIASES: (False, False, True, True, True, True),
    Capability.MARK_CLAIM_LEVEL: (False, False, False, True, True, True),
    Capability.RETRACT_CLAIM: (False, False, False, True, True, True),
    Capability.SHARE_MEDIA: (False, False, False, True, True, True),
    Capability.HANDLE_OBJECTIONS: (False, False, False, True, True, True),
    Capability.MANAGE_ACCESS: (False, False, False, True, True, True),
    Capability.LIST_USERS: (False, False, False, True, True, True),
    Capability.INVITE_PROFESSORS: (False, False, False, False, True, True),
    Capability.CHANGE_ROLES: (False, False, False, False, True, True),
    Capability.DISABLE_USERS: (False, False, False, False, True, True),
    Capability.MANAGE_KEYS: (False, False, False, False, False, True),
    Capability.MANAGE_ROUTING: (False, False, False, False, False, True),
    Capability.MANAGE_QUOTAS: (False, False, False, False, False, True),
    Capability.MANAGE_CEILINGS: (False, False, False, False, False, True),
    Capability.MANAGE_DATASETS: (False, False, False, False, True, True),
    Capability.VIEW_USAGE: (False, False, False, False, True, True),
    Capability.VIEW_EVALUATION: (False, False, False, True, True, True),
    Capability.VIEW_AUDIT_LOG: (False, False, False, False, True, True),
    Capability.BUILD_LESSONS: (False, False, False, True, True, True),
    Capability.HIDE_GENERATED: (False, False, False, True, True, True),
    Capability.CONTRIBUTE_TESTIMONY: (False, True, False, False, False, False),
    Capability.REVIEW_TESTIMONY: (False, False, False, True, True, True),
    Capability.REVIEW_CONTRIBUTIONS: (False, False, False, False, True, True),
    Capability.CONFIRM_GUARDIAN_CONSENT: (False, False, False, True, True, True),
}


def test_matrix_covers_every_capability() -> None:
    assert set(MATRIX) == set(Capability)


def test_every_capability_is_in_exactly_one_map() -> None:
    by_rank = set(CAPABILITY_MIN_ROLE)
    by_role = set(ROLE_ONLY_CAPABILITIES)
    assert by_rank | by_role == set(Capability)
    assert not by_rank & by_role


def test_testimony_is_contributed_by_artisans_only() -> None:
    assert {Capability.CONTRIBUTE_TESTIMONY: frozenset({ARTISAN})} == ROLE_ONLY_CAPABILITIES
    assert "CONTRIBUTE_TESTIMONY" in capabilities_of(ARTISAN)
    assert "CONTRIBUTE_TESTIMONY" not in capabilities_of(MASTER_ADMIN)
    assert not can({"role": PROFESSOR}, Capability.CONTRIBUTE_TESTIMONY)
    assert can({"role": PROFESSOR}, Capability.REVIEW_TESTIMONY)
    assert not can(RESEARCHER, Capability.REVIEW_TESTIMONY)


def test_artisans_hold_every_student_capability() -> None:
    student = set(capabilities_of(STUDENT))
    artisan = set(capabilities_of(ARTISAN))
    assert artisan - student == {"CONTRIBUTE_TESTIMONY"}


def test_the_lowest_role_stays_student() -> None:
    assert LOWEST_ROLE == STUDENT
    assert not can(ARTISAN, Capability.MANAGE_ACCESS)
    assert assignable_roles(ARTISAN) == []


@pytest.mark.parametrize("capability", list(MATRIX))
def test_capability_matrix(capability: Capability) -> None:
    expected = MATRIX[capability]
    actual = tuple(can(role, capability) for role in LADDER)
    assert actual == expected


def test_admin_holds_everything_a_professor_holds() -> None:
    professor = {cap for cap in Capability if can(PROFESSOR, cap)}
    admin = {cap for cap in Capability if can(ADMIN, cap)}
    assert admin - professor == {
        Capability.INVITE_PROFESSORS,
        Capability.CHANGE_ROLES,
        Capability.DISABLE_USERS,
        Capability.VIEW_USAGE,
        Capability.VIEW_AUDIT_LOG,
        Capability.MANAGE_DATASETS,
        Capability.REVIEW_CONTRIBUTIONS,
    }
    assert professor <= admin


def test_assignable_roles() -> None:
    assert assignable_roles(MASTER_ADMIN) == [MASTER_ADMIN, ADMIN, PROFESSOR, RESEARCHER, ARTISAN, STUDENT]
    assert assignable_roles(ADMIN) == [PROFESSOR, RESEARCHER, ARTISAN, STUDENT]
    assert assignable_roles(PROFESSOR) == [RESEARCHER, ARTISAN, STUDENT]
    assert assignable_roles(RESEARCHER) == []
    assert assignable_roles(STUDENT) == []
    assert may_assign(PROFESSOR, STUDENT)
    assert not may_assign(PROFESSOR, PROFESSOR)
    assert not may_assign(RESEARCHER, None)
    assert may_assign(PROFESSOR, None)


def test_admin_assigns_up_to_professor_only() -> None:
    assert may_assign(ADMIN, PROFESSOR)
    assert may_assign(ADMIN, STUDENT)
    assert not may_assign(ADMIN, ADMIN)
    assert not may_assign(ADMIN, MASTER_ADMIN)
    assert not may_assign(PROFESSOR, ADMIN)


def test_master_admin_assigns_admin() -> None:
    assert may_assign(MASTER_ADMIN, ADMIN)
    assert may_assign(MASTER_ADMIN, MASTER_ADMIN)


def test_manage_target() -> None:
    assert may_manage_target(MASTER_ADMIN, MASTER_ADMIN)
    assert may_manage_target(MASTER_ADMIN, ADMIN)
    assert may_manage_target(ADMIN, PROFESSOR)
    assert may_manage_target(ADMIN, STUDENT)
    assert not may_manage_target(ADMIN, ADMIN)
    assert not may_manage_target(ADMIN, MASTER_ADMIN)
    assert may_manage_target(PROFESSOR, RESEARCHER)
    assert not may_manage_target(PROFESSOR, PROFESSOR)
    assert not may_manage_target(PROFESSOR, ADMIN)
    assert not may_manage_target(RESEARCHER, PROFESSOR)
    assert may_manage_target(PROFESSOR, ARTISAN)
    assert not may_manage_target(ARTISAN, ARTISAN)


def test_two_factor_required_roles() -> None:
    assert requires_two_factor(PROFESSOR)
    assert requires_two_factor(ADMIN)
    assert requires_two_factor(MASTER_ADMIN)
    assert not requires_two_factor(RESEARCHER)
    assert not requires_two_factor(STUDENT)
    assert not requires_two_factor(ARTISAN)


def test_no_role_has_a_daily_allowance_for_now() -> None:
    for role in [*ROLE_RANK, "GUEST"]:
        assert [daily_allowance(role, resource) for resource in ("VOICE_SECONDS", "IMAGE", "VIDEO")] == [
            None,
            None,
            None,
        ], role


@pytest.mark.usefixtures("allowances_an_owner_might_set")
def test_daily_allowances_follow_the_table_when_one_is_set() -> None:
    assert daily_allowance(STUDENT, "VOICE_SECONDS") == 600
    assert daily_allowance(RESEARCHER, "VOICE_SECONDS") == 1800
    assert daily_allowance(STUDENT, "IMAGE") == 5
    assert daily_allowance(PROFESSOR, "IMAGE") == 50
    assert daily_allowance(STUDENT, "VIDEO") == 0
    assert daily_allowance(PROFESSOR, "VIDEO") == 10
    assert daily_allowance(MASTER_ADMIN, "VIDEO") is None


@pytest.mark.usefixtures("allowances_an_owner_might_set")
def test_artisans_have_no_allowance_cap_and_do_not_fall_back_to_students() -> None:
    for resource in ("VOICE_SECONDS", "IMAGE", "VIDEO"):
        assert daily_allowance(ARTISAN, resource) is None


@pytest.mark.usefixtures("allowances_an_owner_might_set")
def test_admin_daily_allowances_when_set() -> None:
    assert daily_allowance(ADMIN, "VOICE_SECONDS") == 3600
    assert daily_allowance(ADMIN, "IMAGE") == 100
    assert daily_allowance(ADMIN, "VIDEO") == 20


def test_artisans_have_their_own_rows_and_no_cap_in_them() -> None:
    assert [daily_allowance(ARTISAN, resource) for resource in ("VOICE_SECONDS", "IMAGE", "VIDEO")] == [
        None
    ] * 3
    assert DEFAULTS[ROLE_DAILY_USD][ARTISAN] is None
    assert set(DEFAULTS[ROLE_DAILY_USD]) == set(ROLE_RANK)


def refusal(call: object, *args: object) -> HTTPException:
    with pytest.raises(HTTPException) as raised:
        call(*args)
    return raised.value


def test_admin_cannot_give_admin_roles() -> None:
    for role in (ADMIN, MASTER_ADMIN):
        refused = refusal(refuse_unless_assignable, ADMIN, role)
        assert refused.status_code == 403
        assert refused.detail == "You can give these roles: Professor, Researcher, Artisan, Student."
    refuse_unless_assignable(ADMIN, PROFESSOR)
    refuse_unless_assignable(MASTER_ADMIN, ADMIN)


def test_unknown_role_is_unprocessable() -> None:
    assert refusal(refuse_unless_assignable, MASTER_ADMIN, "VISITOR").status_code == 422
    assert refusal(refuse_unless_assignable, MASTER_ADMIN, None).status_code == 422


def test_admin_cannot_manage_admin_accounts() -> None:
    for target in ({"role": ADMIN}, {"role": MASTER_ADMIN}):
        refused = refusal(refuse_unless_manageable, {"role": ADMIN}, target)
        assert refused.status_code == 403
        assert refused.detail == MANAGE_TARGET_REFUSAL
    refuse_unless_manageable({"role": ADMIN}, {"role": PROFESSOR})
    refuse_unless_manageable({"role": MASTER_ADMIN}, {"role": ADMIN})


@pytest.mark.parametrize("configured", ["ADMIN", "MASTER_ADMIN", "VISITOR"])
def test_default_sign_up_role_is_never_an_admin_role(
    monkeypatch: pytest.MonkeyPatch, configured: str
) -> None:
    monkeypatch.setattr(get_settings(), "default_signup_role", configured)
    assert role_for_email("someone@example.com") == STUDENT


def test_default_sign_up_role_may_be_professor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "default_signup_role", PROFESSOR)
    assert role_for_email("someone@example.com") == PROFESSOR
