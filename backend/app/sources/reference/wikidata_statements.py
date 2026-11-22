from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import unquote

from ..records import clean_text
from .mediawiki import primary_language
from .wikidata_times import time_text

__all__ = [
    "ENTITY_PREFIX",
    "EXTERNAL_ID_NAMES",
    "ITEM_ID",
    "ONTOLOGY_PREFIX",
    "Statement",
    "binding_value",
    "external_ids_of",
    "statement_lines",
    "statements_from_bindings",
    "statements_query",
]

ITEM_ID = re.compile(r"^Q[1-9]\d*$")
ENTITY_PREFIX = "http://www.wikidata.org/entity/"
ONTOLOGY_PREFIX = "http://wikiba.se/ontology#"
FILE_PATH_PREFIX = "http://commons.wikimedia.org/wiki/Special:FilePath/"
UNITLESS = f"{ENTITY_PREFIX}Q199"
EXTERNAL_ID_NAMES = {"P662": "pubchem_cid", "P231": "cas_number", "P683": "chebi"}
STATEMENTS_QUERY = """SELECT ?property ?propertyLabel ?type ?value ?valueLabel ?unit ?unitLabel ?precision WHERE {
  VALUES ?item { wd:%(item)s }
  ?item ?claim ?statement .
  ?property wikibase:claim ?claim ; wikibase:statementProperty ?ps ; wikibase:propertyType ?type .
  ?statement ?ps ?value ; wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
  OPTIONAL {
    ?property wikibase:statementValue ?psv .
    ?statement ?psv ?node .
    OPTIONAL { ?node wikibase:quantityUnit ?unit . }
    OPTIONAL { ?node wikibase:timePrecision ?precision . }
  }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "%(languages)s". }
}"""


@dataclass(frozen=True, order=True)
class Statement:
    property_number: int
    property_label: str
    value: str
    value_type: str


def statements_query(item_id: str, language: str) -> str:
    if not ITEM_ID.match(item_id):
        raise ValueError(f"{item_id!r} is not a Wikidata item id")
    languages = ",".join(dict.fromkeys([primary_language(language), "mul", "en"]))
    return STATEMENTS_QUERY % {"item": item_id, "languages": languages}


def statements_from_bindings(bindings: Iterable[Mapping[str, Any]]) -> list[Statement]:
    found: set[Statement] = set()
    for row in bindings:
        statement = _statement(row)
        if statement is not None:
            found.add(statement)
    return sorted(found)


def statement_lines(statements: Iterable[Statement]) -> list[str]:
    grouped: dict[tuple[int, str], list[str]] = {}
    for statement in statements:
        if statement.value_type == "ExternalId":
            continue
        grouped.setdefault((statement.property_number, statement.property_label), []).append(statement.value)
    return [f"{label}: {'; '.join(values)}" for (_number, label), values in sorted(grouped.items())]


def external_ids_of(statements: Iterable[Statement]) -> dict[str, str]:
    found: dict[str, str] = {}
    for statement in statements:
        name = EXTERNAL_ID_NAMES.get(f"P{statement.property_number}")
        if name and statement.value_type == "ExternalId" and name not in found:
            found[name] = statement.value
    return found


def binding_value(row: Mapping[str, Any], name: str) -> str | None:
    cell = row.get(name)
    return clean_text(cell.get("value")) if isinstance(cell, Mapping) else None


def _statement(row: Mapping[str, Any]) -> Statement | None:
    property_iri = binding_value(row, "property") or ""
    label = binding_value(row, "propertyLabel")
    value_type = (binding_value(row, "type") or "").removeprefix(ONTOLOGY_PREFIX)
    number = property_iri.removeprefix(ENTITY_PREFIX).removeprefix("P")
    if not number.isdigit() or not label:
        return None
    value = _rendered_value(row, value_type)
    if value is None:
        return None
    return Statement(int(number), label, value, value_type)


def _rendered_value(row: Mapping[str, Any], value_type: str) -> str | None:
    raw = binding_value(row, "value")
    if raw is None:
        return None
    if value_type == "WikibaseItem":
        return binding_value(row, "valueLabel") or raw.removeprefix(ENTITY_PREFIX)
    if value_type == "Quantity":
        unit = binding_value(row, "unit")
        unit_label = binding_value(row, "unitLabel")
        return raw if unit in (None, UNITLESS) or not unit_label else f"{raw} {unit_label}"
    if value_type == "Time":
        return time_text(raw, binding_value(row, "precision"))
    if value_type == "CommonsMedia":
        return unquote(raw.removeprefix(FILE_PATH_PREFIX))
    return raw
