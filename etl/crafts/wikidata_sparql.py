from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from common import PoliteClient

from wikidata_names import clean_term
from wikidata_vocabulary import CLAIM_PROPS, GI_INDIA, LANGS

__all__ = ["SPARQL", "Linker", "chunks", "parse_coord"]

SPARQL = "https://query.wikidata.org/sparql"


def chunks(items: list[Any], size: int) -> Iterable[list[Any]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


class Linker:
    def __init__(self, client: PoliteClient) -> None:
        self.client = client

    def sparql(self, query: str) -> list[dict[str, Any]]:
        payload = self.client.get_json(
            SPARQL,
            {"format": "json"},
            data={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        return payload["results"]["bindings"]

    def gi_pool(self) -> dict[str, str]:
        rows = self.sparql(
            f"SELECT ?item ?label WHERE {{ ?item wdt:P1389 wd:{GI_INDIA} . "
            "?item rdfs:label ?label . FILTER(LANG(?label) = 'en') }"
        )
        return {r["item"]["value"].rsplit("/", 1)[1]: r["label"]["value"] for r in rows}

    @staticmethod
    def _literal(text: str) -> str:
        return '"' + clean_term(text) + '"'

    @staticmethod
    def _qid(binding: dict[str, Any]) -> str:
        return binding["value"].rsplit("/", 1)[1]

    def wikipedia_search(self, terms: list[str], batch: int = 25) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for group in chunks(sorted({clean_term(t) for t in terms}), batch):
            values = " ".join(self._literal(t) for t in group)
            rows = self.sparql(
                f"SELECT ?term ?item ?ord WHERE {{ VALUES ?term {{ {values} }} "
                'SERVICE wikibase:mwapi { bd:serviceParam wikibase:endpoint "en.wikipedia.org" ; '
                'wikibase:api "Generator" ; mwapi:generator "search" ; mwapi:gsrsearch ?term ; '
                'mwapi:gsrnamespace "0" ; mwapi:gsrlimit "5" ; wikibase:limit "once" . '
                "?item wikibase:apiOutputItem mwapi:item . ?ord wikibase:apiOrdinal true . } }"
            )
            for row in sorted(rows, key=lambda r: int(r.get("ord", {}).get("value", 0))):
                if "item" in row:
                    out.setdefault(row["term"]["value"], []).append(self._qid(row["item"]))
        return out

    def wikidata_search(self, terms: list[str], batch: int = 25) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for group in chunks(sorted({clean_term(t) for t in terms}), batch):
            values = " ".join(self._literal(t) for t in group)
            rows = self.sparql(
                f"SELECT ?term ?item WHERE {{ VALUES ?term {{ {values} }} "
                'SERVICE wikibase:mwapi { bd:serviceParam wikibase:endpoint "www.wikidata.org" ; '
                'wikibase:api "Search" ; mwapi:srsearch ?term ; mwapi:srlimit "5" ; wikibase:limit "once" . '
                "?item wikibase:apiOutputItem mwapi:title . } }"
            )
            for row in rows:
                if "item" in row and self._qid(row["item"]).startswith("Q"):
                    out.setdefault(row["term"]["value"], []).append(self._qid(row["item"]))
        return out

    def entities(self, qids: list[str]) -> dict[str, dict[str, Any]]:
        found: dict[str, dict[str, Any]] = {}
        langs = ", ".join(f"'{lang}'" for lang in LANGS)
        sites = " ".join(f"<https://{lang}.wikipedia.org/>" for lang in LANGS)

        def blank() -> dict[str, Any]:
            return {"labels": {}, "aliases": {}, "descriptions": {}, "sitelinks": {}}

        for batch in chunks(sorted(qids), 150):
            values = " ".join(f"wd:{q}" for q in batch)
            rows = self.sparql(
                f"SELECT ?item ?kind ?text WHERE {{ VALUES ?item {{ {values} }} "
                "{ ?item rdfs:label ?text . BIND('label' AS ?kind) } UNION "
                "{ ?item skos:altLabel ?text . BIND('alias' AS ?kind) } UNION "
                "{ ?item schema:description ?text . BIND('description' AS ?kind) } "
                f"FILTER(LANG(?text) IN ({langs})) }}"
            )
            for row in rows:
                entity = found.setdefault(self._qid(row["item"]), blank())
                lang = row["text"].get("xml:lang", "")
                kind = row["kind"]["value"]
                text = row["text"]["value"]
                if kind == "label":
                    entity["labels"][lang] = {"value": text}
                elif kind == "alias":
                    entity["aliases"].setdefault(lang, []).append({"value": text})
                else:
                    entity["descriptions"][lang] = {"value": text}
            rows = self.sparql(
                f"SELECT ?item ?site ?title WHERE {{ VALUES ?item {{ {values} }} VALUES ?site {{ {sites} }} "
                "?article schema:about ?item ; schema:isPartOf ?site ; schema:name ?title . }"
            )
            for row in rows:
                entity = found.setdefault(self._qid(row["item"]), blank())
                lang = row["site"]["value"].removeprefix("https://").split(".", 1)[0]
                entity["sitelinks"][f"{lang.replace('-', '_')}wiki"] = {"title": row["title"]["value"]}
            for qid in batch:
                found.setdefault(qid, blank())
        return found

    def claims(self, qids: list[str]) -> dict[str, dict[str, list[Any]]]:
        out: dict[str, dict[str, list[Any]]] = {}
        props = " ".join(f"wdt:{p}" for p in CLAIM_PROPS)
        for batch in chunks(sorted(qids), 120):
            values = " ".join(f"wd:{q}" for q in batch)
            rows = self.sparql(
                f"SELECT ?item ?prop ?value WHERE {{ VALUES ?item {{ {values} }} VALUES ?prop {{ {props} }} "
                "?item ?prop ?value . }"
            )
            for row in rows:
                qid = row["item"]["value"].rsplit("/", 1)[1]
                prop = row["prop"]["value"].rsplit("/", 1)[1]
                value = row["value"]["value"]
                if value.startswith("http://www.wikidata.org/entity/"):
                    value = value.rsplit("/", 1)[1]
                out.setdefault(qid, {}).setdefault(prop, []).append(value)
        return out

    def coordinates(self, qids: list[str]) -> dict[str, dict[str, float]]:
        out: dict[str, dict[str, float]] = {}
        for batch in chunks(sorted(qids), 200):
            values = " ".join(f"wd:{q}" for q in batch)
            rows = self.sparql(f"SELECT ?item ?c WHERE {{ VALUES ?item {{ {values} }} ?item wdt:P625 ?c . }}")
            for row in rows:
                point = parse_coord(row["c"]["value"])
                if point:
                    out.setdefault(self._qid(row["item"]), point)
        return out

    def labels(self, qids: list[str]) -> dict[str, str]:
        out: dict[str, str] = {}
        for batch in chunks(sorted(qids), 200):
            values = " ".join(f"wd:{q}" for q in batch)
            rows = self.sparql(
                f"SELECT ?item ?label WHERE {{ VALUES ?item {{ {values} }} ?item rdfs:label ?label . "
                "FILTER(LANG(?label) = 'en') }"
            )
            for row in rows:
                out[row["item"]["value"].rsplit("/", 1)[1]] = row["label"]["value"]
        return out

    def enwiki_pages(self, titles: list[str], batch: int = 40) -> dict[str, dict[str, Any]]:
        out: dict[str, dict[str, Any]] = {}
        for group in chunks(sorted(set(titles)), batch):
            values = " ".join(self._literal(t) for t in group)
            rows = self.sparql(
                f"SELECT ?title ?category WHERE {{ VALUES ?title {{ {values} }} "
                'SERVICE wikibase:mwapi { bd:serviceParam wikibase:endpoint "en.wikipedia.org" ; '
                'wikibase:api "Categories" ; mwapi:titles ?title ; mwapi:clshow "!hidden" . '
                "?category wikibase:apiOutput mwapi:category . } }"
            )
            for title in group:
                out.setdefault(title, {"categories": [], "coordinates": [], "description": ""})
            for row in rows:
                if "category" in row:
                    entry = out.setdefault(
                        row["title"]["value"], {"categories": [], "coordinates": [], "description": ""}
                    )
                    entry["categories"].append(row["category"]["value"].removeprefix("Category:"))
        for entry in out.values():
            entry["categories"] = sorted(set(entry["categories"]))
        return out


def parse_coord(value: str) -> dict[str, float] | None:
    match = re.match(r"Point\(([-0-9.eE]+) ([-0-9.eE]+)\)", value)
    if not match:
        return None
    return {"lat": round(float(match.group(2)), 6), "lon": round(float(match.group(1)), 6)}
