from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

__all__ = [
    "APPROVED_CAP_USD",
    "CapLedger",
    "Recorded",
    "Recorder",
    "approved_cap",
    "written_fixture",
]

APPROVED_CAP_USD = Decimal("5")
JSON_TYPE = "application/json"


def approved_cap(value: str) -> Decimal:
    cap = Decimal(value)
    if not Decimal(0) < cap <= APPROVED_CAP_USD:
        raise ValueError(f"the owner approved at most US${APPROVED_CAP_USD} for the paid checks, not {value}")
    return cap


@dataclass
class CapLedger:
    cap_usd: Decimal
    spent_usd: Decimal = Decimal(0)
    rows: list[dict[str, Any]] = field(default_factory=list)

    def allows(self, estimate_usd: Decimal) -> bool:
        return self.spent_usd + estimate_usd <= self.cap_usd

    def spend(self, check: str, estimate_usd: Decimal, actual_usd: Decimal | None = None) -> None:
        counted = estimate_usd if actual_usd is None else max(actual_usd, Decimal(0))
        self.spent_usd += counted
        self.rows.append({"check": check, "estimateUsd": str(estimate_usd), "countedUsd": str(counted)})

    def skip(self, check: str, estimate_usd: Decimal) -> None:
        self.rows.append({"check": check, "estimateUsd": str(estimate_usd), "skipped": "cap"})


@dataclass(frozen=True)
class Recorded:
    method: str
    path: str
    status: int
    content_type: str
    body: bytes

    def fixture(self) -> bytes:
        if JSON_TYPE in self.content_type:
            return (json.dumps(json.loads(self.body), indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        return self.body


class Recorder:
    def __init__(self) -> None:
        self.replies: list[Recorded] = []

    async def __call__(self, response: httpx.Response) -> None:
        await response.aread()
        request = response.request
        self.replies.append(
            Recorded(
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                content_type=response.headers.get("content-type", ""),
                body=response.content,
            )
        )

    def last(self, path_end: str) -> Recorded | None:
        return next((reply for reply in reversed(self.replies) if reply.path.endswith(path_end)), None)


def written_fixture(folder: Path, name: str, body: bytes) -> str:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_bytes(body)
    return name
