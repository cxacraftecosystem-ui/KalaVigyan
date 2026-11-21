from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel

from app.core.errors import InvalidInput
from app.models.component_kinds import AUTHORED_ART_KINDS, AUTHORED_SCRIPT_KINDS, PAGE_TOOL_KINDS, PIECE_KINDS

from .base import ContractModel
from .component_specs_blocks import SPEC_MODELS_BLOCKS
from .component_specs_data import SPEC_MODELS_DATA
from .component_specs_either import SPEC_MODELS_EITHER, form_model
from .component_specs_general import SPEC_MODELS_GENERAL
from .component_specs_plates import SPEC_MODELS_PLATES
from .component_specs_science import SPEC_MODELS_SCIENCE
from .component_specs_tools import SPEC_MODELS_TOOLS
from .why_here import SPEC_MODELS_WHY_HERE

__all__ = [
    "CONTRIBUTABLE_KINDS",
    "SPEC_MODELS",
    "checked_spec",
    "not_contributable",
]

SPEC_GROUPS: tuple[Mapping[str, type[ContractModel]], ...] = (
    SPEC_MODELS_PLATES,
    SPEC_MODELS_DATA,
    SPEC_MODELS_SCIENCE,
    SPEC_MODELS_TOOLS,
    SPEC_MODELS_BLOCKS,
    SPEC_MODELS_GENERAL,
    SPEC_MODELS_WHY_HERE,
)
PAGE_TOOL = "the site builds the {kind} of every page from its data, so it is never delivered"
AUTHORED_ART = (
    "a {kind} draws an authored page's own art; give pictures with give_pictures and the site places them"
)
AUTHORED_SCRIPT = (
    "a {kind} runs an authored page's own script; deliver a drawing, a timeline or a map_layer instead"
)
WITHHELD = (*PAGE_TOOL_KINDS, *AUTHORED_ART_KINDS, *AUTHORED_SCRIPT_KINDS)


def _joined() -> Mapping[str, type[BaseModel]]:
    joined: dict[str, type[BaseModel]] = {}
    for group in SPEC_GROUPS:
        twice = set(joined) & set(group)
        if twice:
            raise InvalidInput(f"Two spec groups model the kinds {sorted(twice)}")
        joined.update(group)
    return MappingProxyType({**joined, **SPEC_MODELS_EITHER})


SPEC_MODELS = _joined()
CONTRIBUTABLE_KINDS = tuple(
    sorted(kind for kind in SPEC_MODELS if kind in PIECE_KINDS and kind not in WITHHELD)
)


def checked_spec(kind: str, spec: Mapping[str, Any]) -> ContractModel:
    model = form_model(kind, spec) or SPEC_MODELS.get(kind)
    if model is None or not issubclass(model, ContractModel):
        raise InvalidInput(f"No spec model draws the component kind {kind!r}")
    return model.model_validate(spec)


def not_contributable(kind: str) -> str | None:
    if kind in PAGE_TOOL_KINDS:
        return PAGE_TOOL.format(kind=kind)
    if kind in AUTHORED_ART_KINDS:
        return AUTHORED_ART.format(kind=kind)
    if kind in AUTHORED_SCRIPT_KINDS:
        return AUTHORED_SCRIPT.format(kind=kind)
    return None
