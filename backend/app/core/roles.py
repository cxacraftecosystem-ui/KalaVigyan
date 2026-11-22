from enum import StrEnum
from typing import Any

MASTER_ADMIN = "MASTER_ADMIN"
ADMIN = "ADMIN"
PROFESSOR = "PROFESSOR"
RESEARCHER = "RESEARCHER"
ARTISAN = "ARTISAN"
STUDENT = "STUDENT"

ROLE_RANK: dict[str, int] = {
    STUDENT: 15,
    ARTISAN: 18,
    RESEARCHER: 30,
    PROFESSOR: 40,
    ADMIN: 50,
    MASTER_ADMIN: 60,
}

ROLE_LABELS: dict[str, str] = {
    STUDENT: "Student",
    ARTISAN: "Artisan",
    RESEARCHER: "Researcher",
    PROFESSOR: "Professor",
    ADMIN: "Admin",
    MASTER_ADMIN: "Master Admin",
}

ROLES_BY_RANK: tuple[str, ...] = tuple(sorted(ROLE_RANK, key=lambda role: -ROLE_RANK[role]))
LOWEST_ROLE: str = ROLES_BY_RANK[-1]

TWO_FACTOR_REQUIRED_ROLES = frozenset({PROFESSOR, ADMIN, MASTER_ADMIN})
UNCAPPED_ROLES = frozenset({MASTER_ADMIN})


class Capability(StrEnum):
    ASK_STANDARD = "ASK_STANDARD"
    VOICE = "VOICE"
    GENERATE_IMAGE = "GENERATE_IMAGE"
    GENERATE_VIDEO = "GENERATE_VIDEO"
    SAVE_EXPORT = "SAVE_EXPORT"
    READ_RESEARCHER_QUOTES = "READ_RESEARCHER_QUOTES"
    PROPOSE_KNOWLEDGE = "PROPOSE_KNOWLEDGE"
    RUN_ENRICHMENT = "RUN_ENRICHMENT"
    ACCEPT_ALIASES = "ACCEPT_ALIASES"
    MARK_CLAIM_LEVEL = "MARK_CLAIM_LEVEL"
    RETRACT_CLAIM = "RETRACT_CLAIM"
    SHARE_MEDIA = "SHARE_MEDIA"
    HANDLE_OBJECTIONS = "HANDLE_OBJECTIONS"
    MANAGE_ACCESS = "MANAGE_ACCESS"
    LIST_USERS = "LIST_USERS"
    INVITE_PROFESSORS = "INVITE_PROFESSORS"
    CHANGE_ROLES = "CHANGE_ROLES"
    DISABLE_USERS = "DISABLE_USERS"
    MANAGE_KEYS = "MANAGE_KEYS"
    MANAGE_ROUTING = "MANAGE_ROUTING"
    MANAGE_QUOTAS = "MANAGE_QUOTAS"
    MANAGE_CEILINGS = "MANAGE_CEILINGS"
    MANAGE_DATASETS = "MANAGE_DATASETS"
    VIEW_USAGE = "VIEW_USAGE"
    VIEW_EVALUATION = "VIEW_EVALUATION"
    VIEW_AUDIT_LOG = "VIEW_AUDIT_LOG"
    BUILD_LESSONS = "BUILD_LESSONS"
    HIDE_GENERATED = "HIDE_GENERATED"
    CONTRIBUTE_TESTIMONY = "CONTRIBUTE_TESTIMONY"
    REVIEW_TESTIMONY = "REVIEW_TESTIMONY"
    REVIEW_CONTRIBUTIONS = "REVIEW_CONTRIBUTIONS"
    CONFIRM_GUARDIAN_CONSENT = "CONFIRM_GUARDIAN_CONSENT"


CAPABILITY_MIN_ROLE: dict[Capability, str] = {
    Capability.ASK_STANDARD: STUDENT,
    Capability.VOICE: STUDENT,
    Capability.GENERATE_IMAGE: STUDENT,
    Capability.GENERATE_VIDEO: RESEARCHER,
    Capability.SAVE_EXPORT: STUDENT,
    Capability.READ_RESEARCHER_QUOTES: RESEARCHER,
    Capability.PROPOSE_KNOWLEDGE: RESEARCHER,
    Capability.RUN_ENRICHMENT: RESEARCHER,
    Capability.ACCEPT_ALIASES: RESEARCHER,
    Capability.MARK_CLAIM_LEVEL: PROFESSOR,
    Capability.RETRACT_CLAIM: PROFESSOR,
    Capability.SHARE_MEDIA: PROFESSOR,
    Capability.HANDLE_OBJECTIONS: PROFESSOR,
    Capability.MANAGE_ACCESS: PROFESSOR,
    Capability.LIST_USERS: PROFESSOR,
    Capability.INVITE_PROFESSORS: ADMIN,
    Capability.CHANGE_ROLES: ADMIN,
    Capability.DISABLE_USERS: ADMIN,
    Capability.MANAGE_KEYS: MASTER_ADMIN,
    Capability.MANAGE_ROUTING: MASTER_ADMIN,
    Capability.MANAGE_QUOTAS: MASTER_ADMIN,
    Capability.MANAGE_CEILINGS: MASTER_ADMIN,
    Capability.MANAGE_DATASETS: ADMIN,
    Capability.VIEW_USAGE: ADMIN,
    Capability.VIEW_EVALUATION: PROFESSOR,
    Capability.VIEW_AUDIT_LOG: ADMIN,
    Capability.BUILD_LESSONS: PROFESSOR,
    Capability.HIDE_GENERATED: PROFESSOR,
    Capability.REVIEW_TESTIMONY: PROFESSOR,
    Capability.REVIEW_CONTRIBUTIONS: ADMIN,
    Capability.CONFIRM_GUARDIAN_CONSENT: PROFESSOR,
}

ROLE_ONLY_CAPABILITIES: dict[Capability, frozenset[str]] = {
    Capability.CONTRIBUTE_TESTIMONY: frozenset({ARTISAN}),
}

ALLOWANCE_RESOURCES: tuple[str, ...] = ("VOICE_SECONDS", "IMAGE", "VIDEO")


def role_value(user_or_role: Any) -> str:
    if isinstance(user_or_role, str):
        return user_or_role
    role = user_or_role.get("role") if isinstance(user_or_role, dict) else getattr(user_or_role, "role", None)
    return str(getattr(role, "value", role) or "")


def role_rank(user_or_role: Any) -> int:
    return ROLE_RANK.get(role_value(user_or_role), 0)


def has_rank(user_or_role: Any, role: str) -> bool:
    return role_rank(user_or_role) >= ROLE_RANK[role]


def is_known_role(role: Any) -> bool:
    return isinstance(role, str) and role in ROLE_RANK


def is_master_admin(user_or_role: Any) -> bool:
    return role_value(user_or_role) == MASTER_ADMIN


def can(user_or_role: Any, capability: Capability) -> bool:
    holders = ROLE_ONLY_CAPABILITIES.get(capability)
    if holders is not None:
        return role_value(user_or_role) in holders
    return has_rank(user_or_role, CAPABILITY_MIN_ROLE[capability])


def capabilities_of(user_or_role: Any) -> list[str]:
    return sorted(cap.value for cap in Capability if can(user_or_role, cap))


def assignable_roles(actor: Any) -> list[str]:
    if is_master_admin(actor):
        return list(ROLES_BY_RANK)
    if can(actor, Capability.MANAGE_ACCESS):
        own = role_rank(actor)
        return [role for role in ROLES_BY_RANK if ROLE_RANK[role] < own]
    return []


def may_assign(actor: Any, role: str | None) -> bool:
    if role is None:
        return can(actor, Capability.MANAGE_ACCESS)
    return role in assignable_roles(actor)


def may_manage_target(actor: Any, target: Any) -> bool:
    if is_master_admin(actor):
        return True
    return role_rank(actor) > role_rank(target)


def is_uncapped(user_or_role: Any) -> bool:
    return role_value(user_or_role) in UNCAPPED_ROLES


def requires_two_factor(user_or_role: Any) -> bool:
    return role_value(user_or_role) in TWO_FACTOR_REQUIRED_ROLES
