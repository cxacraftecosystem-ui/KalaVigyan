import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import Field

from app.research.base import ContractModel, absent
from app.research.blocks_lede import LedeBlock
from app.research.blocks_signature import SignatureBlock
from app.research.category_page import CategoryList, CategoryPage
from app.research.craft_catalogue import CraftCatalogue
from app.research.craft_compare import CraftComparison
from app.research.craft_page import CraftPage
from app.research.explainer import Explainer
from app.research.knowledge_pieces import KnowledgePiece
from app.research.quiz import ExplainerQuiz
from app.research.terms import Term

from .blocks_golden import QUANTITIES, SUPPLY_DISTRICT, TIMELINE_UNDATED, BlocksFixture
from .golden import SHARED
from .golden_fields import reachable_models, shown_fields, shown_in, unshown_fields
from .learning_golden import AlertsFixture, LessonFixture, VersionsFixture
from .phase_b_golden import PhaseBFixture
from .phase_c_golden import PhaseCFixture
from .phase_d_golden import PhaseDFixture

GOLDEN_MODELS: dict[str, Any] = {
    "craft.page.golden.json": CraftPage,
    "craft.page.register.golden.json": CraftPage,
    "category.page.golden.json": CategoryPage,
    "category.page.not-curated.golden.json": CategoryPage,
    "category.list.golden.json": CategoryList,
    "craft.catalogue.golden.json": CraftCatalogue,
    "learning.compare.golden.json": CraftComparison,
    "explainer.document.golden.json": Explainer,
    "explainer.lede.golden.json": Explainer,
    "explainer.withdrawn.golden.json": Explainer,
    "explainer.phase-b.golden.json": PhaseBFixture,
    "explainer.phase-c.golden.json": PhaseCFixture,
    "explainer.phase-d.golden.json": PhaseDFixture,
    QUANTITIES: BlocksFixture,
    TIMELINE_UNDATED: BlocksFixture,
    SUPPLY_DISTRICT: BlocksFixture,
    "explainer.signature.golden.json": list[SignatureBlock],
    "explainer.signature-lede.golden.json": LedeBlock,
    "explainer.piece.golden.json": KnowledgePiece,
    "explainer.term.golden.json": Term,
    "learning.quiz.golden.json": ExplainerQuiz,
    "learning.versions.golden.json": VersionsFixture,
    "learning.alerts.golden.json": AlertsFixture,
    "learning.lesson.golden.json": LessonFixture,
}
SERVED = (CraftPage, CategoryPage, CategoryList, CraftCatalogue, CraftComparison, Explainer)
NOT_SERVED_TO_THE_WEB = {
    "app.research.craft_catalogue.CatalogueCraftRecord": "the catalogue's records, served only to the MCP tools"
}
UNSHOWN_FILE = Path(__file__).with_name("unshown_fields.json")


class Cited(ContractModel):
    title: str
    container_title: str | None = Field(default=None, exclude_if=absent)


class Listing(ContractModel):
    sources: list[Cited]


@cache
def every_shown() -> frozenset[tuple[str, str]]:
    return frozenset(key for name, root in GOLDEN_MODELS.items() for key in shown_fields(root, [name]))


def test_a_field_the_payload_leaves_out_is_unshown_until_a_golden_carries_it() -> None:
    plain = shown_in(Listing, '{"sources": [{"title": "Block printing of Akola"}]}')
    module = __name__
    assert plain == {(f"{module}.Listing", "sources"), (f"{module}.Cited", "title")}
    assert unshown_fields([Listing], plain) == [f"{module}.Cited.container_title"]
    journal = shown_in(Listing, '{"sources": [{"title": "Akola", "containerTitle": "Textile history"}]}')
    assert unshown_fields([Listing], plain | journal) == []
    assert reachable_models([list[Listing]]) == {Listing, Cited}


def test_every_golden_file_of_a_served_payload_is_listed() -> None:
    listed = set(GOLDEN_MODELS)
    for prefix in ("craft.page", "category.", "craft.catalogue", "learning.compare", "explainer.document"):
        assert {path.name for path in SHARED.glob(f"{prefix}*.golden.json")} <= listed


def served_unshown() -> set[str]:
    unshown = set(unshown_fields(SERVED, set(every_shown())))
    return {name for name in unshown if name.rsplit(".", 1)[0] not in NOT_SERVED_TO_THE_WEB}


def test_every_field_a_served_payload_can_carry_appears_in_a_golden_or_in_the_shrinking_list() -> None:
    listed = set(json.loads(UNSHOWN_FILE.read_text(encoding="utf-8"))["fields"])
    unshown = served_unshown()
    assert sorted(unshown - listed) == [], "show these fields in a golden"
    assert sorted(listed - unshown) == [], (
        f"these are shown or gone now; remove them from {UNSHOWN_FILE.name}"
    )


def test_a_model_kept_out_of_the_web_s_payloads_is_one_they_can_hold() -> None:
    reachable = {f"{model.__module__}.{model.__qualname__}" for model in reachable_models(SERVED)}
    assert set(NOT_SERVED_TO_THE_WEB) <= reachable
