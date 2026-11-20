from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .base import ContractModel

__all__ = [
    "REVALIDATE_ROUTE",
    "REVALIDATE_SECRET_HEADER",
    "PageOwners",
    "RevalidationRequest",
    "category_targets",
    "craft_targets",
    "revalidation_request",
]

REVALIDATE_ROUTE = "/api/revalidate"
REVALIDATE_SECRET_HEADER = "x-revalidate-secret"
CRAFT_PAGE_TAG = "craft-page:{slug}"
DOCUMENT_TAG = "monograph-document:{subject}:{slug}"
CRAFT_PATH = "/crafts/{slug}"
CATEGORY_PATH = "/categories/{slug}"
DOCUMENT_PATH = "{page}/monograph"


@dataclass(frozen=True)
class PageOwners:
    crafts: tuple[str, ...] = ()
    categories: tuple[str, ...] = ()

    @property
    def empty(self) -> bool:
        return not self.crafts and not self.categories


class RevalidationRequest(ContractModel):
    paths: list[str]
    tags: list[str]


def craft_targets(slug: str) -> tuple[list[str], list[str]]:
    page = CRAFT_PATH.format(slug=slug)
    tags = [CRAFT_PAGE_TAG.format(slug=slug), DOCUMENT_TAG.format(subject="craft", slug=slug)]
    return [page, DOCUMENT_PATH.format(page=page)], tags


def category_targets(slug: str) -> tuple[list[str], list[str]]:
    page = CATEGORY_PATH.format(slug=slug)
    return [page, DOCUMENT_PATH.format(page=page)], [DOCUMENT_TAG.format(subject="category", slug=slug)]


def revalidation_request(owners: PageOwners) -> RevalidationRequest:
    paths: list[str] = []
    tags: list[str] = []
    for found_paths, found_tags in (
        *(craft_targets(slug) for slug in _sorted(owners.crafts)),
        *(category_targets(slug) for slug in _sorted(owners.categories)),
    ):
        paths.extend(found_paths)
        tags.extend(found_tags)
    return RevalidationRequest(paths=paths, tags=tags)


def _sorted(slugs: Iterable[str]) -> list[str]:
    return sorted(set(slugs))
