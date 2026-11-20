from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Any

from app.core.errors import InvalidInput

from .base import ContractModel
from .component_specs_blocks import SPEC_MODELS_BLOCKS
from .component_specs_data import SPEC_MODELS_DATA
from .component_specs_general import SPEC_MODELS_GENERAL
from .component_specs_plates import SPEC_MODELS_PLATES
from .component_specs_science import SPEC_MODELS_SCIENCE
from .component_specs_tools import SPEC_MODELS_TOOLS

__all__ = ["SPEC_MODELS", "checked_spec"]

SPEC_GROUPS: tuple[Mapping[str, type[ContractModel]], ...] = (
    SPEC_MODELS_PLATES,
    SPEC_MODELS_DATA,
    SPEC_MODELS_SCIENCE,
    SPEC_MODELS_TOOLS,
    SPEC_MODELS_BLOCKS,
    SPEC_MODELS_GENERAL,
)


def _joined() -> Mapping[str, type[ContractModel]]:
    joined: dict[str, type[ContractModel]] = {}
    for group in SPEC_GROUPS:
        twice = set(joined) & set(group)
        if twice:
            raise InvalidInput(f"Two spec groups model the kinds {sorted(twice)}")
        joined.update(group)
    return MappingProxyType(joined)


SPEC_MODELS = _joined()


def checked_spec(kind: str, spec: Mapping[str, Any]) -> ContractModel:
    model = SPEC_MODELS.get(kind)
    if model is None:
        raise InvalidInput(f"No spec model draws the component kind {kind!r}")
    return model.model_validate(spec)
