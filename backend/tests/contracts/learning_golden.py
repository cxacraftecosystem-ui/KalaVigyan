from typing import Any, Literal

from app.research.alerts import NotificationList, SavedExplainerList, WeeklyDigest
from app.research.base import ContractModel
from app.research.explainer_versions import (
    BuildsOn,
    BuildsOnEvent,
    ExplainerHistory,
    ExplainerVersionDocument,
)
from app.research.lessons import LessonList, LessonPack, LessonRequest
from app.research.shared_science import ConceptCraftsPage, SharedConcept, SharedScience

from .golden import golden_json

__all__ = [
    "ALERTS",
    "CITATIONS",
    "DISTRICT_CRAFTS",
    "LESSON",
    "SHARED_SCIENCE",
    "VERSIONS",
    "AlertsFixture",
    "LessonFixture",
    "SharedScienceFixture",
    "VersionsFixture",
    "learning",
]

VERSIONS = "learning.versions.golden.json"
ALERTS = "learning.alerts.golden.json"
LESSON = "learning.lesson.golden.json"
CITATIONS = "learning.citations.golden.json"
SHARED_SCIENCE = "learning.shared-science.golden.json"
DISTRICT_CRAFTS = "map.district-crafts.golden.json"


class VersionsFixture(ContractModel):
    schema_version: Literal[1]
    history: ExplainerHistory
    latest: ExplainerVersionDocument
    request: BuildsOn
    builds_on: BuildsOnEvent


class AlertsFixture(ContractModel):
    schema_version: Literal[1]
    saved: SavedExplainerList
    notifications: NotificationList
    digest: WeeklyDigest


class LessonFixture(ContractModel):
    schema_version: Literal[1]
    request: LessonRequest
    pack: LessonPack
    list: LessonList


class SharedScienceFixture(ContractModel):
    schema_version: Literal[1]
    craft: SharedScience
    concept: SharedConcept
    crafts: ConceptCraftsPage


def learning(name: str) -> Any:
    return golden_json(name)
