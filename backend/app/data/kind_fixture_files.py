from __future__ import annotations

import json
from functools import cache
from typing import Any

from .craft_master_loader import DATA_DIR

__all__ = ["KIND_FIXTURES_DIR", "KIND_FIXTURE_ORDER", "kind_fixtures"]

KIND_FIXTURES_DIR = DATA_DIR / "kind_fixtures"
KIND_FIXTURE_ORDER = (
    "drawing",
    "chart",
    "fact_table",
    "timeline",
    "map_layer",
    "stat_tiles",
    "map_sequence",
    "map_sequence_dhokra",
    "source_disagreements",
    "label_card",
    "swatch_cards",
    "swatch_pair",
    "voice",
    "stage_player",
    "dip_player",
    "reaction_player",
    "diagram",
    "equation_card",
    "structure_diagram",
    "molecule_3d",
    "material_cards",
    "experiment_lab",
    "choice_toggle",
    "choice_toggle_copper",
)


@cache
def _fixture_text(name: str) -> str:
    return (KIND_FIXTURES_DIR / f"{name}.json").read_text(encoding="utf-8")


def kind_fixtures() -> list[dict[str, Any]]:
    filed = sorted(path.stem for path in KIND_FIXTURES_DIR.glob("*.json"))
    if filed != sorted(KIND_FIXTURE_ORDER):
        raise ValueError(
            f"the kind fixtures on file {filed} are not the ordered list {sorted(KIND_FIXTURE_ORDER)}"
        )
    return [json.loads(_fixture_text(name)) for name in KIND_FIXTURE_ORDER]
