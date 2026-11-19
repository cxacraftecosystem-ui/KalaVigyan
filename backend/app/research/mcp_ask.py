from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from typing import Literal
from urllib.parse import urlencode

from .base import ContractModel
from .blocks import BlockBase
from .blocks_component import ComponentBlock
from .citations import AnswerSentence, SourceRef
from .coverage_answers import ConsultedField, consulted_fields
from .crafts import CraftRef
from .explainer import Explainer
from .explainer_versions import ExplainerVersionDocument
from .knowledge_api import ATTRIBUTION
from .vocabulary import AnswerLanguage, Depth, Discipline, ShownLevel, SourceType, TrustTier

__all__ = [
    "ANSWER_PAGE_PATH",
    "ANSWER_VIEW_MIME",
    "ANSWER_VIEW_URI",
    "ASK_SCHEMA_VERSION",
    "ASK_TIMEOUT_SECONDS",
    "AnswerView",
    "AskedAnswer",
    "AskedCraft",
    "AskedSection",
    "AskedSentence",
    "AskedSource",
    "PlacedComponent",
    "answer_url",
    "asked_answer",
]

ASK_SCHEMA_VERSION = 1
ASK_TIMEOUT_SECONDS = 600
ANSWER_VIEW_URI = "ui://kalavigyan/answer.html"
ANSWER_VIEW_MIME = "text/html;profile=mcp-app"
ANSWER_PAGE_PATH = "/ask"
READY = "READY"


class AskedCraft(ContractModel):
    slug: str
    name: str
    page_url: str


class AskedSentence(ContractModel):
    text: str
    level: ShownLevel
    claim_ids: list[str]
    source_ids: list[str]
    cites: list[int]


class PlacedComponent(ContractModel):
    label: str
    title: str
    kind: str
    url: str


class AskedSection(ContractModel):
    id: str
    field: Discipline
    title: str
    sentences: list[AskedSentence]
    components: list[PlacedComponent]


class AskedSource(ContractModel):
    number: int
    id: str
    kind: SourceType
    title: str
    authors: list[str]
    year: int | None
    doi: str | None
    url: str | None
    publisher: str | None
    licence: str | None
    attribution: str | None
    reliability: TrustTier | None


class AnswerView(ContractModel):
    resource_uri: str = ANSWER_VIEW_URI
    mime_type: str = ANSWER_VIEW_MIME


class AskedAnswer(ContractModel):
    schema_version: Literal[1] = ASK_SCHEMA_VERSION
    answer_id: uuid.UUID
    version: int
    question: str
    crafts: list[AskedCraft]
    depth: Depth
    language: AnswerLanguage
    opening: list[AskedSentence]
    sections: list[AskedSection]
    fields: list[ConsultedField]
    sources: list[AskedSource]
    follow_ups: list[str]
    answer_url: str
    view: AnswerView = AnswerView()
    attribution: str = ATTRIBUTION
    data_note: str


def answer_url(site: str, explainer_id: uuid.UUID, version: int) -> str:
    query = urlencode({"explainer": str(explainer_id), "version": str(version)})
    return f"{site.rstrip('/')}{ANSWER_PAGE_PATH}?{query}"


def asked_answer(document: ExplainerVersionDocument, *, site: str, data_note: str) -> AskedAnswer:
    explainer = document.explainer
    numbers = {source.id: number for number, source in enumerate(explainer.sources, start=1)}
    opening = explainer.lede.cited_sentences() if explainer.lede is not None else ()
    return AskedAnswer(
        answer_id=explainer.answer_id,
        version=document.mark.version,
        question=explainer.question,
        crafts=[_craft(craft, site) for craft in explainer.understood.crafts],
        depth=explainer.understood.depth,
        language=explainer.understood.language,
        opening=[_sentence(sentence, numbers) for sentence in opening],
        sections=_sections(explainer, numbers, site),
        fields=consulted_fields(explainer),
        sources=[_source(source, numbers[source.id]) for source in explainer.sources],
        follow_ups=list(explainer.follow_ups),
        answer_url=answer_url(site, document.mark.explainer_id, document.mark.version),
        data_note=data_note,
    )


def _sections(explainer: Explainer, numbers: Mapping[str, int], site: str) -> list[AskedSection]:
    return [
        AskedSection(
            id=section.id,
            field=section.discipline,
            title=section.title,
            sentences=[_sentence(sentence, numbers) for sentence in _sentences(section.blocks)],
            components=[
                _component(block, site) for block in section.blocks if isinstance(block, ComponentBlock)
            ],
        )
        for section in explainer.sections
        if section.state == READY
    ]


def _sentences(blocks: Iterable[BlockBase]) -> Iterable[AnswerSentence]:
    for block in blocks:
        yield from block.cited_sentences()


def _sentence(sentence: AnswerSentence, numbers: Mapping[str, int]) -> AskedSentence:
    sources = list(dict.fromkeys(citation.source_id for citation in sentence.citations))
    return AskedSentence(
        text=sentence.text,
        level=sentence.level,
        claim_ids=list(dict.fromkeys(citation.claim_id for citation in sentence.citations)),
        source_ids=sources,
        cites=sorted({numbers[source_id] for source_id in sources if source_id in numbers}),
    )


def _component(block: ComponentBlock, site: str) -> PlacedComponent:
    return PlacedComponent(
        label=block.label,
        title=block.title,
        kind=block.component_kind,
        url=f"{site.rstrip('/')}{block.href}",
    )


def _craft(craft: CraftRef, site: str) -> AskedCraft:
    return AskedCraft(slug=craft.slug, name=craft.name, page_url=f"{site.rstrip('/')}{craft.path}")


def _source(source: SourceRef, number: int) -> AskedSource:
    return AskedSource(number=number, **source.model_dump(by_alias=False))
