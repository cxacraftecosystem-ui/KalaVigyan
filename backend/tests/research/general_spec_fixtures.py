from __future__ import annotations

import uuid
from typing import Any

__all__ = [
    "CHART",
    "DRAWING",
    "MAP_LAYER",
    "SVG",
    "TABLE",
    "TIMELINE",
    "chart_units",
    "table_units",
]

HEAD = {"title": "u0001", "caption": "u0002"}
SVG = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 60" width="120" height="60">'
    '<rect x="1" y="1" width="20" height="10" fill="var(--ink-1)"/></svg>'
)
DRAWING: dict[str, Any] = {"head": HEAD, "svg": SVG, "alt": "u0003"}
CHART: dict[str, Any] = {
    "head": HEAD,
    "form": "bars",
    "valueLabel": "u0003",
    "series": [
        {
            "name": "u0004",
            "points": [
                {"label": "u0005", "value": 518, "reading": "u0006"},
                {"label": "u0007", "value": 331, "reading": "u0008"},
            ],
        }
    ],
    "emphasis": 0,
}
TABLE: dict[str, Any] = {
    "head": HEAD,
    "columns": [{"label": "u0003"}, {"label": "u0004"}],
    "rows": [{"cells": ["u0005", "u0006"]}],
}
TIMELINE: dict[str, Any] = {
    "head": HEAD,
    "events": [
        {"year": 1868, "when": "u0003", "title": "u0004", "text": "u0005"},
        {"year": 1947, "when": "u0006", "title": "u0007", "text": "u0008"},
    ],
}
MAP_LAYER: dict[str, Any] = {
    "head": HEAD,
    "places": [{"longitude": 69.67, "latitude": 23.25, "name": "u0003", "reading": "u0004", "value": 518}],
    "valueLabel": "u0005",
}


def chart_units(claim: uuid.UUID) -> dict[str, Any]:
    cited = [str(claim)]
    return {
        "u0001": {"text": "Bhuj had its wettest year of the pair in 1981.", "claimIds": cited},
        "u0002": {"text": "Bhuj received 518 mm of rain in 1981 and 331 mm in 1982.", "claimIds": cited},
        "u0003": {"text": "Rainfall, mm"},
        "u0004": {"text": "Bhuj"},
        "u0005": {"text": "The first year", "claimIds": cited},
        "u0006": {"text": "518 mm", "claimIds": cited},
        "u0007": {"text": "The next year", "claimIds": cited},
        "u0008": {"text": "331 mm", "claimIds": cited},
    }


def table_units(claim: uuid.UUID) -> dict[str, Any]:
    cited = [str(claim)]
    return {
        "u0001": {"text": "Alum fixes the madder red on the cotton.", "claimIds": cited},
        "u0002": {"text": "Alum fixes the madder red on the cotton.", "claimIds": cited},
        "u0003": {"text": "Mordant"},
        "u0004": {"text": "What it does"},
        "u0005": {"text": "Alum"},
        "u0006": {"text": "Fixes the madder red", "claimIds": cited},
    }
