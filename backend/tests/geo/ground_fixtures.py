from collections.abc import Sequence
from typing import Any

from app.geo.ground_layers import GroundLayers, ground_layers
from app.geo.ground_materials import CraftMaterial
from app.geo.place_ground import GroundInputs, LocatedPlace, craft_ground, direct_measures
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.why_here import CraftGround

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
ORIGIN = (77.0, 20.0)
GOLDEN_GROUND = "place.ground.golden.json"
SOURCE_ID = "00000000-0000-4000-8000-0000000000a1"
DIGEST = "abcdef0123456789" * 4
CRAFT = CraftRef(slug="Ground-Fixture", name="Ground fixture", path="/crafts/Ground-Fixture")

Point = tuple[float, float]


def _number(value: int) -> str:
    folded = ~(value << 1) if value < 0 else value << 1
    out = []
    while folded >= 0x20:
        out.append(ALPHABET[(folded & 0x1F) | 0x20])
        folded >>= 5
    out.append(ALPHABET[folded])
    return "".join(out)


def encoded(records: Sequence[Sequence[Point]]) -> str:
    parts: list[str] = []
    x = y = 0
    for record in records:
        parts.append(_number(len(record)))
        for longitude, latitude in record:
            px, py = round(longitude * 1000), round(latitude * 1000)
            parts.append(_number(px - x) + _number(py - y))
            x, y = px, py
    return "".join(parts)


def square(west: float, south: float, east: float, north: float) -> list[Point]:
    return [(west, south), (east, south), (east, north), (west, north)]


def relief() -> dict[str, Any]:
    return {
        "datasets": [
            {
                "title": "ETOPO1 1 Arc-Minute Global Relief Model, ice surface",
                "publisher": "NOAA National Centers for Environmental Information",
                "url": "https://example.org/etopo1.asc",
                "licence": "Public domain (U.S. Government work)",
                "citation": "Amante and Eakins, 2009.",
                "sha256": DIGEST,
            }
        ],
        "breaks": [100, 300, 600],
        "bands": [
            {"min": 100, "rings": [encoded([square(76.5, 19.5, 77.5, 20.5)])]},
            {"min": 300, "rings": [encoded([square(76.9, 19.9, 77.05, 20.05)])]},
            {"min": 600, "rings": []},
        ],
    }


def rivers() -> dict[str, Any]:
    natural_earth = [
        {
            "title": "Natural Earth 1:10m physical vectors",
            "file": name,
            "version": "5.0.0",
            "url": f"https://example.org/{name}.zip",
            "sha256": DIGEST,
        }
        for name in ("ne_10m_rivers_lake_centerlines", "ne_10m_lakes")
    ]
    return {
        "licence": "Public domain",
        "datasets": natural_earth,
        "ranks": [{"rank": 4, "lines": encoded([[(77.1, 19.8), (77.1, 20.2)]])}],
        "lakes": [encoded([square(77.3, 20.3, 77.4, 20.4)])],
        "labels": [{"text": "Fixture", "tier": 1, "longitude": 77.1, "latitude": 20.1, "angle": 90.0}],
    }


def minerals() -> dict[str, Any]:
    return {
        "source": {
            "title": "Mineral Resources Data System",
            "publisher": "U.S. Geological Survey",
            "url": "https://example.org/mrds-csv.zip",
            "licence": "Public domain (U.S. Government work)",
            "citation": "U.S. Geological Survey. Mineral Resources Data System.",
            "sha256": DIGEST,
        },
        "classes": [
            {"id": "iron", "label": "Iron"},
            {"id": "alloy", "label": "Manganese, chromium and alloy metals"},
            {"id": "aluminium", "label": "Aluminium"},
            {"id": "base", "label": "Copper, lead, zinc and precious metals"},
            {"id": "sands", "label": "Titanium, zirconium and rare earths"},
            {"id": "industrial", "label": "Industrial minerals"},
        ],
        "statuses": ["Producer", "Past Producer", "Prospect", "Occurrence", "Unknown"],
        "sites": [
            [1, "Near iron", "Fixture State", 77.0, 20.1, 0, 3, "Iron"],
            [2, "Far copper", "Fixture State", 77.0, 20.6, 3, 1, "Copper, Gold"],
            [3, "Mid alum", "Fixture State", 77.0, 19.7, 2, 3, "Aluminum"],
        ],
    }


def fixture_layers() -> GroundLayers:
    return ground_layers(relief(), rivers(), minerals())


def fixture_source() -> SourceRef:
    return SourceRef(
        id=SOURCE_ID,
        kind="WEB_PAGE",
        title="A fixture source that places the craft",
        authors=[],
        year=2024,
        doi=None,
        url="https://example.org/place",
        publisher=None,
        licence=None,
        attribution=None,
        reliability=None,
    )


def fixture_place(**changes: Any) -> LocatedPlace:
    fields: dict[str, Any] = {
        "key": "place-1",
        "name": "Fixture village",
        "roles": ("PRACTISED",),
        "precision": "POINT",
        "district": None,
        "district_lgd": None,
        "state": "Fixture State",
        "longitude": ORIGIN[0],
        "latitude": ORIGIN[1],
        "source_id": SOURCE_ID,
    }
    return LocatedPlace(**{**fields, **changes})


def fixture_inputs() -> GroundInputs:
    return GroundInputs(
        craft=CRAFT,
        places=(fixture_place(),),
        materials=(
            CraftMaterial("Alum", "MORDANT"),
            CraftMaterial("Iron filings", "METAL"),
            CraftMaterial("Natural indigo", "DYE"),
            CraftMaterial("Copper vessel", "METAL"),
            CraftMaterial("River clay", "CLAY"),
        ),
        sources=(fixture_source(),),
    )


def fixture_ground() -> CraftGround:
    built = craft_ground(fixture_inputs(), direct_measures(fixture_layers()))
    assert built is not None
    return built
