from __future__ import annotations

from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from app.research.base import ContractModel
from app.research.subject_keys import TermKey
from app.research.term_marking import GlossaryEntry, TermMarker

from .layers import LAYERS_BY_ID

__all__ = ["LAYER_TERMS_FILE", "LayerTerm", "LayerTerms", "layer_marker", "layer_terms"]

LAYER_TERMS_FILE = Path(__file__).with_name("layer_terms.json")
ABOUT_MIN_CHARS = 40


class LayerTerm(ContractModel):
    key: TermKey
    label: str = Field(min_length=1, max_length=120)
    layer: str = Field(min_length=1)
    aliases: list[str]
    local_names: list[str]

    def glossary_entry(self) -> GlossaryEntry:
        return GlossaryEntry(key=self.key, surfaces=(self.label, *self.aliases, *self.local_names))


class LayerTerms(ContractModel):
    schema_version: Literal[1]
    about: str = Field(min_length=ABOUT_MIN_CHARS)
    terms: list[LayerTerm] = Field(min_length=1)

    @model_validator(mode="after")
    def _one_term_per_registry_layer(self) -> Self:
        layers = [term.layer for term in self.terms]
        unknown = sorted(set(layers) - set(LAYERS_BY_ID))
        if unknown:
            raise ValueError(f"layer terms name layers the registry does not hold: {', '.join(unknown)}")
        if len(set(layers)) != len(layers) or set(layers) != set(LAYERS_BY_ID):
            raise ValueError("every registry layer has exactly one term")
        keys = [term.key for term in self.terms]
        if len(set(keys)) != len(keys):
            raise ValueError("each layer term key is used once")
        return self

    def layer_of(self) -> Mapping[str, str]:
        return MappingProxyType({term.key: term.layer for term in self.terms})


@lru_cache(maxsize=1)
def layer_terms() -> LayerTerms:
    return LayerTerms.model_validate_json(LAYER_TERMS_FILE.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def layer_marker() -> TermMarker:
    return TermMarker([term.glossary_entry() for term in layer_terms().terms])
