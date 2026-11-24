from __future__ import annotations

import zlib
from collections.abc import Iterable

__all__ = ["INFLATED_CODINGS", "Inflater", "content_codings"]

IDENTITY = "identity"
DEFLATE = "deflate"
GZIP_BITS = zlib.MAX_WBITS | 16
WINDOW_BITS = {"gzip": GZIP_BITS, "x-gzip": GZIP_BITS, DEFLATE: zlib.MAX_WBITS}
RAW_DEFLATE_BITS = -zlib.MAX_WBITS
INFLATED_CODINGS = frozenset(WINDOW_BITS)


def content_codings(values: Iterable[str]) -> tuple[str, ...]:
    codings = (value.strip().lower() for value in values)
    return tuple(coding for coding in codings if coding and coding != IDENTITY)


class Inflater:
    def __init__(self, coding: str, *, limit: int) -> None:
        if coding not in WINDOW_BITS:
            raise ValueError(f"{coding!r} is not one of {sorted(INFLATED_CODINGS)}")
        self._coding = coding
        self._left = limit + 1
        self._decompressor = zlib.decompressobj(WINDOW_BITS[coding])
        self._fresh = True

    def inflate(self, data: bytes) -> bytes:
        room = max(self._left, 1)
        try:
            out = self._decompressor.decompress(data, room)
        except zlib.error:
            if not (self._fresh and self._coding == DEFLATE):
                raise
            self._decompressor = zlib.decompressobj(RAW_DEFLATE_BITS)
            out = self._decompressor.decompress(data, room)
        self._fresh = self._fresh and not data
        self._left -= len(out)
        return out
