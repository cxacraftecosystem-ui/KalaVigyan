from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator, Mapping, Sequence
from itertools import pairwise
from typing import Any, ClassVar, Literal, Self

from pydantic import AwareDatetime, Field, model_validator
from pydantic.alias_generators import to_camel

from app.models.enums import EVIDENCE_LEVELS, IMAGE_RELEVANCE

from .base import ContractModel, absent, empty
from .citations import AnswerSentence, Citation
from .colours import ColourWord
from .crafts import CraftRef
from .media_refs import MediaRef
from .quotes import quote_occurs
from .terms import TermSpan, span_problems
from .vocabulary import FACT_LEVELS, MaterialKind, MaterialRole, ShownLevel, StageType, weakest_level

__all__ = [
    "AFTER_COLOURS_MAX",
    "AFTER_TEXT_MAX_CHARS",
    "BLOCK_ID_MAX_CHARS",
    "BLOCK_ID_PATTERN",
    "IMAGES_MAX",
    "IMAGE_RELEVANCE",
    "SENTENCE",
    "BlockBase",
    "DifferRead",
    "DifferReading",
    "ExplainerSentence",
    "ImageItem",
    "ImagesBlock",
    "LadderCondition",
    "LadderMaterial",
    "LadderStage",
    "LadderTool",
    "ProcessLadderBlock",
    "ProseBlock",
    "ReuseMarker",
    "SentenceSpec",
    "StageAfter",
    "StagePicture",
    "named_in",
    "require_facts",
    "require_findings",
    "sentences_in_payload",
    "stated_texts",
    "with_sentences_in_payload",
]

BLOCK_ID_MAX_CHARS = 80
BLOCK_ID_PATTERN = r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$"
IMAGES_MAX = 8
AFTER_TEXT_MAX_CHARS = 120
AFTER_COLOURS_MAX = 3
DIFFER_WEIGHT_VALUES = (1, 2, 3)

SENTENCE = "sentence"

ImageRelevance = Literal[*IMAGE_RELEVANCE]
SentenceChange = Callable[[Mapping[str, Any]], dict[str, Any]]
SentenceSpec = tuple[tuple[str, Any], ...]


class ReuseMarker(ContractModel):
    piece_id: uuid.UUID
    stored_at: AwareDatetime


def _unflagged(value: object) -> bool:
    return value is False


class ExplainerSentence(AnswerSentence):
    terms: list[TermSpan]
    sources_differ: bool = Field(default=False, exclude_if=_unflagged)

    @model_validator(mode="after")
    def _terms_mark_the_shown_text(self) -> Self:
        problems = span_problems(self.text, self.terms)
        if problems:
            raise ValueError(f"sentence {self.id}: {'; '.join(problems)}")
        return self


class BlockBase(ContractModel):
    SENTENCES: ClassVar[SentenceSpec] = ()

    id: str = Field(min_length=1, max_length=BLOCK_ID_MAX_CHARS, pattern=BLOCK_ID_PATTERN)
    kind: str
    version: int
    reuse: ReuseMarker | None

    def cited_sentences(self) -> Iterator[AnswerSentence]:
        yield from _model_sentences(self, self.SENTENCES)

    def shown_labels(self) -> list[str]:
        return []

    def citations(self) -> Iterator[Citation]:
        for sentence in self.cited_sentences():
            yield from sentence.citations

    def direct_source_ids(self) -> Iterator[str]:
        yield from ()

    def illustrated_claim_ids(self) -> set[str]:
        return set()

    def cited_claim_ids(self) -> set[str]:
        return {citation.claim_id for citation in self.citations()}

    def cited_source_ids(self) -> list[str]:
        ordered = dict.fromkeys(citation.source_id for citation in self.citations())
        ordered.update(dict.fromkeys(self.direct_source_ids()))
        return list(ordered)

    def cites_datasets(self) -> bool:
        return False

    @model_validator(mode="after")
    def _every_block_carries_its_evidence(self) -> Self:
        if not (self.cited_source_ids() or self.illustrated_claim_ids() or self.cites_datasets()):
            raise ValueError(f"block {self.id} cites nothing, so it is not shown")
        return self


class ProseBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("sentences", [SENTENCE]),)

    kind: Literal["prose"]
    version: Literal[1]
    sentences: list[ExplainerSentence] = Field(min_length=1)

    @model_validator(mode="after")
    def _facts_only_once_each(self) -> Self:
        require_facts(self.id, self.sentences)
        return self


class LadderMaterial(ContractModel):
    material_id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)
    kind: MaterialKind
    role: MaterialRole
    citations: list[Citation] = Field(min_length=1)
    botanical_name: str | None = Field(default=None, min_length=1, max_length=200, exclude_if=absent)
    pubchem_cid: int | None = Field(default=None, ge=1, exclude_if=absent)
    local_names: list[str] = Field(default_factory=list, exclude_if=empty)


class StageAfter(ContractModel):
    text: str = Field(min_length=1, max_length=AFTER_TEXT_MAX_CHARS)
    colours: list[ColourWord] = Field(default_factory=list, max_length=AFTER_COLOURS_MAX)
    citations: list[Citation] = Field(min_length=1)

    @model_validator(mode="after")
    def _each_colour_once(self) -> Self:
        if len(set(self.colours)) != len(self.colours):
            raise ValueError(f"the cloth after a stage names each colour once: {self.text!r}")
        return self


class LadderTool(ContractModel):
    tool_id: uuid.UUID
    name: str = Field(min_length=1, max_length=300)
    local_names: list[str]
    citations: list[Citation] = Field(min_length=1)


class DifferRead(ContractModel):
    sentence: ExplainerSentence | None
    shown_in: str | None

    @model_validator(mode="after")
    def _a_sentence_or_where_it_is_shown(self) -> Self:
        if (self.sentence is None) == (self.shown_in is None):
            raise ValueError("a reading is its sentence, or the id of the sentence that already shows it")
        return self


class DifferReading(ContractModel):
    key: str = Field(min_length=1, max_length=80)
    about: str = Field(min_length=1, max_length=300)
    weight: Literal[*DIFFER_WEIGHT_VALUES]
    readings: list[DifferRead] = Field(min_length=2)

    def sentences(self) -> Iterator[ExplainerSentence]:
        yield from (read.sentence for read in self.readings if read.sentence is not None)


class StagePicture(ContractModel):
    media: MediaRef
    caption: str = Field(min_length=1, max_length=300)
    stand_in: str | None


class LadderCondition(ContractModel):
    label: str = Field(min_length=1, max_length=120)
    stated: str = Field(min_length=1, max_length=200)
    citations: list[Citation] = Field(min_length=1)

    @model_validator(mode="after")
    def _stated_as_its_source_says(self) -> Self:
        if not any(c.quote and quote_occurs(self.stated, c.quote) for c in self.citations):
            raise ValueError(f"condition {self.label!r} states {self.stated!r}, which no cited quote says")
        return self


class LadderStage(ContractModel):
    stage_id: uuid.UUID
    ordinal: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=300)
    stage_type: StageType
    level: ShownLevel
    sentences: list[ExplainerSentence] = Field(min_length=1)
    materials: list[LadderMaterial]
    conditions: list[LadderCondition]
    reaction_ids: list[uuid.UUID]
    local_name: str | None = Field(default=None, min_length=1, max_length=200, exclude_if=absent)
    unnumbered: bool | None = Field(default=None, exclude_if=absent)
    after: StageAfter | None = Field(default=None, exclude_if=absent)
    why: ExplainerSentence | None = Field(default=None, exclude_if=absent)
    tools: list[LadderTool] = Field(default_factory=list, exclude_if=empty)
    differs: list[DifferReading] = Field(default_factory=list, exclude_if=empty)
    pictures: list[StagePicture] = Field(default_factory=list, exclude_if=empty)

    @model_validator(mode="after")
    def _level_follows_the_stage_sentences(self) -> Self:
        require_facts(f"stage {self.stage_id}", self.sentences)
        expected = weakest_level(sentence.level for sentence in self.sentences)
        if self.level != expected:
            raise ValueError(f"stage {self.stage_id} is {expected}, not {self.level}")
        if len(set(self.reaction_ids)) != len(self.reaction_ids):
            raise ValueError(f"stage {self.stage_id} links each reaction once")
        return self

    def citations(self) -> Iterator[Citation]:
        for sentence in self.added_sentences():
            yield from sentence.citations
        for part in (*self.materials, *self.conditions, *self.tools, *([self.after] if self.after else [])):
            yield from part.citations

    def added_sentences(self) -> Iterator[ExplainerSentence]:
        yield from self.sentences
        if self.why is not None:
            yield self.why
        for differ in self.differs:
            yield from differ.sentences()


class ProcessLadderBlock(BlockBase):
    SENTENCES: ClassVar[SentenceSpec] = (("stages", [(("sentences", [SENTENCE]),)]),)

    kind: Literal["process_ladder"]
    version: Literal[1]
    craft: CraftRef
    process_id: uuid.UUID
    stages: list[LadderStage] = Field(min_length=1)

    @model_validator(mode="after")
    def _stages_climb_in_order(self) -> Self:
        ordinals = [stage.ordinal for stage in self.stages]
        if any(a >= b for a, b in pairwise(ordinals)):
            raise ValueError(f"ladder {self.id} lists its stages by rising ordinal")
        return self

    def citations(self) -> Iterator[Citation]:
        for stage in self.stages:
            yield from stage.citations()

    def cited_sentences(self) -> Iterator[AnswerSentence]:
        for stage in self.stages:
            yield from stage.added_sentences()


class ImageItem(ContractModel):
    media: MediaRef
    claim_ids: list[uuid.UUID] = Field(min_length=1)
    relevance: ImageRelevance

    @model_validator(mode="after")
    def _claims_once_each(self) -> Self:
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError(f"image {self.media.id} names each claim it illustrates once")
        return self


class ImagesBlock(BlockBase):
    kind: Literal["images"]
    version: Literal[1]
    items: list[ImageItem] = Field(min_length=1, max_length=IMAGES_MAX)

    @model_validator(mode="after")
    def _each_image_once(self) -> Self:
        ids = [item.media.id for item in self.items]
        if len(set(ids)) != len(ids):
            raise ValueError(f"images {self.id} shows each image once")
        return self

    def illustrated_claim_ids(self) -> set[str]:
        return {str(claim_id) for item in self.items for claim_id in item.claim_ids}

    def shown_labels(self) -> list[str]:
        return [item.media.title for item in self.items]


def stated_texts(sentence: AnswerSentence) -> list[str]:
    return [sentence.original or sentence.text, *(c.quote for c in sentence.citations if c.quote)]


def named_in(name: str, sentence: AnswerSentence) -> bool:
    return any(quote_occurs(name.casefold(), text.casefold()) for text in stated_texts(sentence))


def require_facts(owner: str, sentences: Sequence[ExplainerSentence]) -> None:
    require_findings(owner, sentences)
    if any(sentence.level not in FACT_LEVELS for sentence in sentences):
        raise ValueError(f"{owner} states facts only; a hypothesis is an open question")


def require_findings(owner: str, sentences: Sequence[ExplainerSentence]) -> None:
    ids = [sentence.id for sentence in sentences]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{owner} lists each sentence once")
    if any(sentence.level not in EVIDENCE_LEVELS for sentence in sentences):
        raise ValueError(f"{owner} shows stored findings only, each at its stored level")


def sentences_in_payload(payload: Mapping[str, Any], spec: SentenceSpec) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []

    def kept(sentence: Mapping[str, Any]) -> dict[str, Any]:
        found.append(sentence)
        return dict(sentence)

    with_sentences_in_payload(payload, spec, kept)
    return found


def with_sentences_in_payload(
    payload: Mapping[str, Any], spec: SentenceSpec, change: SentenceChange
) -> dict[str, Any]:
    return _changed_object(payload, spec, change)


def _model_sentences(owner: Any, spec: SentenceSpec) -> Iterator[AnswerSentence]:
    for name, node in spec:
        yield from _node_sentences(getattr(owner, name), node)


def _node_sentences(value: Any, node: Any) -> Iterator[AnswerSentence]:
    if value is None:
        return
    if node == SENTENCE:
        yield value
    elif isinstance(node, list):
        for item in value:
            yield from _node_sentences(item, node[0])
    else:
        yield from _model_sentences(value, node)


def _changed_object(value: Mapping[str, Any], spec: SentenceSpec, change: SentenceChange) -> dict[str, Any]:
    changed = dict(value)
    for name, node in spec:
        key = to_camel(name)
        if key in changed:
            changed[key] = _changed_node(changed[key], node, change)
    return changed


def _changed_node(value: Any, node: Any, change: SentenceChange) -> Any:
    if value is None:
        return None
    if node == SENTENCE:
        return change(value)
    if isinstance(node, list):
        return [_changed_node(item, node[0], change) for item in value]
    return _changed_object(value, node, change)
