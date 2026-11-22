import ast
from pathlib import Path

from app.models.enums import AI_PROVIDERS, AI_TASKS
from app.providers.catalogue import (
    DEFAULT_ROUTES,
    PROVIDERS,
    ROUTABLE_TASKS,
    TASK_LABELS,
    AiProvider,
    AiTask,
    catalogue,
    supports,
)
from app.providers.presets import ALLOWED_KEY_NAMES, BY_PRESET
from app.services import managed_secrets

MIGRATION = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0060_reranking.py"


def constants() -> dict[str, object]:
    found: dict[str, object] = {}
    for node in ast.parse(MIGRATION.read_text("utf-8")).body:
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            target, value = node.targets[0].id, node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            target, value = node.target.id, node.value
        else:
            continue
        try:
            found[target] = ast.literal_eval(value)
        except ValueError:
            continue
    return found


def test_voyage_reranks_only_and_rerank_routes_to_rerank_3() -> None:
    spec = PROVIDERS[AiProvider.VOYAGE]
    assert (spec.managed_key, spec.preset, spec.kind, spec.base_url) == (
        "VOYAGE_API_KEY",
        "voyage",
        "voyage",
        "https://api.voyageai.com/v1",
    )
    assert (spec.console_url, spec.pricing_url) == (
        "https://dash.voyageai.com",
        "https://docs.voyageai.com/docs/pricing",
    )
    (model,) = spec.models
    assert (model.id, model.price_per_mtok, model.tasks) == (
        "rerank-3",
        (0.05, 0.0),
        frozenset({AiTask.RERANK}),
    )
    assert DEFAULT_ROUTES[AiTask.RERANK] == ((AiProvider.VOYAGE, "rerank-3"),)
    assert AiTask.RERANK in ROUTABLE_TASKS and TASK_LABELS[AiTask.RERANK] == "Rerank stored facts"
    assert not supports("VOYAGE", "rerank-3", AiTask.COMPOSE)
    assert not supports("GEMINI", "gemini-embedding-2", AiTask.RERANK)


def test_the_admin_catalogue_lists_voyage_with_its_rerank_model() -> None:
    entry = next(row for row in catalogue() if row["provider"] == "VOYAGE")
    assert (entry["managedKey"], entry["defaultModel"]) == ("VOYAGE_API_KEY", "rerank-3")
    assert [(m["id"], m["tasks"], m["pricePerMTok"]) for m in entry["models"]] == [
        ("rerank-3", ["RERANK"], [0.05, 0.0])
    ]


def test_the_key_is_a_managed_key_the_voyage_preset_may_read() -> None:
    assert "VOYAGE_API_KEY" in managed_secrets.MANAGED_KEYS and "VOYAGE_API_KEY" in ALLOWED_KEY_NAMES
    assert managed_secrets.MANAGED_KEYS["VOYAGE_API_KEY"].settings_attr == "voyage_api_key"
    assert BY_PRESET["voyage"]["base_url"] == "https://api.voyageai.com/v1"


def test_the_migration_adds_the_two_values_the_models_hold_and_seeds_the_default_route() -> None:
    held = constants()
    assert (held["revision"], held["down_revision"]) == ("0060_reranking", "0059_page_translations")
    assert held["ENUM_ADDITIONS"] == (("AiProvider", ("VOYAGE",)), ("AiTask", ("RERANK",)))
    assert AI_PROVIDERS[-1] == "VOYAGE" and AI_TASKS[-1] == "RERANK"
    route = held["RERANK_ROUTE"]
    assert isinstance(route, dict)
    assert ((AiProvider(route["provider"]), route["model"]),) == DEFAULT_ROUTES[AiTask.RERANK]
    provider = held["VOYAGE"]
    assert isinstance(provider, dict)
    spec = PROVIDERS[AiProvider.VOYAGE]
    assert (provider["preset"], provider["kind"], provider["baseUrl"], provider["apiKeySecretKey"]) == (
        spec.preset,
        spec.kind,
        spec.base_url,
        spec.managed_key,
    )
