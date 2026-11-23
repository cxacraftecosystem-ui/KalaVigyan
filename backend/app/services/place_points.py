from __future__ import annotations

from dataclasses import dataclass

__all__ = ["OriginPlace", "RegisterPoint", "ShownPlace"]


@dataclass(frozen=True)
class OriginPlace:
    wikidata_id: str
    latitude: float
    longitude: float


@dataclass(frozen=True)
class RegisterPoint:
    district_lgd: int
    latitude: float
    longitude: float


ShownPlace = OriginPlace | RegisterPoint
