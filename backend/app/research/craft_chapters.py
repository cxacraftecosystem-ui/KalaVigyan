from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .chapter_keys import CHAPTER_KEYS, CHAPTER_TITLES, DISCIPLINE_CHAPTERS
from .citations import AnswerSentence, Citation
from .craft_origins import GENERATED_KINDS, ORIGIN_BASES, AskedQuestion, ItemOrigin
from .craft_parts import PagePart, PagePlate
from .explainer import BUILT_BLOCK_KINDS, BUILT_FIGURE_KINDS, Block
from .media_refs import MediaRef

__all__ = [
    "BORROWED_SCOPES",
    "CHAPTER_KEYS",
    "CHAPTER_TITLES",
    "DISCIPLINE_CHAPTERS",
    "FIGURE_KINDS",
    "FIGURE_TITLES",
    "GENERATED_KINDS",
    "KIN_ITEM_KINDS",
    "ORIGIN_BASES",
    "PAGE_BLOCK_KINDS",
    "AskedQuestion",
    "Borrowed",
    "Chapter",
    "ChapterItem",
    "FigureHead",
    "ItemOrigin",
    "figure_title",
]

FIGURE_KINDS = ("FIGURE", "TABLE")
BORROWED_SCOPES = ("FAMILY", "KIN")
NOT_ON_THE_PAGE = frozenset({"quiz", "compare", "map_layer", "component"})
PAGE_BLOCK_KINDS = (
    frozenset(BUILT_BLOCK_KINDS) - NOT_ON_THE_PAGE | frozenset(BUILT_FIGURE_KINDS) | {"artisan_voice"}
)
KIN_ITEM_KINDS = frozenset({"relatives"})
FIGURE_TITLES: Mapping[str, str] = MappingProxyType(
    {
        "process_ladder": "How {craft} is made, in {stages} stages",
        "reaction_player": "{mechanism}, step by step",
        "molecule_3d": "{name} in three dimensions",
        "region_story": "Where {craft} is made: {places}",
        "climate_risk": "{finding}",
        "seasons": "The working year of {craft}",
        "timeline_map": "{craft} in time and place, {first} to {last}",
        "market_gi": "The market and GI record of {craft}",
        "key_facts": "Key facts",
        "indigo_vat": "The indigo vat",
        "mordant_bath": "The mordant bath",
        "lost_wax": "Lost-wax casting",
        "firing": "The firing",
    }
)
TABLE_KINDS = frozenset({"market_gi", "key_facts"})
FIELD = re.compile(r"\{(\w+)\}")


class Borrowed(ContractModel):
    scope: Literal[*BORROWED_SCOPES]
    slug: str = Field(min_length=1)
    label: str = Field(min_length=1)


class FigureHead(ContractModel):
    kind: Literal[*FIGURE_KINDS]
    title: str = Field(min_length=1, max_length=300)
    borrowed: list[Borrowed]


class ChapterItem(ContractModel):
    block: Block | None
    part: PagePart | None
    figure: FigureHead | None
    origin: ItemOrigin | None
    piece_id: uuid.UUID | None

    @model_validator(mode="after")
    def _a_block_or_a_part(self) -> Self:
        if (self.block is None) == (self.part is None):
            raise ValueError("a chapter item is an answer block or a page part, never both")
        if self.block is not None and self.block.kind not in PAGE_BLOCK_KINDS:
            raise ValueError(
                f"block {self.block.id} is a {self.block.kind} block, which a page does not show"
            )
        return self

    @property
    def kind(self) -> str:
        return self.block.kind if self.block is not None else str(self.part.kind) if self.part else ""

    @property
    def kin(self) -> bool:
        return self.kind in KIN_ITEM_KINDS

    def sentences(self) -> Iterator[AnswerSentence]:
        if self.block is not None:
            yield from self.block.cited_sentences()
        if self.part is not None:
            yield from self.part.cited_sentences()
            for plate in self.part.plates():
                yield from plate.sentences

    def citations(self) -> Iterator[Citation]:
        if self.block is not None:
            yield from self.block.citations()
        if self.part is not None:
            yield from self.part.citations()

    def cited_source_ids(self) -> list[str]:
        if self.block is not None:
            return self.block.cited_source_ids()
        return self.part.cited_source_ids() if self.part is not None else []

    def shown_media(self) -> Iterator[MediaRef]:
        if self.part is not None:
            yield from self.part.shown_media()
        block = self.block
        for item in getattr(block, "items", None) or []:
            yield item.media
        for level in getattr(block, "levels", None) or []:
            if getattr(level, "media", None) is not None:
                yield level.media
        for stage in getattr(block, "stages", None) or []:
            for picture in getattr(stage, "pictures", None) or []:
                yield picture.media


class Chapter(ContractModel):
    key: Literal[*CHAPTER_KEYS]
    title: str = Field(min_length=1, max_length=120)
    opener: PagePlate | None
    items: list[ChapterItem] = Field(min_length=1)

    def plates(self) -> Iterator[PagePlate]:
        if self.opener is not None:
            yield self.opener

    def sentences(self) -> Iterator[AnswerSentence]:
        for plate in self.plates():
            yield from plate.sentences
        for item in self.items:
            yield from item.sentences()


def figure_title(kind: str, values: Mapping[str, object]) -> FigureHead | None:
    template = FIGURE_TITLES.get(kind)
    if template is None:
        return None
    wanted = FIELD.findall(template)
    if any(values.get(name) in (None, "") for name in wanted):
        return None
    return FigureHead(
        kind="TABLE" if kind in TABLE_KINDS else "FIGURE",
        title=template.format(**{name: values[name] for name in wanted}),
        borrowed=[],
    )
