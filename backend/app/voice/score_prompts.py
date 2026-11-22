from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = [
    "CUE_SECONDS",
    "SCORE_CUES",
    "SCORE_MUSIC_PROMPT",
    "SCORE_PROMPT_VERSION",
    "CuePrompt",
    "cue_prompt",
]

SCORE_PROMPT_VERSION = "film-score/v1"
CUE_SECONDS = 2.0
SCORE_MUSIC_PROMPT = (
    "A calm instrumental documentary underscore with soft hand percussion, warm strings and a gentle "
    "drone, steady and unobtrusive beneath spoken narration, without vocals or lyrics."
)


@dataclass(frozen=True)
class CuePrompt:
    prompt: str
    seconds: float = CUE_SECONDS
    offset_seconds: float = 0.0


SCORE_CUES: Mapping[tuple[str, str | None], CuePrompt] = MappingProxyType(
    {
        ("process_ladder", None): CuePrompt(
            "Soft rhythmic tapping of wooden hand tools on a workbench, close and gentle"
        ),
        ("prose", "GEOGRAPHY"): CuePrompt(
            "Gentle running water in a shallow stream with a light breeze, calm and natural", 3.0, 0.5
        ),
        ("region_story", None): CuePrompt(
            "A river flowing steadily over smooth stones, calm natural ambience", 3.0, 0.5
        ),
        ("reaction_player", None): CuePrompt("Liquid bubbling softly as it simmers in a metal vessel"),
        ("seasons", None): CuePrompt("Light rain falling on leaves, soft and distant", 3.0),
        ("map_layer", None): CuePrompt("A large paper map unfolding softly on a wooden table"),
        ("molecule_3d", None): CuePrompt("A soft airy shimmer that rises gently and fades"),
    }
)


def cue_prompt(kind: str, discipline: str | None) -> CuePrompt | None:
    return SCORE_CUES.get((kind, discipline)) or SCORE_CUES.get((kind, None))
