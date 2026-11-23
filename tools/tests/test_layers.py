from __future__ import annotations

from pathlib import PurePosixPath

from hygiene.layers import LAYER_IMPORTS, import_violations, module_name


def check(path: str, text: str) -> list[str]:
    return [violation.describe() for violation in import_violations([(PurePosixPath(path), text)])]


def test_module_name_of_a_module_and_a_package() -> None:
    assert module_name(PurePosixPath("backend/app/core/db.py")) == ("app.core.db", False)
    assert module_name(PurePosixPath("backend/app/providers/__init__.py")) == ("app.providers", True)


def test_downward_imports_pass() -> None:
    assert (
        check("backend/app/services/audit.py", "from app.core.db import get_session\nimport app.models\n")
        == []
    )
    assert check("backend/app/api/routes/auth.py", "from app.services import mailer\n") == []


def test_core_importing_a_service_is_refused() -> None:
    found = check("backend/app/core/deps.py", "import os\n\nfrom app.services.users import serialize_user\n")
    assert found == [
        "backend/app/core/deps.py:3: core imports app.services.users (core may not import services)"
    ]


def test_from_app_import_names_the_layer() -> None:
    found = check("backend/app/models/crafts.py", "from app import services\n")
    assert found == [
        "backend/app/models/crafts.py:1: models imports app.services (models may not import services)"
    ]


def test_a_late_import_inside_a_function_is_still_checked() -> None:
    text = "def load():\n    from app.api import router\n    return router\n"
    found = check("backend/app/services/craft_seed.py", text)
    assert found == [
        "backend/app/services/craft_seed.py:2: services imports app.api (services may not import api)"
    ]


def test_relative_import_resolves_against_its_package() -> None:
    assert check("backend/app/providers/openai_p.py", "from .base import Adapter\n") == []
    found = check("backend/app/schemas/auth.py", "from ..services import users\n")
    assert found == [
        "backend/app/schemas/auth.py:1: schemas imports app.services (schemas may not import services)"
    ]


def test_schemas_reuse_research_shapes_but_not_models() -> None:
    assert check("backend/app/schemas/science.py", "from app.research.citations import Citation\n") == []
    found = check("backend/app/schemas/science.py", "from app.models.enums import STAGE_TYPES\n")
    assert found == [
        "backend/app/schemas/science.py:1: schemas imports app.models.enums (schemas may not import models)"
    ]


def test_the_science_engine_builds_on_the_contracts_and_reaches_no_storage() -> None:
    assert (
        check("backend/app/science/process_view.py", "from app.schemas.science import CraftProcess\n") == []
    )
    assert check("backend/app/services/science_seed.py", "from app.science.balance import balance\n") == []
    found = check("backend/app/science/balance.py", "from app.models import Reaction\n")
    assert found == [
        "backend/app/science/balance.py:1: science imports app.models (science may not import models)"
    ]


def test_the_region_builder_builds_on_the_contracts_and_reaches_no_storage() -> None:
    assert check("backend/app/geo/region_view.py", "from app.schemas.region import CraftRegion\n") == []
    assert check("backend/app/services/region_records.py", "from app.geo.places import region_places\n") == []
    assert check("backend/app/api/routes/map_layers.py", "from app.geo.layers import map_layer\n") == []
    assert check("backend/app/geo/places.py", "from app.models import CraftLocation\n") == [
        "backend/app/geo/places.py:1: geo imports app.models (geo may not import models)"
    ]
    assert check("backend/app/geo/layers.py", "from app.science.units import normalised_bounds\n") == [
        "backend/app/geo/layers.py:1: geo imports app.science.units (geo may not import science)"
    ]


def test_relative_import_inside_a_package_init() -> None:
    assert check("backend/app/providers/__init__.py", "from . import base\n") == []


def test_feature_layers_do_not_import_each_other_sideways() -> None:
    found = check("backend/app/services/knowledge_view.py", "from app.schemas.common import APIModel\n")
    assert found == [
        "backend/app/services/knowledge_view.py:1: services imports app.schemas.common (services may not import schemas)"
    ]


def test_a_script_checks_media_through_the_media_pipeline_and_nothing_below_imports_media() -> None:
    assert check("backend/app/scripts/paid_check_video.py", "from app.media.mp4 import video_facts\n") == []
    assert check("backend/app/services/media_ref_store.py", "from app.media.mp4 import video_facts\n") != []


def test_nothing_below_the_entry_points_imports_main_or_scripts() -> None:
    assert check("backend/app/api/router.py", "from app.main import app\n") != []
    assert check("backend/app/services/craft_seed.py", "from app.scripts import seed_crafts\n") != []


def test_an_unmapped_layer_fails_closed() -> None:
    found = check("backend/app/governance/flags.py", "import math\n")
    assert found == [
        "backend/app/governance/flags.py:1: governance imports app.governance.flags "
        "(app.governance is not a layer in LAYER_IMPORTS)"
    ]


def test_importing_the_root_package_is_refused() -> None:
    found = check("backend/app/core/config.py", "import app\n")
    assert found == ["backend/app/core/config.py:1: core imports app (imports the root package)"]


def test_third_party_imports_are_ignored() -> None:
    assert check("backend/app/core/db.py", "import sqlalchemy\nfrom fastapi import Depends\n") == []


def test_shared_layers_import_no_feature_layer() -> None:
    assert LAYER_IMPORTS["models"] == frozenset({"models"})
    assert LAYER_IMPORTS["data"] == frozenset({"data"})
    assert LAYER_IMPORTS["core"] == frozenset({"core", "models"})
    assert LAYER_IMPORTS["research"] == frozenset({"research", "core", "models"})


def test_the_research_contracts_import_no_feature_layer() -> None:
    found = check("backend/app/research/stream.py", "from app.services import knowledge_view\n")
    assert found == [
        "backend/app/research/stream.py:1: research imports app.services (research may not import services)"
    ]
    upward = "from app.research.vocabulary import LEVEL_ORDER\n"
    assert check("backend/app/services/knowledge_view.py", upward) == []


def test_retrieval_sits_below_services_and_reaches_no_service() -> None:
    assert check("backend/app/services/knowledge_view.py", "from app.retrieval import hybrid\n") == []
    found = check("backend/app/retrieval/hybrid.py", "from app.services import knowledge_view\n")
    assert found == [
        "backend/app/retrieval/hybrid.py:1: retrieval imports app.services (retrieval may not import services)"
    ]


def test_the_planner_builds_on_sources_and_reaches_no_provider_or_service() -> None:
    assert check("backend/app/planner/reading.py", "from app.sources.adapter import build_document\n") == []
    assert (
        check("backend/app/services/live_sources.py", "from app.planner.reading import LiveSources\n") == []
    )
    found = check("backend/app/planner/drafting.py", "from app.providers import router\n")
    assert found == [
        "backend/app/planner/drafting.py:1: planner imports app.providers (planner may not import providers)"
    ]
    found = check("backend/app/sources/adapter.py", "from app.planner import policy\n")
    assert found == [
        "backend/app/sources/adapter.py:1: sources imports app.planner (sources may not import planner)"
    ]


def test_voice_orchestrates_providers_and_contracts_and_only_entry_points_import_it() -> None:
    allowed = "from app.providers.elevenlabs import ElevenLabs\nfrom app.schemas.voice import MAX_TURNS\n"
    assert check("backend/app/voice/relay.py", allowed) == []
    assert check("backend/app/api/routes/voice.py", "from app.voice.relay import relay_turn_events\n") == []
    assert check("backend/app/worker.py", "from app.voice.daily_upkeep import daily_voice_upkeep\n") == []
    found = check("backend/app/worker.py", "from app.providers.elevenlabs import ElevenLabs\n")
    assert found == [
        "backend/app/worker.py:1: worker imports app.providers.elevenlabs (worker may not import providers)"
    ]
    found = check("backend/app/voice/relay.py", "from app.api import voice_deps\n")
    assert found == ["backend/app/voice/relay.py:1: voice imports app.api (voice may not import api)"]
    found = check("backend/app/services/answering.py", "from app.voice import turns\n")
    assert found == [
        "backend/app/services/answering.py:1: services imports app.voice (services may not import voice)"
    ]


def test_providers_sit_below_services_and_services_call_them() -> None:
    found = check("backend/app/providers/router.py", "from app.services import app_settings\n")
    assert found == [
        "backend/app/providers/router.py:1: providers imports app.services (providers may not import services)"
    ]
    assert check("backend/app/services/managed_secrets.py", "from app.providers import anthropic_p\n") == []
