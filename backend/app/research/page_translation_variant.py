from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

from .document_translation import DocumentTranslation
from .monograph_page import MonographContent, TextUnit
from .translation_passages import is_translatable, passage_leaves, unit_hash, with_texts
from .vocabulary import ANSWER_LANGUAGE_SPECS, CANONICAL_LANGUAGE, text_direction

__all__ = ["NO_TRANSLATIONS", "ServedTranslations", "Variant", "translations_digest", "variant_content"]

DIGEST_SEPARATOR = ","


@dataclass(frozen=True)
class ServedTranslations:
    by_hash: Mapping[str, tuple[str, ...]] = field(default_factory=lambda: MappingProxyType({}))
    earlier: frozenset[str] = frozenset()
    digest: str = ""

    @property
    def empty(self) -> bool:
        return not self.by_hash


NO_TRANSLATIONS = ServedTranslations()


@dataclass(frozen=True)
class Variant:
    content: MonographContent
    translation: DocumentTranslation


@dataclass
class _Tally:
    passages: int = 0
    translated: int = 0
    held: int = 0


def translations_digest(ids: Iterable[str]) -> str:
    joined = DIGEST_SEPARATOR.join(sorted(ids))
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def variant_content(
    content: MonographContent, served: ServedTranslations, *, language: str, source_version: int
) -> Variant:
    tally = _Tally()
    units = {key: _shown(key, unit, served, language, tally) for key, unit in content.units.items()}
    translation = DocumentTranslation(
        source_version=source_version,
        script=ANSWER_LANGUAGE_SPECS[language].script,
        direction=text_direction(language),
        passages=tally.passages,
        translated=tally.translated,
        held=tally.held,
    )
    return Variant(content=content.model_copy(update={"units": units}), translation=translation)


def _shown(key: str, unit: TextUnit, served: ServedTranslations, language: str, tally: _Tally) -> TextUnit:
    if not is_translatable(key, unit.nodes):
        return unit
    tally.passages += 1
    texts = served.by_hash.get(unit_hash(unit.nodes, unit.claim_ids))
    if texts is not None and len(texts) == len(passage_leaves(unit.nodes)):
        tally.translated += 1
        return unit.model_copy(update={"nodes": with_texts(unit.nodes, texts), "lang": language})
    tally.held += key in served.earlier
    return unit.model_copy(update={"lang": CANONICAL_LANGUAGE})
