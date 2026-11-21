from __future__ import annotations

import re
import uuid

__all__ = ["GAP_DETAIL_PREFIX", "GAP_TASK", "gap_detail", "gap_id", "is_gap_detail"]

GAP_TASK = "ANSWER_GAP"
GAP_DETAIL_PREFIX = "gap-"
GAP_DETAIL = re.compile(rf"^{GAP_DETAIL_PREFIX}[0-9a-f]{{32}}$")


def gap_detail(gap: uuid.UUID) -> str:
    return f"{GAP_DETAIL_PREFIX}{gap.hex}"


def is_gap_detail(detail: str) -> bool:
    return GAP_DETAIL.match(detail) is not None


def gap_id(detail: str) -> uuid.UUID | None:
    return uuid.UUID(hex=detail.removeprefix(GAP_DETAIL_PREFIX)) if is_gap_detail(detail) else None
