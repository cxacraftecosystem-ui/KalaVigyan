from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .craft_master_loader import ALL_INDIA, MasterCraft, load_master
from .portal_craft_register import PortalCraft, load_portal_crafts

__all__ = ["CategoryScope", "CraftScope", "SubCategory", "category_scopes", "craft_scopes", "is_family"]


@dataclass(frozen=True)
class CraftScope:
    slug: str
    name: str
    family: bool
    category_slug: str | None = None
    merged_into: str | None = None


@dataclass(frozen=True)
class SubCategory:
    slug: str
    name: str


@dataclass(frozen=True)
class CategoryScope:
    slug: str
    name: str
    sub_categories: tuple[SubCategory, ...]


def craft_scopes(
    master: Sequence[MasterCraft] | None = None, portal: Sequence[PortalCraft] | None = None
) -> dict[str, CraftScope]:
    listed = load_master() if master is None else master
    category_of_sub = {craft.sub_category_slug: craft.category_slug for craft in listed}
    scopes = {
        craft.slug: CraftScope(
            craft.slug,
            craft.name,
            is_family(craft.is_catch_all, craft.state_of_practice),
            category_slug=craft.category_slug,
        )
        for craft in listed
    }
    for craft in load_portal_crafts() if portal is None else portal:
        if craft.slug in scopes:
            raise ValueError(f"portal craft {craft.slug} is already on the master list")
        scopes[craft.slug] = CraftScope(
            craft.slug,
            craft.name,
            is_family(False, craft.state_of_practice),
            category_slug=category_of_sub.get(craft.sub_category_slug or ""),
            merged_into=craft.merged_into,
        )
    return scopes


def category_scopes(master: Sequence[MasterCraft] | None = None) -> dict[str, CategoryScope]:
    names: dict[str, str] = {}
    subs: dict[str, dict[str, str]] = {}
    for craft in load_master() if master is None else master:
        names.setdefault(craft.category_slug, craft.category)
        subs.setdefault(craft.category_slug, {}).setdefault(craft.sub_category_slug, craft.sub_category)
    return {
        slug: CategoryScope(slug, name, tuple(SubCategory(sub, label) for sub, label in subs[slug].items()))
        for slug, name in names.items()
    }


def is_family(catch_all: bool, practice: Sequence[str]) -> bool:
    return catch_all or tuple(practice) == (ALL_INDIA,)
