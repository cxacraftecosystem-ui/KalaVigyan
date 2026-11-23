from __future__ import annotations

from collections.abc import Callable, Mapping, Set
from typing import Any

from pydantic.alias_generators import to_camel

from app.data.craft_text import fold
from app.research.blocks import SENTENCE, SentenceSpec, sentences_in_payload
from app.research.blocks_learning import COMPARE_CRAFTS_MIN
from app.research.vocabulary import weakest_level

from .picture_sites import blocked_picture

__all__ = [
    "Payload",
    "Repeat",
    "blocked_media",
    "claims_of",
    "compared_rows",
    "fresh_nodes",
    "independent",
    "kept_sentences",
    "leveled_stages",
    "picture_keys",
    "quantity_rows",
    "sentence_keys",
    "zoomed_levels",
]

Payload = dict[str, Any]
Repeat = Callable[[Mapping[str, Any]], bool]


def sentence_keys(text: str | None, original: str | None = None) -> set[str]:
    return {key for value in (text, original) if value and (key := fold(value))}


def claims_of(sentence: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(citation["claimId"] for citation in sentence.get("citations", []))


def independent(difference: Mapping[str, Any]) -> bool:
    mine, theirs = difference["thisView"], difference["otherView"]
    return not (claims_of(mine) & claims_of(theirs) or _sources_of(mine) & _sources_of(theirs))


def kept_sentences(holder: Mapping[str, Any], spec: SentenceSpec, repeat: Repeat) -> Payload | None:
    kept = dict(holder)
    for name, node in spec:
        key = to_camel(name)
        value = kept.get(key)
        if value is None:
            continue
        if node == SENTENCE and repeat(value):
            return None
        if isinstance(node, list):
            kept[key] = [part for item in value if (part := _kept_part(item, node[0], repeat)) is not None]
        elif node != SENTENCE:
            kept[key] = _kept_part(value, node, repeat)
    return kept


def compared_rows(payload: Mapping[str, Any], repeat: Repeat) -> Payload:
    rows = []
    for row in payload["rows"]:
        cells = [None if cell is None or repeat(cell["sentence"]) else cell for cell in row["cells"]]
        if sum(cell is not None for cell in cells) >= COMPARE_CRAFTS_MIN:
            rows.append({**row, "cells": cells})
    return {**payload, "rows": rows}


def quantity_rows(payload: Mapping[str, Any], shown: Mapping[str, str], repeat: Repeat) -> Payload:
    rows = []
    for row in payload["rows"]:
        kept = {name: value for name, value in row.items() if name != "shownIn"}
        shown_in = _shown_in(row["sentence"], shown)
        if shown_in is not None:
            rows.append({**kept, "shownIn": shown_in})
        elif not repeat(row["sentence"]):
            rows.append(kept)
    return {**payload, "rows": rows}


def fresh_nodes(payload: Mapping[str, Any], shown_terms: Set[str]) -> Payload:
    focus = (payload.get("focus") or {}).get("slug")
    nodes = [node for node in payload["nodes"] if node["termKey"] not in shown_terms and _viable(node, focus)]
    return {**payload, "nodes": nodes}


def zoomed_levels(payload: Mapping[str, Any], shown_pictures: Set[str]) -> Payload:
    taken = set(shown_pictures)
    levels = []
    for level in payload["levels"]:
        media = level.get("media")
        keys = picture_keys(media) if media is not None else set()
        if keys & taken or (media is not None and blocked_media(media)):
            continue
        taken |= keys
        levels.append(level)
    mapped = any(level.get("district") is not None for level in levels)
    return {**payload, "levels": levels, **({} if mapped else {"datasets": [], "boundaryCaption": None})}


def leveled_stages(payload: Mapping[str, Any]) -> Payload:
    stages = [
        {**stage, "level": weakest_level(sentence["level"] for sentence in stage["sentences"])}
        for stage in payload["stages"]
    ]
    return {**payload, "stages": stages}


def picture_keys(media: Mapping[str, Any]) -> set[str]:
    urls = (media["pageUrl"], media["imageUrl"])
    return {f"media:{media['id']}", *(f"url:{_bare_url(url)}" for url in urls)}


def blocked_media(media: Mapping[str, Any]) -> bool:
    return blocked_picture(page_url=media["pageUrl"], image_url=media["imageUrl"], title=media["title"])


def _kept_part(value: Any, node: Any, repeat: Repeat) -> Any:
    if value is None:
        return None
    if node == SENTENCE:
        return None if repeat(value) else value
    kept = kept_sentences(value, node, repeat)
    said = kept is not None and (sentences_in_payload(kept, node) or not sentences_in_payload(value, node))
    return kept if said else None


def _viable(node: Mapping[str, Any], focus: str | None) -> bool:
    slugs = [entry["craft"]["slug"] for entry in node["crafts"]]
    return len(slugs) >= COMPARE_CRAFTS_MIN and (focus is None or focus in slugs)


def _shown_in(sentence: Mapping[str, Any], shown: Mapping[str, str]) -> str | None:
    keys = sorted(sentence_keys(sentence["text"], sentence.get("original")))
    return next((shown[key] for key in keys if key in shown), None)


def _bare_url(url: str) -> str:
    return url.split("#", 1)[0].split("?", 1)[0].rstrip("/").casefold()


def _sources_of(sentence: Mapping[str, Any]) -> frozenset[str]:
    return frozenset(citation["sourceId"] for citation in sentence.get("citations", []))
