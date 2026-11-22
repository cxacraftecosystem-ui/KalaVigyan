from __future__ import annotations

import html
from collections.abc import Mapping
from datetime import date

from .open_data_tables import TABLES

__all__ = [
    "ATTRIBUTION",
    "BIBTEX_KEY",
    "CITED_WORKS",
    "CODE_URL",
    "CREATOR",
    "DATASET_TITLE",
    "KEYWORDS",
    "LEFT_OUT",
    "LICENCE_ID",
    "LICENCE_NAME",
    "LICENCE_URL",
    "PUBLISHER",
    "SUMMARY",
    "citation_bibtex",
    "citation_text",
    "data_page",
    "page_citation_bibtex",
    "page_citation_text",
    "zenodo_description",
]

DATASET_TITLE = "KalaVigyan open knowledge"
BIBTEX_KEY = "kalavigyan_open_knowledge"
CREATOR = "KalaVigyan, Centre of Excellence for Unified AI-Enabled Craft Ecosystem Platform, IIT Kharagpur"
PUBLISHER = "Zenodo"
LICENCE_ID = "CC-BY-4.0"
LICENCE_NAME = "Creative Commons Attribution 4.0 International"
LICENCE_URL = "https://creativecommons.org/licenses/by/4.0/"
CODE_URL = "https://github.com/cxacraftecosystem-ui/KalaVigyan"
DATA_PATH = "/data"
SUMMARY = (
    "Cited facts about India's crafts and the science behind them, with the sources they rest on and where "
    "in each source the supporting words stand; the crafts, families and categories with their Wikidata and "
    "Local Government Directory identifiers; the curated structure of each craft (stages, materials and "
    "tools, reactions as stated, native names and geographical indications); the catalogue of KalaVigyan's "
    "figures and components; and the records of the open datasets behind its maps."
)
ATTRIBUTION = (
    f"{CREATOR}. {DATASET_TITLE}, licensed under CC BY 4.0. Name KalaVigyan and the Centre, and link the "
    "dataset's DOI, wherever this data is shown."
)
CITED_WORKS = (
    "KalaVigyan's licence covers its own sentences and structure. The works its facts cite keep their own "
    "licences: the release carries none of their words, only where each supporting passage stands and a "
    "link to read it at its source."
)
LEFT_OUT = (
    "Verbatim quotes from the cited works, which stay under their own terms; read them at the source by the locator.",
    "The names of contributors and reviewers.",
    "Facts held while a quote is checked again, texts that contributors supplied privately, field "
    "recordings, field photographs and personal accounts.",
    "The values of the map datasets: their records are here, and their values come from their publishers.",
)
KEYWORDS = (
    "Indian crafts",
    "handicrafts",
    "craft science",
    "traditional knowledge",
    "cultural heritage",
    "materials",
    "natural dyes",
    "India",
    "open data",
)


def data_page(site: str) -> str:
    return f"{site.rstrip('/')}{DATA_PATH}"


def citation_text(version: str, released: date, doi: str, *, title: str = DATASET_TITLE) -> str:
    return (
        f"{CREATOR}. ({released.year}). {title} (Version {version}) [Data set]. "
        f"{PUBLISHER}. https://doi.org/{doi}"
    )


def citation_bibtex(
    version: str, released: date, doi: str, *, title: str = DATASET_TITLE, key: str = BIBTEX_KEY
) -> str:
    versioned = f"{key}_{version.replace('.', '_')}"
    fields = (
        ("author", f"{{{CREATOR}}}"),
        ("title", title),
        ("year", str(released.year)),
        ("version", version),
        ("publisher", PUBLISHER),
        ("doi", doi),
        ("url", f"https://doi.org/{doi}"),
    )
    lines = [f"  {name} = {{{value}}}" for name, value in fields]
    return f"@misc{{{versioned},\n" + ",\n".join(lines) + "\n}"


def page_citation_text(site: str) -> str:
    return f"{CREATOR}. {DATASET_TITLE} [Data set]. {data_page(site)}"


def page_citation_bibtex(site: str) -> str:
    fields = (("author", f"{{{CREATOR}}}"), ("title", DATASET_TITLE), ("url", data_page(site)))
    lines = [f"  {name} = {{{value}}}" for name, value in fields]
    return "@misc{kalavigyan_open_knowledge,\n" + ",\n".join(lines) + "\n}"


def zenodo_description(counts: Mapping[str, int], *, summary: str = SUMMARY) -> str:
    rows = "".join(
        f"<li>{html.escape(table.title)} ({html.escape(table.name)}): {counts.get(table.name, 0)}</li>"
        for table in TABLES
    )
    left_out = "".join(f"<li>{html.escape(item)}</li>" for item in LEFT_OUT)
    return (
        f"<p>{html.escape(summary)}</p>"
        f"<p>{html.escape(CITED_WORKS)}</p>"
        f"<p>Rows in this version:</p><ul>{rows}</ul>"
        f"<p>Left out:</p><ul>{left_out}</ul>"
        "<p>Each table comes as JSON Lines and as CSV, described field by field in datapackage.json "
        "(a Frictionless Data Package). SHA256SUMS lists a SHA-256 checksum for every file.</p>"
    )
