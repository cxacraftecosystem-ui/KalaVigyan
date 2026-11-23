from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass

from app.data.curation_scopes import CategoryScope, CraftScope, category_scopes, craft_scopes
from app.data.district_register import DistrictRegister, load_district_register

from .check_file import CheckFile, check_file_problems
from .claim_rules import claim_problems
from .coverage import coverage_problems
from .dossier import CATEGORY_SCOPE, Dossier
from .entity_rules import (
    alternative_problems,
    community_problems,
    market_problems,
    picture_problems,
    place_problems,
    reaction_problems,
    stage_problems,
)
from .overview_rules import overview_problems
from .page_rules import native_name_problems, placement_problems, stage_page_problems
from .problems import Problem
from .references import id_problems, reference_problems
from .scope_rules import category_problems, craft_scope_problems, scope_header_problems
from .source_rules import personal_data_problems, source_problems

__all__ = ["DOSSIER_RULES", "CheckContext", "content_problems", "default_context", "dossier_problems"]

DOSSIER_RULES: tuple[Callable[[Dossier], list[Problem]], ...] = (
    claim_problems,
    source_problems,
    community_problems,
    stage_problems,
    reaction_problems,
    alternative_problems,
    market_problems,
    picture_problems,
    stage_page_problems,
    placement_problems,
    native_name_problems,
    overview_problems,
    coverage_problems,
    personal_data_problems,
)


@dataclass(frozen=True)
class CheckContext:
    crafts: Mapping[str, CraftScope]
    categories: Mapping[str, CategoryScope]
    districts: DistrictRegister


def default_context() -> CheckContext:
    return CheckContext(
        crafts=craft_scopes(), categories=category_scopes(), districts=load_district_register()
    )


def content_problems(dossier: Dossier, context: CheckContext) -> list[Problem]:
    found = scope_header_problems(dossier, context.crafts, context.categories)
    structure = [*id_problems(dossier), *reference_problems(dossier)]
    if structure:
        return found + structure
    for rule in DOSSIER_RULES:
        found += rule(dossier)
    category = context.categories.get(dossier.slug) if dossier.scope == CATEGORY_SCOPE else None
    if category is not None:
        found += category_problems(dossier, category, context.crafts)
    elif dossier.scope != CATEGORY_SCOPE:
        found += craft_scope_problems(dossier)
    return found + place_problems(dossier, context.districts)


def dossier_problems(dossier: Dossier, context: CheckContext, check: CheckFile | None) -> list[Problem]:
    return content_problems(dossier, context) + check_file_problems(dossier, check)
