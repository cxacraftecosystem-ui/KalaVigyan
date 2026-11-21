from __future__ import annotations

import json
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from types import MappingProxyType
from typing import Any, Literal, Protocol

from pydantic import Field, ValidationError

from .base import ContractModel

__all__ = [
    "CLEAR",
    "FACE",
    "FLAGGED",
    "FLAG_REASONS",
    "ID_DOCUMENT",
    "NEAR_BITS",
    "NEAR_DUPLICATE",
    "NEAR_IDENTICAL_BITS",
    "NOT_SCREENED",
    "SCREEN_FLAGS",
    "SCREEN_VERDICTS",
    "UNSCREENED",
    "VISION_ANSWER_SCHEMA",
    "VISION_OUTPUT_TOKENS",
    "Near",
    "ScreenSummary",
    "ScreenVerdict",
    "VisionAnswer",
    "VisionRequest",
    "VisionScreen",
    "VisionVerdict",
    "screen_flags",
    "screen_reasons",
    "signed_fingerprint",
    "unscreened",
    "verdict_of",
    "vision_flags",
    "vision_prompt",
    "vision_verdict",
]

CLEAR = "CLEAR"
FLAGGED = "FLAGGED"
UNSCREENED = "UNSCREENED"
SCREEN_VERDICTS = (CLEAR, FLAGGED, UNSCREENED)
ID_DOCUMENT = "ID_DOCUMENT"
FACE = "FACE"
FACE_IN_AI_IMAGE = "FACE_IN_AI_IMAGE"
UNSAFE = "UNSAFE"
NEAR_DUPLICATE = "NEAR_DUPLICATE"
NOT_SCREENED = "NOT_SCREENED"
SCREEN_FLAGS = (ID_DOCUMENT, FACE, FACE_IN_AI_IMAGE, UNSAFE, NEAR_DUPLICATE, NOT_SCREENED)
FLAG_REASONS: Mapping[str, str] = MappingProxyType(
    {
        ID_DOCUMENT: "It may show an identity document, or a card with a face and a number.",
        FACE: "It shows a person's face.",
        FACE_IN_AI_IMAGE: "It is AI-made and shows a person's face.",
        UNSAFE: "It may show content that is not safe to publish.",
        NEAR_DUPLICATE: "It looks like a picture KalaVigyan already holds.",
        NOT_SCREENED: "The automatic screen did not look at it, so a person checks it.",
    }
)
NEAR_IDENTICAL_BITS = 6
NEAR_BITS = 12
VISION_OUTPUT_TOKENS = 300
NOTE_MAX_CHARS = 300
FINGERPRINT_SPAN = 1 << 64
FINGERPRINT_SIGN = 1 << 63
SCREEN_SYSTEM = (
    "You screen pictures given to a public encyclopaedia of Indian crafts before a person reviews them. Look "
    "only at the picture. Answer in the JSON schema and nothing else."
)
ID_QUESTION = (
    "Does it show an identity document or card: an Aadhaar card, a PAN card, a passport, a voter ID, a driving "
    "licence, a bank card, or any card that carries a person's face and a number?"
)
FACE_QUESTION = "Does it show a human face, drawn or photographed?"
UNSAFE_QUESTION = (
    "Does it show content unsafe to publish: nudity or sexual content, violence or injury, gore, hate symbols, "
    "self-harm, or a weapon aimed at a person?"
)
NOTE_ASK = "In note, say in one sentence what you saw that made any answer true, or leave it empty."
VISION_ANSWER_SCHEMA: Mapping[str, Any] = MappingProxyType(
    {
        "type": "object",
        "properties": {
            "idDocument": {"type": "boolean"},
            "face": {"type": "boolean"},
            "unsafe": {"type": "boolean"},
            "note": {"type": "string"},
        },
        "required": ["idDocument", "face", "unsafe", "note"],
        "additionalProperties": False,
    }
)

ScreenVerdict = Literal[*SCREEN_VERDICTS]


class VisionAnswer(ContractModel):
    id_document: bool
    face: bool
    unsafe: bool
    note: str = Field(default="", max_length=2000)


@dataclass(frozen=True)
class VisionRequest:
    preview: bytes
    mime: str
    ai_made: bool
    user_id: uuid.UUID | None
    role: str | None
    faces: bool = False


@dataclass(frozen=True)
class VisionVerdict:
    ran: bool
    flags: tuple[str, ...] = ()
    note: str | None = None
    provider: str | None = None
    model: str | None = None
    usage_event_id: uuid.UUID | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: Decimal = Decimal(0)


class VisionScreen(Protocol):
    async def __call__(self, request: VisionRequest) -> VisionVerdict: ...


@dataclass(frozen=True)
class Near:
    asset_id: uuid.UUID
    distance: int
    live: bool
    contributed: bool


class ScreenSummary(ContractModel):
    verdict: ScreenVerdict
    flags: list[str]
    reasons: list[str]


def unscreened(note: str) -> VisionVerdict:
    return VisionVerdict(ran=False, flags=(NOT_SCREENED,), note=note)


def vision_prompt(*, ai_made: bool) -> tuple[str, str]:
    face = FACE_QUESTION + (" The picture is AI-made." if ai_made else "")
    return SCREEN_SYSTEM, "\n".join((ID_QUESTION, face, UNSAFE_QUESTION, NOTE_ASK))


def vision_flags(answer: VisionAnswer, *, ai_made: bool, faces: bool = False) -> tuple[str, ...]:
    raised = (
        (ID_DOCUMENT, answer.id_document),
        (FACE, faces and not ai_made and answer.face),
        (FACE_IN_AI_IMAGE, ai_made and answer.face),
        (UNSAFE, answer.unsafe),
    )
    return tuple(flag for flag, up in raised if up)


def vision_verdict(
    text: str, *, ai_made: bool, faces: bool = False
) -> tuple[tuple[str, ...], str | None] | None:
    try:
        answer = VisionAnswer.model_validate(json.loads(text))
    except ValueError, ValidationError:
        return None
    flags = vision_flags(answer, ai_made=ai_made, faces=faces)
    note = answer.note.strip()[:NOTE_MAX_CHARS] or None
    return flags, note if flags else None


def screen_flags(vision: VisionVerdict, near: Near | None) -> tuple[str, ...]:
    close = (NEAR_DUPLICATE,) if near is not None and near.distance <= NEAR_BITS else ()
    return tuple(flag for flag in SCREEN_FLAGS if flag in (*vision.flags, *close))


def verdict_of(flags: Sequence[str]) -> str:
    if NOT_SCREENED in flags:
        return UNSCREENED
    return FLAGGED if flags else CLEAR


def screen_reasons(flags: Sequence[str], note: str | None) -> list[str]:
    reasons = [FLAG_REASONS[flag] for flag in flags]
    return [*reasons, note] if note and flags else reasons


def signed_fingerprint(fingerprint: int) -> int:
    if not 0 <= fingerprint < FINGERPRINT_SPAN:
        raise ValueError(f"a fingerprint is 64 bits, not {fingerprint}")
    return fingerprint - FINGERPRINT_SPAN if fingerprint >= FINGERPRINT_SIGN else fingerprint
