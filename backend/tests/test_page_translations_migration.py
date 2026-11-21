import ast
from pathlib import Path

from app.models.page_translations import TRANSLATION_ORIGINS, TRANSLATION_ROW_STATUSES
from app.research.page_translations import TRANSLATION_STATUSES
from app.research.review_switch import PROPOSAL_ORIGINS

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0059_page_translations.py"


def constants() -> dict[str, object]:
    found: dict[str, object] = {}
    for node in ast.parse(MIGRATION.read_text("utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target, value = node.target.id, node.value
        else:
            continue
        if isinstance(value, ast.Constant) or (
            isinstance(value, ast.Tuple) and all(isinstance(item, ast.Constant) for item in value.elts)
        ):
            found[target] = ast.literal_eval(value)
    return found


def test_the_migration_checks_the_statuses_and_origins_the_models_and_contract_hold() -> None:
    held = constants()
    assert held["STATUSES"] == TRANSLATION_ROW_STATUSES == TRANSLATION_STATUSES
    assert held["STATUSES"] == ("APPROVED", "IN_REVIEW", "DRAFT", "REJECTED", "SUPERSEDED")
    assert held["ORIGINS"] == TRANSLATION_ORIGINS == PROPOSAL_ORIGINS
    assert held["revision"] == "0059_page_translations"
    assert (held["TRANSLATION"], held["TEXT_UNIT"], held["READER"]) == (
        "PageTranslation",
        "PageTextUnit",
        "TranslationReader",
    )
