from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .citations import SourceRef
from .explainer import Block

__all__ = [
    "ANSWER_BLOCK_KIND",
    "BLOCK_FIGURE_KINDS",
    "SPEC_MODELS_BLOCKS",
    "AnswerBlockSpec",
    "BlockFigure",
    "BlockSource",
]

ANSWER_BLOCK_KIND = "answer_block"
BLOCK_FIGURE_KINDS = ("FIGURE", "TABLE")
SOURCE_KEY = r"^g[1-9][0-9]*$"
FIGURE_TITLE_MAX = 300


class BlockSource(ContractModel):
    key: str = Field(pattern=SOURCE_KEY)
    ref: SourceRef


class BlockFigure(ContractModel):
    kind: Literal[*BLOCK_FIGURE_KINDS]
    number: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=FIGURE_TITLE_MAX)


class AnswerBlockSpec(ContractModel):
    block: Block
    figure: BlockFigure | None = None
    sources: list[BlockSource] = Field(default_factory=list)

    @model_validator(mode="after")
    def _every_cited_source_listed_once(self) -> Self:
        ids = [source.ref.id for source in self.sources]
        keys = [source.key for source in self.sources]
        if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
            raise ValueError(f"block {self.block.id} lists each source once, under its own key")
        missing = sorted(set(self.block.cited_source_ids()) - set(ids))
        if missing:
            raise ValueError(f"block {self.block.id} cites sources it does not list: {missing}")
        return self


SPEC_MODELS_BLOCKS: Mapping[str, type[ContractModel]] = MappingProxyType({ANSWER_BLOCK_KIND: AnswerBlockSpec})
