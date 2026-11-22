from __future__ import annotations

import json
import uuid
from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel

from .blocks import BlockBase
from .citation_export import (
    BIBTEX_TYPES,
    CITATION_FORMATS,
    CSL_TYPES,
    DATASET_ROW_KIND,
    RIS_END,
    RIS_TYPES,
    CitationEntry,
    CitationExport,
    CslItem,
    citation_key,
)
from .citations import SourceRef
from .datasets import DatasetRef

__all__ = [
    "CITATION_EXPORT_SCHEMA_VERSION",
    "CITATION_MEDIA_TYPES",
    "ApaReferences",
    "CitationFile",
    "CitedThing",
    "bibtex_entry",
    "citation_entries",
    "citation_file",
    "cited_datasets",
    "csl_item",
    "dataset_access_key",
    "exported_citations",
    "ris_record",
]

CITATION_EXPORT_SCHEMA_VERSION = 1
CITATION_MEDIA_TYPES: Mapping[str, str] = MappingProxyType(
    {
        "bib": "application/x-bibtex",
        "ris": "application/x-research-info-systems",
        "txt": "text/plain",
        "json": "application/vnd.citationstyles.csl+json",
    }
)
BIBTEX_VENUES: Mapping[str, str] = MappingProxyType(
    {"article": "publisher", "book": "publisher", "incollection": "publisher", "techreport": "institution"}
)
BIBTEX_CONTAINERS: Mapping[str, str] = MappingProxyType({"article": "journal", "incollection": "booktitle"})
BIBTEX_ESCAPES: Mapping[str, str] = MappingProxyType(
    {
        "\\": r"\textbackslash{}",
        "{": r"\textbraceleft{}",
        "}": r"\textbraceright{}",
        "%": r"\%",
        "&": r"\&",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
)
BIBTEX_LINK_ESCAPES: Mapping[str, str] = MappingProxyType({"\\": "%5C", "{": "%7B", "}": "%7D"})
RIS_LINE_END = "\r\n"
DATASET_ACCESS_PREFIX = "dataset:"

CitedThing = SourceRef | DatasetRef
ApaReferences = Callable[[Sequence[CslItem]], list[str]]


@dataclass(frozen=True)
class CitationFile:
    text: str
    media_type: str
    extension: str


def dataset_access_key(code: str) -> str:
    return f"{DATASET_ACCESS_PREFIX}{code}"


def cited_datasets(blocks: Iterable[BlockBase]) -> list[DatasetRef]:
    found: dict[str, DatasetRef] = {}
    for block in blocks:
        for dataset in _datasets_in(block):
            found.setdefault(dataset.code, dataset)
    return list(found.values())


def csl_item(number: int, cited: CitedThing, accessed: date | None) -> CslItem:
    fields: dict[str, Any] = {"id": citation_key(number)}
    if isinstance(cited, SourceRef):
        fields |= {
            "type": CSL_TYPES[cited.kind],
            "title": cited.title,
            "author": [{"literal": name} for name in cited.authors if name.strip()],
            "container-title": cited.container_title,
            "publisher": _house(cited, beside_container=True),
            "DOI": cited.doi or None,
            "URL": cited.url,
        }
        if cited.year is not None:
            fields["issued"] = {"date-parts": [[cited.year]]}
    else:
        fields |= {
            "type": CSL_TYPES[DATASET_ROW_KIND],
            "title": cited.title,
            "author": [{"literal": cited.publisher}] if cited.publisher else [],
            "publisher": cited.publisher,
            "version": cited.edition,
            "URL": cited.url,
        }
    if accessed is not None:
        fields["accessed"] = {"date-parts": [[accessed.year, accessed.month, accessed.day]]}
    return CslItem.model_validate(fields)


def bibtex_entry(number: int, cited: CitedThing) -> str:
    kind = cited.kind if isinstance(cited, SourceRef) else DATASET_ROW_KIND
    entry_type = BIBTEX_TYPES[kind]
    names = _names(cited)
    fields = [
        ("author", " and ".join(f"{{{_escaped(name)}}}" for name in names) if names else None),
        ("title", f"{{{_escaped(cited.title)}}}"),
        *((name, _escaped(value)) for name, value in _bibtex_venues(entry_type, cited)),
        ("year", str(cited.year) if isinstance(cited, SourceRef) and cited.year is not None else None),
        ("doi", _link(cited.doi) if isinstance(cited, SourceRef) and cited.doi else None),
        ("url", _link(cited.url) if cited.url else None),
    ]
    lines = [f"  {name} = {{{value}}}," for name, value in fields if value]
    return "\n".join([f"@{entry_type}{{{citation_key(number)},", *lines, "}"]) + "\n"


def ris_record(number: int, cited: CitedThing) -> str:
    kind = cited.kind if isinstance(cited, SourceRef) else DATASET_ROW_KIND
    year = cited.year if isinstance(cited, SourceRef) else None
    tags = [
        ("TY", RIS_TYPES[kind]),
        *(("AU", name) for name in _names(cited)),
        ("TI", cited.title),
        ("PY", str(year) if year is not None else None),
        ("T2", cited.container_title if isinstance(cited, SourceRef) else None),
        ("PB", _house(cited, beside_container=True)),
        ("DO", cited.doi if isinstance(cited, SourceRef) else None),
        ("UR", cited.url),
        ("ID", citation_key(number)),
    ]
    lines = [f"{tag}  - {_one_line(value)}{RIS_LINE_END}" for tag, value in tags if value]
    return "".join(lines) + RIS_END


def citation_entries(
    cited: Sequence[CitedThing], *, accessed: Mapping[str, date], apa: ApaReferences
) -> list[CitationEntry]:
    items = [
        csl_item(number, thing, accessed.get(_access_key(thing))) for number, thing in enumerate(cited, 1)
    ]
    references = apa(items)
    if len(references) != len(items):
        raise ValueError(f"the APA style wrote {len(references)} references for {len(items)} citations")
    return [
        CitationEntry(
            number=number,
            source_id=thing.id if isinstance(thing, SourceRef) else None,
            dataset_code=thing.code if isinstance(thing, DatasetRef) else None,
            csl=item,
            apa=_dataset_citation(thing) or reference,
            bibtex=bibtex_entry(number, thing),
            ris=ris_record(number, thing),
        )
        for number, (thing, item, reference) in enumerate(zip(cited, items, references, strict=True), 1)
    ]


def exported_citations(
    explainer_id: uuid.UUID, version: int, entries: Sequence[CitationEntry]
) -> CitationExport:
    return CitationExport(
        schema_version=CITATION_EXPORT_SCHEMA_VERSION,
        explainer_id=explainer_id,
        version=version,
        entries=list(entries),
    )


def citation_file(export: CitationExport, fmt: str) -> CitationFile:
    if fmt not in CITATION_FORMATS:
        raise ValueError(f"citations are written as {', '.join(CITATION_FORMATS)}, not {fmt!r}")
    entries = export.entries
    if fmt == "bib":
        text = "\n".join(entry.bibtex for entry in entries)
    elif fmt == "ris":
        text = "".join(entry.ris for entry in entries)
    elif fmt == "txt":
        text = "".join(f"[{entry.number}] {entry.apa}\n" for entry in entries)
    else:
        items = [entry.csl.model_dump(mode="json", by_alias=True) for entry in entries]
        text = json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    return CitationFile(text=text, media_type=CITATION_MEDIA_TYPES[fmt], extension=fmt)


def _datasets_in(value: object) -> Iterator[DatasetRef]:
    if isinstance(value, DatasetRef):
        yield value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from _datasets_in(getattr(value, name))
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _datasets_in(item)


def _access_key(thing: CitedThing) -> str:
    return thing.id if isinstance(thing, SourceRef) else dataset_access_key(thing.code)


def _names(cited: CitedThing) -> list[str]:
    if isinstance(cited, SourceRef):
        return [name for name in cited.authors if name.strip()]
    return [cited.publisher] if cited.publisher else []


def _bibtex_venues(entry_type: str, cited: CitedThing) -> list[tuple[str, str]]:
    container = cited.container_title if isinstance(cited, SourceRef) else None
    holder = BIBTEX_CONTAINERS.get(entry_type)
    shown = [(holder, container)] if holder and container else []
    house = _house(cited, beside_container=bool(shown))
    return [*shown, *([(BIBTEX_VENUES.get(entry_type, "howpublished"), house)] if house else [])]


def _house(cited: CitedThing, *, beside_container: bool) -> str | None:
    container = cited.container_title if isinstance(cited, SourceRef) else None
    if beside_container and container is not None and cited.publisher == container:
        return None
    return cited.publisher or None


def _dataset_citation(thing: CitedThing) -> str | None:
    return thing.citation if isinstance(thing, DatasetRef) and thing.citation else None


def _escaped(text: str) -> str:
    return "".join(BIBTEX_ESCAPES.get(ch, ch) for ch in text)


def _link(text: str) -> str:
    return "".join(BIBTEX_LINK_ESCAPES.get(ch, ch) for ch in text)


def _one_line(text: str) -> str:
    return " ".join(text.split())
