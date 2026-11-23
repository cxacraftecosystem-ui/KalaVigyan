from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from .paid_check_steps import PaidCheck

__all__ = ["CHECK_GROUPS", "STANDING_GROUPS", "chosen_checks", "groups_of"]

CHECK_GROUPS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "narration": ("narration_en", "narration_hi"),
        "music": ("music_bed",),
        "image": ("gemini_image",),
        "speech": ("gemini_speech",),
        "agent": ("agent_turn",),
        "video": ("gemini_video",),
    }
)
STANDING_GROUPS: tuple[str, ...] = ("narration", "music", "image", "speech", "agent")


def groups_of(text: str) -> tuple[str, ...]:
    groups = tuple(dict.fromkeys(part.strip() for part in text.split(",") if part.strip()))
    unknown = [group for group in groups if group not in CHECK_GROUPS]
    if unknown:
        raise ValueError(
            f"no paid check is named {', '.join(unknown)}; the checks are {', '.join(CHECK_GROUPS)}"
        )
    if not groups:
        raise ValueError("a paid check run makes at least one check")
    return groups


def chosen_checks(checks: Sequence[PaidCheck], groups: Sequence[str]) -> list[PaidCheck]:
    names = {name for group in groups for name in CHECK_GROUPS[group]}
    known = {check.name for check in checks}
    missing = sorted(names - known)
    if missing:
        raise ValueError(f"the paid checks name {', '.join(missing)} but make no such check")
    return [check for check in checks if check.name in names]
