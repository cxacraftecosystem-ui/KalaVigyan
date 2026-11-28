from __future__ import annotations

from collections.abc import Sequence

from app.research.datasets import DatasetRef

from .layer_records import SiteLayer, site_layers

__all__ = ["MAP_LAYERS_TOPIC", "NO_RECORD_HELD", "layers_text", "map_layers_text"]

MAP_LAYERS_TOPIC = "map-layers"
NO_RECORD_HELD = "no dataset record: a map that names it is refused until its record is held"
NOT_NAMED = "none: a places map draws it in a close frame of its own"
HEAD = (
    "# The map layers and their dataset records\n\n"
    "Every layer the site's maps draw beneath a page's places, with the dataset record it rests on, as the "
    "dataset guide records one (`datasets/1`): the code, title, publisher, edition, version, period, native "
    "resolution, coordinate reference system, licence and its address, attribution, whether the data may be "
    "redistributed, citation and DOI, landing page and, for a layer built into a file, the day each download "
    "was read and its SHA-256. A declared `timeline_map` names a layer in `layers` by the name below; the "
    "server writes each record into the stored spec and the page prints each credit under the map, so a "
    "contribution sends no datasets and cites no layer as a fact. A district layer is drawn only where the site "
    "holds its values, and its record is the run's own, so a field the registry writes as set per run is filled "
    "by that run.\n"
)
TABLE_HEAD = "## The layers\n\n| Name in `layers` | Layer | What it draws | Rests on |\n|---|---|---|---|\n"
RECORDS_HEAD = "## The dataset records\n"
FIELDS = (
    ("Title", "title"),
    ("Publisher", "publisher"),
    ("Edition", "edition"),
    ("Version", "version"),
    ("Period", "period"),
    ("Native resolution", "native_resolution"),
    ("Coordinate reference system", "crs"),
    ("Licence", "licence"),
    ("Licence address", "licence_url"),
    ("Attribution", "attribution"),
    ("Redistributable", "redistributable"),
    ("Citation", "citation"),
    ("DOI", "doi"),
    ("Landing page", "landing_url"),
    ("File read from", "url"),
    ("Read on", "read_on"),
    ("SHA-256", "sha256"),
)


def map_layers_text() -> str:
    return layers_text(site_layers())


def layers_text(layers: Sequence[SiteLayer]) -> str:
    rows = "".join(_row(layer) for layer in layers)
    records: dict[str, tuple[DatasetRef, list[str]]] = {}
    for layer in layers:
        for record in layer.records:
            records.setdefault(record.code, (record, []))[1].append(layer.name)
    shown = "".join(_record(record, names) for record, names in records.values())
    return f"{HEAD}\n{TABLE_HEAD}{rows}\n{RECORDS_HEAD}{shown}"


def _row(layer: SiteLayer) -> str:
    name = f"`{layer.name}`" if layer.named else NOT_NAMED
    rests = ", ".join(f"`{record.code}`" for record in layer.records) or NO_RECORD_HELD
    return f"| {name} | {_cell(layer.title)} | {_cell(layer.draws)} | {rests} |\n"


def _record(record: DatasetRef, names: Sequence[str]) -> str:
    lines = [f"\n### {record.code}\n\n| Field | Value |\n|---|---|\n"]
    for label, attribute in FIELDS:
        value = getattr(record, attribute)
        if value is not None:
            lines.append(f"| {label} | {_cell(_shown(value))} |\n")
    lines.append(f"| Layers | {', '.join(f'`{name}`' for name in names)} |\n")
    return "".join(lines)


def _shown(value: object) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def _cell(text: str) -> str:
    return " ".join(text.replace("|", "/").split())
