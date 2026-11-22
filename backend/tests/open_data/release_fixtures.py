from dataclasses import replace

from app.services.open_data_release import ReleaseStamp
from app.services.open_data_rows import OpenDataTables, checked_tables
from app.services.open_data_scope import ReleaseScope
from app.services.open_data_tables import TABLES

__all__ = [
    "AJRAKH",
    "AJRAKH_STAMP",
    "SITE",
    "STAMP",
    "empty_tables",
    "family_row",
    "tables_with",
]

SITE = "https://kalavigyan.example"
STAMP = ReleaseStamp(
    target="SANDBOX",
    version="2026.11.21",
    doi="10.5072/zenodo.200",
    concept_doi="10.5072/zenodo.199",
    record_id=200,
    concept_record_id=199,
)
AJRAKH = ReleaseScope(craft="Kutch-Ajrakh", name="Kutch Ajrakh")
AJRAKH_STAMP = replace(STAMP, craft="Kutch-Ajrakh")


def empty_tables() -> OpenDataTables:
    return checked_tables({table.name: [] for table in TABLES})


def family_row(slug: str, name: str, sort_order: int) -> dict[str, object]:
    return {"slug": slug, "name": name, "category": "Textiles-Based-Craft-Category", "sort_order": sort_order}


def tables_with(**rows: list[dict[str, object]]) -> OpenDataTables:
    return checked_tables({table.name: list(rows.get(table.name, [])) for table in TABLES})
