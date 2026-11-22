import hashlib
import json
import re
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass

import requests

from geo_etl.remote import USER_AGENT, with_retries

ENDPOINT = "https://query.wikidata.org/sparql"
RIVER_MOUTH = "Q1233637"
RIVER_SOURCE = "Q7376362"
RIVER_CLASS = "Q4022"
ITEMS_PER_QUERY = 300
QUERY_TIMEOUT_S = (10, 120)
SQUARE_METRES_PER_KM2 = 1e6
ENTITY = re.compile(r"^http://www\.wikidata\.org/entity/(Q\d+)$")
POINT = re.compile(r"^Point\((-?\d+(?:\.\d+)?(?:[eE]-?\d+)?) (-?\d+(?:\.\d+)?(?:[eE]-?\d+)?)\)$")
POINTS_QUERY = """SELECT ?item ?part ?coord WHERE {{
  VALUES ?part {{ wd:{mouth} wd:{source} }}
  ?statement pq:P518 ?part ; ps:P625 ?coord .
  ?item p:P625 ?statement .
  BIND(geof:longitude(?coord) AS ?lon) BIND(geof:latitude(?coord) AS ?lat)
  FILTER(?lon >= {west} && ?lon <= {east} && ?lat >= {south} && ?lat <= {north})
}}"""
FACTS_QUERY = """SELECT ?item ?label ?mouth ?area WHERE {{
  VALUES ?item {{ {items} }}
  ?item wdt:P31/wdt:P279* wd:{river} .
  OPTIONAL {{ ?item rdfs:label ?label FILTER(LANG(?label) = "en") }}
  OPTIONAL {{ ?item wdt:P403 ?mouth }}
  OPTIONAL {{ ?item p:P2053/psn:P2053/wikibase:quantityAmount ?area }}
}}"""

LonLat = tuple[float, float]
Ask = Callable[[str], bytes]


@dataclass(frozen=True)
class WikidataRiver:
    item: str
    label: str
    mouths: tuple[LonLat, ...]
    sources: tuple[LonLat, ...]
    mouth_items: tuple[str, ...]
    areas_km2: tuple[float, ...]


@dataclass(frozen=True)
class WikidataAnswer:
    rivers: tuple[WikidataRiver, ...]
    sha256: str


def fetch_rivers(bounds: tuple[float, float, float, float], ask: Ask | None = None) -> WikidataAnswer:
    ask = ask or sparql
    west, south, east, north = bounds
    query = POINTS_QUERY.format(mouth=RIVER_MOUTH, source=RIVER_SOURCE, west=west, east=east, south=south, north=north)
    bodies = [ask(query)]
    points = point_rows(bodies[0])
    facts: list[dict] = []
    for batch in batches(sorted(points), ITEMS_PER_QUERY):
        items = " ".join(f"wd:{item}" for item in batch)
        bodies.append(ask(FACTS_QUERY.format(items=items, river=RIVER_CLASS)))
        facts.extend(bindings(bodies[-1]))
    digest = hashlib.sha256(b"".join(bodies)).hexdigest()
    return WikidataAnswer(rivers=rivers_of(points, facts), sha256=digest)


def sparql(query: str) -> bytes:
    def post() -> bytes:
        response = requests.post(
            ENDPOINT,
            data={"query": query},
            headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
            timeout=QUERY_TIMEOUT_S,
        )
        response.raise_for_status()
        return response.content

    return with_retries(post, retry_on=(requests.RequestException,))


def bindings(body: bytes) -> list[dict]:
    return [{key: value["value"] for key, value in row.items()} for row in json.loads(body)["results"]["bindings"]]


def point_rows(body: bytes) -> dict[str, dict[str, list[LonLat]]]:
    points: dict[str, dict[str, list[LonLat]]] = {}
    for row in bindings(body):
        item, part, where = entity(row["item"]), entity(row["part"]), lon_lat(row["coord"])
        if item and part and where:
            points.setdefault(item, {RIVER_MOUTH: [], RIVER_SOURCE: []})[part].append(where)
    return points


def rivers_of(points: dict[str, dict[str, list[LonLat]]], facts: Iterable[dict]) -> tuple[WikidataRiver, ...]:
    labels: dict[str, set[str]] = {}
    mouths: dict[str, set[str]] = {}
    areas: dict[str, set[float]] = {}
    for row in facts:
        item = entity(row["item"])
        if item is None:
            continue
        labels.setdefault(item, set()).update([row["label"]] if row.get("label") else [])
        mouths.setdefault(item, set()).update(found for found in [entity(row.get("mouth", ""))] if found)
        areas.setdefault(item, set()).update([float(row["area"]) / SQUARE_METRES_PER_KM2] if row.get("area") else [])
    rivers = [
        WikidataRiver(
            item=item,
            label=next(iter(labels[item])),
            mouths=tuple(sorted(set(points[item][RIVER_MOUTH]))),
            sources=tuple(sorted(set(points[item][RIVER_SOURCE]))),
            mouth_items=tuple(sorted(mouths.get(item, ()))),
            areas_km2=tuple(sorted(areas.get(item, ()))),
        )
        for item in sorted(labels)
        if len(labels[item]) == 1 and item in points
    ]
    return tuple(river for river in rivers if river.mouths)


def entity(value: str) -> str | None:
    found = ENTITY.match(value)
    return found.group(1) if found else None


def lon_lat(value: str) -> LonLat | None:
    found = POINT.match(value)
    return (float(found.group(1)), float(found.group(2))) if found else None


def batches(items: Sequence[str], size: int) -> list[Sequence[str]]:
    return [items[start : start + size] for start in range(0, len(items), size)]
