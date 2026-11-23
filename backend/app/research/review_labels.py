from __future__ import annotations

from .review_queue_items import (
    ComponentItem,
    FactItem,
    LayerQueueItem,
    LayoutItem,
    ReadingQueueItem,
    StageQueueItem,
    StructureQueueItem,
)

__all__ = ["LABEL_MAX_CHARS", "cut_label", "queue_label"]

LABEL_MAX_CHARS = 300
ELLIPSIS = "…"

Labelled = (
    FactItem
    | ComponentItem
    | LayoutItem
    | StructureQueueItem
    | ReadingQueueItem
    | LayerQueueItem
    | StageQueueItem
)


def queue_label(item: Labelled) -> str:
    if isinstance(item, FactItem):
        return cut_label(item.fact.statement)
    if isinstance(item, ComponentItem):
        return cut_label(f"Component: {item.component.title}")
    if isinstance(item, LayoutItem):
        return cut_label(f"Layout of {item.layout.subject_name}")
    if isinstance(item, StructureQueueItem):
        said = item.structure.statement or item.structure.kind.replace("_", " ").lower()
        return cut_label(f"{item.structure.subject_name}: {said}")
    if isinstance(item, ReadingQueueItem):
        return cut_label(f"{item.reading.stage}: {item.reading.stated}")
    if isinstance(item, LayerQueueItem):
        return cut_label(f"Map layer: {item.layer.dataset.title}")
    return cut_label(f"Stage: {item.stage.name}")


def cut_label(text: str) -> str:
    flat = " ".join(text.split())
    if len(flat) <= LABEL_MAX_CHARS:
        return flat
    return flat[: LABEL_MAX_CHARS - len(ELLIPSIS)].rstrip() + ELLIPSIS
