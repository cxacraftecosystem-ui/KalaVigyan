from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from contextvars import ContextVar
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "SHORT_REQUEST_CONNECTIONS",
    "ResearchGate",
    "ResearchSession",
    "gated_session_class",
    "research_slots",
]

SHORT_REQUEST_CONNECTIONS = 2

_holding: ContextVar[bool] = ContextVar("research_gate_holding", default=False)


def research_slots(pool_size: int, max_overflow: int) -> int:
    return max(1, pool_size + max_overflow - SHORT_REQUEST_CONNECTIONS)


class ResearchGate:
    def __init__(self, slots: int) -> None:
        if slots < 1:
            raise ValueError(f"a research gate holds at least one slot, not {slots}")
        self.slots = slots
        self._semaphore = asyncio.Semaphore(slots)

    @asynccontextmanager
    async def held(self) -> AsyncIterator[None]:
        if _holding.get():
            yield
            return
        async with self._semaphore:
            token = _holding.set(True)
            try:
                yield
            finally:
                _holding.reset(token)


class ResearchSession(AsyncSession):
    gate: ResearchGate | None = None
    _slot: AbstractAsyncContextManager[None] | None = None

    async def __aenter__(self) -> Self:
        if self.gate is None:
            raise RuntimeError("a research session is opened through research_sessionmaker()")
        self._slot = self.gate.held()
        await self._slot.__aenter__()
        try:
            return await super().__aenter__()
        except BaseException:
            await self._slot.__aexit__(None, None, None)
            raise

    async def __aexit__(
        self, type_: type[BaseException] | None, value: BaseException | None, traceback: TracebackType | None
    ) -> None:
        try:
            await super().__aexit__(type_, value, traceback)
        finally:
            if self._slot is not None:
                await self._slot.__aexit__(type_, value, traceback)


def gated_session_class(gate: ResearchGate) -> type[ResearchSession]:
    class GatedResearchSession(ResearchSession):
        pass

    GatedResearchSession.gate = gate
    return GatedResearchSession
