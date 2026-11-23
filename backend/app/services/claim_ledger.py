from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator, Mapping, Sequence
from types import MappingProxyType
from typing import Any

from pydantic import ValidationError

from app.data.craft_text import fold
from app.research.blocks import SENTENCE, BlockBase, SentenceSpec
from app.research.blocks_people import expert_pairing_problems
from app.research.explainer import BLOCK_MODELS, Block

from .ledger_payloads import (
    Payload,
    Repeat,
    blocked_media,
    claims_of,
    compared_rows,
    fresh_nodes,
    independent,
    kept_sentences,
    leveled_stages,
    picture_keys,
    sentence_keys,
    zoomed_levels,
)
from .restatements import Said, restates_any, said
from .source_merge import SourceMerge

__all__ = [
    "ANCHORED_KINDS",
    "COVERED_NOTE",
    "EXPERT_KIND",
    "LADDER_KIND",
    "ONCE_PER_ANSWER_KINDS",
    "RESTATING_KINDS",
    "SINGLE_BLOCK_KINDS",
    "WHAT_IF_SHARED_OPTIONS",
    "ClaimLedger",
    "admission_batches",
    "sentence_keys",
]

logger = logging.getLogger(__name__)

COVERED_NOTE = "Already covered in this answer."
EXPERT_KIND = "expert_view"
LADDER_KIND = "process_ladder"
SIMULATION_KIND = "simulation"
WHAT_IF_KIND = "what_if"
WHAT_IF_SHARED_OPTIONS = 2
SINGLE_BLOCK_KINDS = frozenset({"prose", "process_ladder", "images"})
ONCE_PER_ANSWER_KINDS = frozenset({"region_story", "seasons", "supply_map", "zoom_story"})

WhatIfKey = tuple[str | None, frozenset[str]]

RESTATING_KINDS: Mapping[str, SentenceSpec] = MappingProxyType(
    {
        "prose": BLOCK_MODELS["prose"].SENTENCES,
        "material_card": BLOCK_MODELS["material_card"].SENTENCES,
        EXPERT_KIND: (("take", [SENTENCE]),),
    }
)
ANCHORED_KINDS = frozenset(
    kind for kind, model in BLOCK_MODELS.items() if model.SENTENCES and kind not in RESTATING_KINDS
)


def admission_batches(blocks: Sequence[Block]) -> Iterator[list[Block]]:
    batch: list[Block] = []
    for block in blocks:
        if block.kind not in SINGLE_BLOCK_KINDS:
            batch.append(block)
            continue
        if batch:
            yield batch
            batch = []
        yield [block]
    if batch:
        yield batch


class ClaimLedger:
    def __init__(self) -> None:
        self.sources = SourceMerge()
        self._texts: set[str] = set()
        self._claims: set[str] = set()
        self._said: list[Said] = []
        self._materials: set[str] = set()
        self._molecules: set[int] = set()
        self._what_ifs: list[WhatIfKey] = []
        self._concepts: set[str] = set()
        self._pictures: set[str] = set()
        self._explained: set[str] = set()
        self._section_claims: dict[str, set[str]] = {}
        self._once: set[str] = set()
        self._differences: set[frozenset[frozenset[str]]] = set()

    def admit(
        self, section_id: str, blocks: Sequence[Block], sources: Mapping[str, Mapping[str, Any]]
    ) -> list[Block]:
        payloads = self._merged(blocks, sources)
        experts = {n: payloads[n] for n, block in enumerate(blocks) if block.kind == EXPERT_KIND}
        admitted: dict[int, Block] = {}
        for n in sorted(range(len(blocks)), key=lambda n: (blocks[n].kind not in ANCHORED_KINDS, n)):
            if blocks[n].kind != EXPERT_KIND:
                block = self._admitted(section_id, blocks[n].kind, payloads[n])
                admitted.update({n: block} if block is not None else {})
            elif n == min(experts):
                admitted.update(self._experts(section_id, experts))
        return [admitted[n] for n in sorted(admitted)]

    def admit_lede[Opening: BlockBase](
        self, block: Opening, sources: Mapping[str, Mapping[str, Any]]
    ) -> Opening:
        (payload,) = self._merged([block], sources)
        lede = type(block).model_validate(payload)
        for sentence in lede.cited_sentences():
            self._texts.update(sentence_keys(sentence.text, sentence.original))
        return lede

    def merged_sentence(
        self, sentence: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
    ) -> Payload:
        for citation in sentence.get("citations", []):
            self.sources.register(citation["sourceId"], sources.get(citation["sourceId"]))
        return self.sources.remapped(dict(sentence))

    def _merged(self, blocks: Sequence[BlockBase], sources: Mapping[str, Mapping[str, Any]]) -> list[Payload]:
        for block in blocks:
            for source_id in block.cited_source_ids():
                self.sources.register(source_id, sources.get(source_id))
        return [
            self.sources.remapped(block.model_dump(mode="json", by_alias=True, exclude_unset=True))
            for block in blocks
        ]

    def _admitted(self, section_id: str, kind: str, payload: Payload) -> Block | None:
        if kind == "images":
            return self._picture(section_id, payload)
        if not self._first_of_its_kind(kind, payload):
            logger.info("block %s shows what this answer already shows", payload["id"])
            return None
        block = next((block for block in self._kept_forms(kind, payload) if block is not None), None)
        if block is not None:
            self._record(section_id, block)
        return block

    def _first_of_its_kind(self, kind: str, payload: Payload) -> bool:
        if kind == "material_card":
            return not _material_keys(payload) & self._materials
        if kind == "molecule_3d":
            return payload["pubchemCid"] not in self._molecules
        if kind == SIMULATION_KIND:
            return fold(payload["concept"]) not in self._explained
        if kind == WHAT_IF_KIND:
            return not any(_same_what_if(_what_if_key(payload), shown) for shown in self._what_ifs)
        return kind not in self._once

    def _kept_forms(self, kind: str, payload: Payload) -> Iterator[Block | None]:
        if kind in RESTATING_KINDS:
            kept = kept_sentences(payload, RESTATING_KINDS[kind], self._restating_repeat())
            yield _validated(kind, kept) if kept is not None else None
            return
        repeats = (
            (self._anchored_repeat(),)
            if kind == LADDER_KIND
            else (self._story_repeat(), self._story_repeat(spared=1), self._anchored_repeat())
        )
        for repeat in repeats:
            kept = self._without_repeats(kind, payload, repeat)
            yield _validated(kind, kept) if kept is not None else None

    def _without_repeats(self, kind: str, payload: Payload, repeat: Repeat) -> Payload | None:
        if kind == "compare":
            return compared_rows(payload, repeat)
        kept = kept_sentences(payload, BLOCK_MODELS[kind].SENTENCES, repeat)
        return None if kept is None else self._repaired(kind, kept)

    def _repaired(self, kind: str, payload: Payload) -> Payload:
        if kind == "concept_graph":
            return fresh_nodes(payload, self._concepts)
        if kind == "zoom_story":
            return zoomed_levels(payload, self._pictures)
        if kind == LADDER_KIND:
            return leveled_stages(self._thinned_stages(payload))
        return payload

    def _thinned_stages(self, payload: Payload) -> Payload:
        shown = tuple(self._said)
        stages = []
        for stage in payload["stages"]:
            fresh = [sentence for sentence in stage["sentences"] if not restates_any(said(sentence), shown)]
            stages.append({**stage, "sentences": fresh or stage["sentences"][:1]})
        return {**payload, "stages": stages}

    def _restating_repeat(self) -> Repeat:
        seen = set(self._texts)
        shown = list(self._said)

        def repeat(sentence: Mapping[str, Any]) -> bool:
            keys = sentence_keys(sentence["text"], sentence.get("original"))
            claims = claims_of(sentence)
            stated = said(sentence)
            if keys & seen or (claims and claims <= self._claims) or restates_any(stated, shown):
                return True
            seen.update(keys)
            shown.append(stated)
            return False

        return repeat

    def _anchored_repeat(self) -> Repeat:
        seen = frozenset(self._texts)
        return lambda sentence: bool(sentence_keys(sentence["text"], sentence.get("original")) & seen)

    def _story_repeat(self, *, spared: int = 0) -> Repeat:
        exact = self._anchored_repeat()
        shown = tuple(self._said)
        left = [spared]

        def repeat(sentence: Mapping[str, Any]) -> bool:
            if exact(sentence):
                return True
            if not restates_any(said(sentence), shown):
                return False
            left[0] -= 1
            return left[0] < 0

        return repeat

    def _experts(self, section_id: str, payloads: Mapping[int, Payload]) -> dict[int, Block]:
        kept, differing = self._new_takes(payloads)
        views = self._paired_views(kept, differing)
        for view in views.values():
            self._record(section_id, view)
        return views

    def _new_takes(self, payloads: Mapping[int, Payload]) -> tuple[dict[int, Payload], set[int]]:
        kept: dict[int, Payload] = {}
        differing: set[int] = set()
        for n, payload in payloads.items():
            stripped = kept_sentences(payload, RESTATING_KINDS[EXPERT_KIND], self._restating_repeat())
            if stripped is not None and stripped["take"]:
                kept[n] = stripped
                self._record_sentences(stripped["take"])
            elif payload["differs"]:
                kept[n] = payload
                differing.add(n)
        return kept, differing

    def _paired_views(self, kept: Mapping[int, Payload], differing: set[int]) -> dict[int, Block]:
        repeated = self._repeated_pairs(kept.values())
        paired = _paired(kept, repeated)
        idle = {n for n in differing if not paired[n]["differs"]}
        if idle:
            paired = _paired({n: p for n, p in kept.items() if n not in idle}, repeated)
        views = _expert_views(paired)
        if expert_pairing_problems(list(views.values())):
            plain = {n: p for n, p in kept.items() if n not in differing}
            views = _expert_views({n: _paired_within(p, set(), set()) for n, p in plain.items()})
        return views

    def _repeated_pairs(self, payloads: Iterable[Payload]) -> set[frozenset[str]]:
        return {
            frozenset({payload["seat"], difference["seat"]})
            for payload in payloads
            for difference in payload["differs"]
            if _difference_key(difference) in self._differences or self._said_already(difference)
        }

    def _said_already(self, difference: Mapping[str, Any]) -> bool:
        sides = (difference["thisView"], difference["otherView"])
        return all(
            sentence_keys(side["text"], side.get("original")) & self._texts
            or (claims_of(side) and claims_of(side) <= self._claims)
            for side in sides
        )

    def _picture(self, section_id: str, payload: Payload) -> Block | None:
        cited = self._section_claims.get(section_id, set())
        for item in payload["items"]:
            media = item["media"]
            claims = [claim for claim in item["claimIds"] if claim in cited]
            if not claims or picture_keys(media) & self._pictures or blocked_media(media):
                continue
            block = _validated("images", {**payload, "items": [{**item, "claimIds": claims}]})
            if block is not None:
                self._pictures.update(picture_keys(media))
                return block
        logger.info("pictures %s show nothing new for this answer", payload["id"])
        return None

    def _record(self, section_id: str, block: Block) -> None:
        payload = block.model_dump(mode="json", by_alias=True)
        self._record_sentences(
            sentence.model_dump(mode="json", by_alias=True) for sentence in block.cited_sentences()
        )
        self._section_claims.setdefault(section_id, set()).update(block.cited_claim_ids())
        if block.kind in ONCE_PER_ANSWER_KINDS:
            self._once.add(block.kind)
        if block.kind == "material_card":
            self._materials.update(_material_keys(payload))
        elif block.kind == "molecule_3d":
            self._molecules.add(payload["pubchemCid"])
        elif block.kind == SIMULATION_KIND:
            self._explained.add(fold(payload["concept"]))
        elif block.kind == WHAT_IF_KIND:
            self._what_ifs.append(_what_if_key(payload))
        elif block.kind == "concept_graph":
            self._concepts.update(node["termKey"] for node in payload["nodes"])
        elif block.kind == EXPERT_KIND:
            self._differences.update(_difference_key(difference) for difference in payload["differs"])
        elif block.kind == "zoom_story":
            self._pictures.update(
                key for level in payload["levels"] if level["media"] for key in picture_keys(level["media"])
            )

    def _record_sentences(self, sentences: Any) -> None:
        for sentence in sentences:
            self._texts.update(sentence_keys(sentence["text"], sentence.get("original")))
            self._claims.update(claims_of(sentence))
            self._said.append(said(sentence))


def _validated(kind: str, payload: Payload) -> Block | None:
    try:
        return BLOCK_MODELS[kind].model_validate(payload)
    except ValidationError as refused:
        logger.info("block %s is left out once its repeats go: %s", payload.get("id"), refused.error_count())
        return None


def _expert_views(payloads: Mapping[int, Payload]) -> dict[int, Block]:
    return {n: view for n, payload in payloads.items() if (view := _validated(EXPERT_KIND, payload))}


def _paired(kept: Mapping[int, Payload], repeated: set[frozenset[str]]) -> dict[int, Payload]:
    seats = {payload["seat"] for payload in kept.values()}
    return {n: _paired_within(payload, seats, repeated) for n, payload in kept.items()}


def _paired_within(payload: Payload, seats: set[str], repeated: set[frozenset[str]]) -> Payload:
    seat = payload["seat"]
    differs = [
        d
        for d in payload["differs"]
        if d["seat"] in seats and frozenset({seat, d["seat"]}) not in repeated and independent(d)
    ]
    return {**payload, "agreesWith": [s for s in payload["agreesWith"] if s in seats], "differs": differs}


def _difference_key(difference: Mapping[str, Any]) -> frozenset[frozenset[str]]:
    return frozenset({claims_of(difference["thisView"]), claims_of(difference["otherView"])})


def _what_if_key(payload: Mapping[str, Any]) -> WhatIfKey:
    options = frozenset(_option_key(option) for option in payload["options"])
    return payload.get("stageId"), options


def _option_key(option: Mapping[str, Any]) -> str:
    held = option.get("materialId") or option.get("termKey")
    return f"held:{held}" if held else f"name:{fold(option['label'])}"


def _same_what_if(one: WhatIfKey, other: WhatIfKey) -> bool:
    return one[0] == other[0] and len(one[1] & other[1]) >= WHAT_IF_SHARED_OPTIONS


def _material_keys(payload: Mapping[str, Any]) -> set[str]:
    named = {
        "cid": payload.get("pubchemCid"),
        "compound": payload.get("compoundId"),
        "material": payload.get("materialId"),
        "term": payload.get("termKey"),
        "name": fold(payload["name"]),
    }
    return {f"{field}:{value}" for field, value in named.items() if value}
