from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from .images import ImageCandidate, shown_inline
from .quotes import content_stem, content_stems, content_words

__all__ = [
    "CLAIMS_PER_IMAGE_MAX",
    "IMAGE_MIN_SHARED_STEMS",
    "SECTION_IMAGES_MAX",
    "SECTION_LINK_CARDS_MAX",
    "TOPIC_WORDS_MAX",
    "ChosenImage",
    "ClaimText",
    "Illustration",
    "choose_images",
    "illustrated_claims",
    "illustration",
    "topic_words",
]

IMAGE_MIN_SHARED_STEMS = 2
CLAIMS_PER_IMAGE_MAX = 3
TOPIC_WORDS_MAX = 2
SECTION_IMAGES_MAX = 4
SECTION_LINK_CARDS_MAX = 2


@dataclass(frozen=True)
class ClaimText:
    claim_id: uuid.UUID
    text: str


@dataclass(frozen=True)
class Illustration:
    claim_ids: tuple[uuid.UUID, ...]
    shared: int


@dataclass(frozen=True)
class ChosenImage:
    candidate: ImageCandidate
    illustration: Illustration


def illustration(
    candidate: ImageCandidate, claims: Sequence[ClaimText], *, leave_out: str
) -> Illustration | None:
    return illustrated_claims(candidate.described, claims, leave_out=leave_out)


def illustrated_claims(described: str, claims: Sequence[ClaimText], *, leave_out: str) -> Illustration | None:
    shown = content_stems(described) - content_stems(leave_out)
    ranked: list[tuple[int, int, uuid.UUID]] = []
    for position, claim in enumerate(claims):
        shared = len(shown & content_stems(claim.text))
        if shared >= IMAGE_MIN_SHARED_STEMS:
            ranked.append((-shared, position, claim.claim_id))
    if not ranked:
        return None
    ranked.sort(key=lambda entry: entry[:2])
    chosen = list(dict.fromkeys(claim_id for _, _, claim_id in ranked))[:CLAIMS_PER_IMAGE_MAX]
    return Illustration(claim_ids=tuple(chosen), shared=-ranked[0][0])


def choose_images(
    candidates: Sequence[ImageCandidate], claims: Sequence[ClaimText], *, leave_out: str
) -> list[ChosenImage]:
    seen: set[str] = set()
    found: list[tuple[bool, int, int, ChosenImage]] = []
    for position, candidate in enumerate(candidates):
        if candidate.original_key in seen:
            continue
        seen.add(candidate.original_key)
        shown = illustration(candidate, claims, leave_out=leave_out)
        if shown is not None:
            found.append(
                (not shown_inline(candidate), -shown.shared, position, ChosenImage(candidate, shown))
            )
    found.sort(key=lambda entry: entry[:3])
    chosen: list[ChosenImage] = []
    cards = 0
    for link_card, _, _, image in found:
        if link_card and cards >= SECTION_LINK_CARDS_MAX:
            continue
        cards += link_card
        chosen.append(image)
    return chosen[:SECTION_IMAGES_MAX]


def topic_words(claims: Sequence[ClaimText], *, leave_out: str) -> list[str]:
    known = content_stems(leave_out)
    first_word: dict[str, str] = {}
    counts: Counter[str] = Counter()
    for claim in claims:
        words = [word for word in content_words(claim.text) if content_stem(word) not in known]
        for word in words:
            first_word.setdefault(content_stem(word), word)
        counts.update({content_stem(word) for word in words})
    ordered = sorted(first_word, key=lambda stem: -counts[stem])
    return [first_word[stem] for stem in ordered[:TOPIC_WORDS_MAX]]
