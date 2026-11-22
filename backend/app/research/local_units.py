from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

__all__ = ["LOCAL_UNITS", "LocalUnit"]


@dataclass(frozen=True)
class LocalUnit:
    measures: str
    words: tuple[str, ...]


LOCAL_UNITS: Mapping[str, LocalUnit] = MappingProxyType(
    {
        "seer": LocalUnit("kg", ("seer", "seers", "ser", "sers")),
        "maund": LocalUnit("kg", ("maund", "maunds")),
        "tola": LocalUnit("g", ("tola", "tolas", "tolah", "tolahs")),
        "chhatak": LocalUnit("g", ("chhatak", "chhataks", "chhatank", "chhatanks", "chattak", "chattaks")),
        "masha": LocalUnit("g", ("masha", "mashas")),
        "ratti": LocalUnit("g", ("ratti", "rattis")),
        "pao": LocalUnit("g", ("pao", "paos")),
        "gaj": LocalUnit("m", ("gaj", "gaz", "guz")),
        "hath": LocalUnit("m", ("hath", "haath")),
        "bigha": LocalUnit("m2", ("bigha", "bighas")),
        "biswa": LocalUnit("m2", ("biswa", "biswas")),
        "kanal": LocalUnit("m2", ("kanal", "kanals")),
        "marla": LocalUnit("m2", ("marla", "marlas")),
        "guntha": LocalUnit("m2", ("guntha", "gunthas", "gunta", "guntas")),
        "katha": LocalUnit("m2", ("katha", "kathas", "kattha", "katthas", "cottah", "cottahs")),
    }
)
