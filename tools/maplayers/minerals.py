from __future__ import annotations

import csv
import io
import zipfile
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "MINERAL_CLASSES",
    "STATUSES",
    "Place",
    "Site",
    "commodities",
    "mineral_class",
    "minerals_body",
    "read_sites",
    "site_from_row",
]

MINERAL_CLASSES: tuple[tuple[str, str, frozenset[str]], ...] = (
    ("iron", "Iron", frozenset({"Iron"})),
    (
        "alloy",
        "Manganese, chromium and alloy metals",
        frozenset({"Manganese", "Chromium", "Vanadium", "Nickel", "Tungsten", "Molybdenum", "Cobalt"}),
    ),
    ("aluminium", "Aluminium", frozenset({"Aluminum"})),
    (
        "base",
        "Copper, lead, zinc and precious metals",
        frozenset({"Copper", "Lead", "Zinc", "Gold", "Silver", "Platinum", "PGE"}),
    ),
    (
        "sands",
        "Titanium, zirconium and rare earths",
        frozenset({"Titanium", "Titanium-Ilmenite", "Zirconium", "REE", "Thorium", "Uranium", "Lithium"}),
    ),
    ("industrial", "Industrial minerals", frozenset()),
)
STATUSES = ("Producer", "Past Producer", "Prospect", "Occurrence", "Unknown")
SKIPPED_STATUS = "Plant"
COMMODITY_FIELDS = ("commod1", "commod2", "commod3")


@dataclass(frozen=True)
class Site:
    dep_id: int
    name: str
    state: str
    longitude: float
    latitude: float
    status: str
    commodities: tuple[str, ...]


def commodities(row: dict[str, str]) -> tuple[str, ...]:
    names: list[str] = []
    for field in COMMODITY_FIELDS:
        for part in (row.get(field) or "").split(","):
            name = part.strip()
            if name and name not in names:
                names.append(name)
    return tuple(names)


def mineral_class(names: Iterable[str]) -> int:
    first = next(iter(names), None)
    for index, (_, _, members) in enumerate(MINERAL_CLASSES):
        if first in members:
            return index
    return len(MINERAL_CLASSES) - 1


def site_from_row(row: dict[str, str], state: str) -> Site | None:
    status = (row.get("dev_stat") or "Unknown").strip() or "Unknown"
    names = commodities(row)
    if status == SKIPPED_STATUS or not names or not row.get("latitude") or not row.get("longitude"):
        return None
    return Site(
        dep_id=int(row["dep_id"]),
        name=(row.get("site_name") or "").strip(),
        state=state,
        longitude=round(float(row["longitude"]), 4),
        latitude=round(float(row["latitude"]), 4),
        status=status if status in STATUSES else "Unknown",
        commodities=names,
    )


def _rows(archive: Path) -> Iterator[dict[str, str]]:
    with zipfile.ZipFile(archive) as opened:
        member = next(name for name in opened.namelist() if name.endswith(".csv"))
        with opened.open(member) as raw:
            yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8", errors="replace"))


@dataclass(frozen=True)
class Place:
    bounds: tuple[float, float, float, float]
    inside: Callable[[float, float], bool]
    state: Callable[[float, float], str]

    def keeps(self, longitude: float, latitude: float) -> bool:
        west, south, east, north = self.bounds
        return west <= longitude <= east and south <= latitude <= north and self.inside(longitude, latitude)


def read_sites(archive: Path, place: Place) -> list[Site]:
    found: list[Site] = []
    for row in _rows(archive):
        try:
            longitude, latitude = float(row["longitude"]), float(row["latitude"])
        except TypeError, ValueError:
            continue
        if not place.keeps(longitude, latitude):
            continue
        site = site_from_row(row, place.state(longitude, latitude))
        if site is not None:
            found.append(site)
    return sorted(found, key=lambda site: site.dep_id)


def minerals_body(sites: list[Site], source: dict[str, str]) -> dict[str, object]:
    return {
        "source": source,
        "classes": [{"id": key, "label": label} for key, label, _ in MINERAL_CLASSES],
        "statuses": list(STATUSES),
        "fields": ["depId", "name", "state", "longitude", "latitude", "class", "status", "commodities"],
        "sites": [
            [
                site.dep_id,
                site.name,
                site.state,
                site.longitude,
                site.latitude,
                mineral_class(site.commodities),
                STATUSES.index(site.status),
                ", ".join(site.commodities),
            ]
            for site in sites
        ],
    }
