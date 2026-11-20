from __future__ import annotations

from app.core.allowances import Ask, Bucket


class MemoryCounter:
    def __init__(self) -> None:
        self.used: dict[tuple[str, str], int] = {}

    async def take(self, bucket: Bucket, ask: Ask) -> int:
        key = (bucket.holder, bucket.kind)
        used = self.used.get(key, 0)
        granted = min(ask.wanted, max(0, ask.limit - used))
        self.used[key] = used + granted
        return granted

    def fill(self, holder: str, kind: str, used: int) -> None:
        self.used[(holder, kind)] = used
