from __future__ import annotations

import asyncio

from app.research.embedding import TextEmbedder, checked_vectors

from .stamps import StampRead

__all__ = ["AnswerEmbeddings"]

Key = tuple[str | None, str]
Vector = list[float]


class AnswerEmbeddings:
    def __init__(self, embed: TextEmbedder, *, stamp: StampRead) -> None:
        self._embed = embed
        self._stamp = stamp
        self._made: dict[Key, asyncio.Future[Vector]] = {}

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        stamp = await self._stamp()
        keys = [(stamp, text) for text in texts]
        loop = asyncio.get_running_loop()
        owned = {key: loop.create_future() for key in dict.fromkeys(keys) if key not in self._made}
        self._made.update(owned)
        waiting = [self._made[key] for key in keys]
        if owned:
            await self._fill(owned)
        return [list(await made) for made in waiting]

    async def _fill(self, owned: dict[Key, asyncio.Future[Vector]]) -> None:
        texts = [text for _, text in owned]
        try:
            vectors = checked_vectors(await self._embed(texts), expected=len(texts))
        except BaseException as failure:
            self._fail(owned, failure)
            raise
        for made, vector in zip(owned.values(), vectors, strict=True):
            made.set_result(vector)

    def _fail(self, owned: dict[Key, asyncio.Future[Vector]], failure: BaseException) -> None:
        for key, made in owned.items():
            del self._made[key]
            if isinstance(failure, Exception):
                made.set_exception(failure)
                made.exception()
            else:
                made.cancel()
