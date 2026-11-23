from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from app.curation.files import CURATION_DIR
from app.models import Source
from app.research.citations import SourceRef
from app.research.craft_page import CraftPage
from app.science.records import CompoundRecord

from .category_preview import category_dossier_records
from .chapter_context import ChapterRows
from .chapter_family import family_science
from .chapter_inputs import chapter_inputs, inputs_records, inputs_rows
from .craft_page import craft_page
from .craft_page_records import CraftPageRecords
from .curated_compounds import curated_compounds
from .curation_preview import dossier_records
from .knowledge_view import source_ref

__all__ = ["PREVIEW_SITE", "chapter_preview", "preview_rows"]

PREVIEW_SITE = "https://kalavigyan.vercel.app"


def chapter_preview(
    craft_slug: str, *, family: str | None = None, inputs: Path | None = None, directory: Path = CURATION_DIR
) -> CraftPage:
    records = dossier_records(craft_slug, directory=directory)
    if inputs is not None:
        records = inputs_records(chapter_inputs(inputs), records)
    return craft_page(records, preview_rows(records, family=family, inputs=inputs, directory=directory))


def preview_rows(
    records: CraftPageRecords, *, family: str | None, inputs: Path | None, directory: Path = CURATION_DIR
) -> ChapterRows:
    rows = replace(_compound_rows(records), site=PREVIEW_SITE)
    if family is not None:
        rows = replace(
            rows, family=family_science(category_dossier_records(family, directory=directory), records.craft)
        )
    if inputs is not None:
        rows = inputs_rows(chapter_inputs(inputs), rows, goldens=inputs.parent)
    return rows


def _compound_rows(records: CraftPageRecords) -> ChapterRows:
    curated = records.curated
    if curated is None:
        return ChapterRows()
    plan = curated_compounds(
        curated.materials, stored_cids=(), stored_sources={}, retrieved_at=curated.curated_at
    )
    compounds = {
        row["id"]: CompoundRecord(row["id"], row["name"], row["formula"], row["pubchemCid"], row["sourceId"])
        for row in plan.compounds
    }
    by_cid = {compound.pubchem_cid: compound.id for compound in compounds.values()}
    linked = {
        item.material_id: by_cid[item.pubchem_cid] for item in curated.materials if item.pubchem_cid in by_cid
    }
    sources = {str(row["id"]): SourceRef.model_validate(source_ref(Source(**row))) for row in plan.sources}
    return ChapterRows(compounds=compounds, material_compounds=linked, record_sources=sources)
