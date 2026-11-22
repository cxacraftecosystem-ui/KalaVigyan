from __future__ import annotations

from collections.abc import Mapping, Sequence
from itertools import batched

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.layers import MAP_LAYERS
from app.models import EnvDataset, KnowledgePiece

from .component_library import library_components, registered_pieces
from .knowledge_export import EXPORT_COMPONENTS_MAX
from .open_data_values import Row, day_of, published_ids

__all__ = ["component_rows", "dataset_codes", "dataset_rows", "payload_dataset_codes"]

LABEL_BATCH = 1000
DATASETS_KEY = "datasets"
CODE_KEY = "code"


async def dataset_codes(session: AsyncSession, labels: Sequence[str]) -> set[str]:
    codes: set[str] = set()
    for chunk in batched(labels, LABEL_BATCH, strict=False):
        payloads = await session.scalars(
            select(KnowledgePiece.payload).where(KnowledgePiece.label.in_(list(chunk)), *registered_pieces())
        )
        for payload in payloads.all():
            codes |= payload_dataset_codes(payload)
    return codes


def payload_dataset_codes(value: object) -> set[str]:
    if isinstance(value, Mapping):
        codes: set[str] = set()
        for key, item in value.items():
            codes |= _named_codes(item) if key == DATASETS_KEY else payload_dataset_codes(item)
        return codes
    if isinstance(value, list):
        return {code for item in value for code in payload_dataset_codes(item)}
    return set()


def _named_codes(value: object) -> set[str]:
    if not isinstance(value, list):
        return payload_dataset_codes(value)
    return {
        item[CODE_KEY] for item in value if isinstance(item, Mapping) and isinstance(item.get(CODE_KEY), str)
    }


async def component_rows(session: AsyncSession, shown: set[str]) -> list[Row]:
    listed = (await library_components(session, limit=EXPORT_COMPONENTS_MAX)).components
    resting = await _resting_claims(session, [component.label for component in listed])
    rows: list[Row] = []
    for component in listed:
        claims = published_ids(resting.get(component.label, []), shown)
        if not claims:
            continue
        rows.append(
            {
                "label": component.label,
                "kind": component.kind,
                "title": component.title,
                "description": component.description or None,
                "field": component.field,
                "fields": list(component.fields),
                "craft": component.craft_slug,
                "subjects": [
                    {"kind": subject.kind, "key": subject.key, "name": subject.name}
                    for subject in component.subjects
                ],
                "claim_ids": claims,
            }
        )
    return sorted(rows, key=lambda row: row["label"])


async def _resting_claims(session: AsyncSession, labels: list[str]) -> dict[str, list[object]]:
    found: dict[str, list[object]] = {}
    for chunk in batched(labels, LABEL_BATCH, strict=False):
        rows = await session.execute(
            select(KnowledgePiece.label, KnowledgePiece.claimIds).where(KnowledgePiece.label.in_(list(chunk)))
        )
        for label, claim_ids in rows.all():
            if label is not None:
                found[label] = list(claim_ids or [])
    return found


async def dataset_rows(session: AsyncSession) -> list[Row]:
    layers: dict[str, list[str]] = {}
    for spec in MAP_LAYERS:
        layers.setdefault(spec.dataset_code, []).append(spec.id)
    rows = (await session.scalars(select(EnvDataset).order_by(EnvDataset.code))).all()
    return [
        {
            "code": dataset.code,
            "title": dataset.title,
            "publisher": dataset.publisher,
            "edition": dataset.edition,
            "period": dataset.period,
            "native_resolution": dataset.nativeResolution,
            "crs": dataset.crs,
            "licence": dataset.licence,
            "licence_url": dataset.licenceUrl,
            "attribution": dataset.attribution,
            "redistributable": bool(dataset.redistributable),
            "citation": dataset.citation,
            "url": dataset.url,
            "retrieved": day_of(dataset.retrievedAt),
            "sha256": dataset.sha256,
            "layers": sorted(layers.get(dataset.code, [])),
        }
        for dataset in rows
    ]
