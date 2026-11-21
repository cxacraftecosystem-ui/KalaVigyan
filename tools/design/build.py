from __future__ import annotations

import json
from typing import Any

from design.build_colour import colour_tokens, plate_tokens, specimen_tokens
from design.build_data import chart_tokens, family_tokens, map_tokens, ramp_tokens
from design.build_type import space_tokens, type_tokens
from design.checks import validate
from design.css import css
from design.material_lists import python_list, typescript_list
from design.materials import material_names
from design.system import System
from design.tailwind import tailwind_ts

__all__ = ["build", "render"]

PASSED_THROUGH = {
    "control": "control",
    "radius": "radius",
    "border": "border",
    "focus": "focus",
    "shadow": "shadow",
    "motion": "motion",
    "z": "zIndex",
    "breakpoints": "breakpoints",
    "grid": "grid",
    "image": "image",
}


def build(system: System) -> dict[str, Any]:
    data = system.data
    dataviz = {
        "chart": chart_tokens(system),
        "ramps": ramp_tokens(system),
        "categorical": family_tokens(system),
        "map": map_tokens(system),
        "hatch": data["hatch"],
    }
    tokens = {
        "meta": data["meta"],
        "color": colour_tokens(system),
        "grain": data["grain"],
        "specimen": specimen_tokens(system),
        "plate": plate_tokens(system),
        "dataviz": dataviz,
        "type": type_tokens(system),
        "space": space_tokens(system),
    }
    tokens.update({key: data[source] for key, source in PASSED_THROUGH.items()})
    return tokens


def render(system: System) -> tuple[dict[str, str], list[str]]:
    tokens = build(system)
    outputs = {
        "tokens.json": json.dumps(tokens, ensure_ascii=False, indent=2) + "\n",
        "tokens.css": css(tokens, system),
        "tailwind.config.ts": tailwind_ts(tokens),
        "depicted_materials.py": python_list(material_names(system.materials)),
        "depictedMaterials.ts": typescript_list(material_names(system.materials)),
    }
    return outputs, validate(tokens, system)
