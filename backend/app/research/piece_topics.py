from __future__ import annotations

import hashlib
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.core.errors import InvalidInput
from app.models.enums import DISTRICT_PLACE_PREFIX

from .subject_keys import topic_key

__all__ = [
    "DISTRICT_SET_DIGEST_CHARS",
    "FACET_NAMESPACES",
    "PLACE_FACETS",
    "TopicSubjects",
    "district_subject",
    "district_topic",
    "facet_topic",
    "facet_topics",
]

FACET_NAMESPACES: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "craft",
        "PROCESS": "process",
        "CHEMISTRY": "reaction",
        "PHYSICS": "concept",
        "MATERIALS": "material",
        "GEOGRAPHY": "water",
        "GEOLOGY": "soil",
        "CLIMATE": "climate",
        "ECOLOGY": "ecology",
        "BOTANY": "material",
        "HISTORY": "history",
        "ECONOMICS": "economy",
        "DESIGN": "design",
        "HEALTH": "health",
        "SOCIETY": "society",
        "POLICY": "policy",
    }
)
PLACE_FACETS = frozenset({"GEOGRAPHY", "GEOLOGY", "CLIMATE"})
DISTRICT_SET_SUBJECT = f"{DISTRICT_PLACE_PREFIX}-set"
DISTRICT_SET_DIGEST_CHARS = 16


@dataclass(frozen=True)
class TopicSubjects:
    craft_slug: str
    question_terms: tuple[str, ...] = ()
    districts: tuple[int, ...] = ()


def district_subject(district_lgd: int) -> str:
    return f"{DISTRICT_PLACE_PREFIX}-{district_lgd}"


def district_topic(namespace: str, district_lgds: Collection[int]) -> str:
    try:
        return topic_key(namespace, *(district_subject(lgd) for lgd in district_lgds))
    except InvalidInput:
        listed = ",".join(str(lgd) for lgd in sorted(set(district_lgds)))
        digest = hashlib.sha256(listed.encode("ascii")).hexdigest()[:DISTRICT_SET_DIGEST_CHARS]
        return topic_key(namespace, f"{DISTRICT_SET_SUBJECT}-{digest}")


def facet_topic(facet: str, subjects: TopicSubjects) -> str | None:
    namespace = FACET_NAMESPACES[facet]
    if subjects.question_terms:
        return _topic(namespace, subjects.question_terms)
    if facet in PLACE_FACETS and subjects.districts:
        return district_topic(namespace, subjects.districts)
    return _topic(namespace, (subjects.craft_slug,))


def facet_topics(facets: Sequence[str], subjects: TopicSubjects) -> dict[str, str]:
    found = {facet: facet_topic(facet, subjects) for facet in dict.fromkeys(facets)}
    return {facet: topic for facet, topic in found.items() if topic is not None}


def _topic(namespace: str, subjects: Sequence[str]) -> str | None:
    try:
        return topic_key(namespace, *subjects)
    except InvalidInput:
        return None
