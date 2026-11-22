from __future__ import annotations

from datetime import UTC, datetime
from math import ceil

from app.core.allowances import Ask, Bucket, Counted, bucket_of


class MemoryCounter:
    def __init__(self, store: dict[Bucket, int] | None = None) -> None:
        self.used: dict[Bucket, int] = {} if store is None else store

    async def take(self, bucket: Bucket, ask: Ask) -> Counted:
        used = self.used.get(bucket, 0)
        earlier = self.used.get(bucket.before, 0)
        granted = min(ask.wanted, max(0, ask.limit - used - ceil(earlier * ask.earlier_share)))
        self.used[bucket] = used + granted
        return Counted(granted=granted, used=used + granted, earlier=earlier)

    async def give_back(self, bucket: Bucket) -> None:
        if bucket in self.used:
            self.used[bucket] = max(0, self.used[bucket] - 1)

    def asked(self, holder: str, kind: str) -> bool:
        return any((bucket.holder, bucket.kind) == (holder, kind) for bucket in self.used)

    def fill(self, holder: str, kind: str, used: int) -> None:
        self.used[bucket_of(holder, kind, datetime.now(UTC))] = used
