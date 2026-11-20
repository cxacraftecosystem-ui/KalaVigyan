from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

__all__ = [
    "AVIF",
    "AVIF_BRANDS",
    "HEIF_BRANDS",
    "MetadataUnplaced",
    "avif_without_metadata",
    "file_brands",
]

AVIF = "image/avif"
FTYP = b"ftyp"
META = b"meta"
IINF = b"iinf"
ILOC = b"iloc"
INFE = b"infe"
IDAT = b"idat"
UUID = b"uuid"
FREE = b"free"
AVIF_BRANDS = frozenset({b"avif", b"avis"})
HEIF_BRANDS = frozenset(
    {b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"hevm", b"hevs", b"mif1", b"msf1"}
)
EXIF = b"Exif"
METADATA_ITEM_TYPES = frozenset({EXIF, b"mime", b"uri "})
EMPTY_EXIF = bytes(4) + b"MM\x00\x2a" + (8).to_bytes(4) + bytes(2) + bytes(4)
FULL_BOX_HEADER = 4
FILE_OFFSETS = 0
IDAT_OFFSETS = 1


class MetadataUnplaced(Exception):
    pass


@dataclass(frozen=True)
class Box:
    kind: bytes
    start: int
    payload: int
    end: int


@dataclass
class Reader:
    data: bytes
    position: int
    end: int

    def take(self, size: int) -> int:
        if size == 0:
            return 0
        if self.position + size > self.end:
            raise MetadataUnplaced("a box is cut short")
        value = int.from_bytes(self.data[self.position : self.position + size])
        self.position += size
        return value


def file_brands(data: bytes) -> frozenset[bytes]:
    if len(data) < 16 or data[4:8] != FTYP:
        return frozenset()
    size = int.from_bytes(data[:4])
    end = min(size, len(data)) if size >= 16 else 16
    listed = [data[8:12], *(data[at : at + 4] for at in range(16, end - 3, 4))]
    return frozenset(listed)


def avif_without_metadata(data: bytes) -> bytes:
    cleaned = bytearray(data)
    for box in _boxes(data, 0, len(data)):
        if box.kind == UUID:
            cleaned[box.start + 4 : box.start + 8] = FREE
            cleaned[box.payload : box.end] = bytes(box.end - box.payload)
        elif box.kind == META:
            _empty_items(cleaned, _metadata_extents(data, box))
    return bytes(cleaned)


def _empty_items(cleaned: bytearray, extents: list[tuple[int, int, bytes]]) -> None:
    emptied: set[bytes] = set()
    for start, end, kind in extents:
        cleaned[start:end] = bytes(end - start)
        if kind == EXIF and kind not in emptied and end - start >= len(EMPTY_EXIF):
            cleaned[start : start + len(EMPTY_EXIF)] = EMPTY_EXIF
            emptied.add(kind)


def _boxes(data: bytes, start: int, end: int) -> Iterator[Box]:
    position = start
    while position + 8 <= end:
        size = int.from_bytes(data[position : position + 4])
        header = 8
        if size == 1:
            if position + 16 > end:
                raise MetadataUnplaced("a large box is cut short")
            size, header = int.from_bytes(data[position + 8 : position + 16]), 16
        elif size == 0:
            size = end - position
        if size < header or position + size > end:
            raise MetadataUnplaced("a box runs past its parent")
        yield Box(data[position + 4 : position + 8], position, position + header, position + size)
        position += size


def _metadata_extents(data: bytes, meta: Box) -> list[tuple[int, int, bytes]]:
    children = {box.kind: box for box in _boxes(data, meta.payload + FULL_BOX_HEADER, meta.end)}
    if IINF not in children:
        return []
    wanted = _metadata_items(data, children[IINF])
    if not wanted:
        return []
    if ILOC not in children:
        raise MetadataUnplaced("metadata items have no locations")
    idat = children.get(IDAT)
    extents = []
    for item, method, offset, length in _locations(data, children[ILOC]):
        kind = wanted.get(item)
        if kind is None:
            continue
        if method == FILE_OFFSETS:
            extents.append((*_bounded(offset, length, len(data)), kind))
        elif method == IDAT_OFFSETS and idat is not None:
            extents.append((*_bounded(idat.payload + offset, length, idat.end), kind))
        else:
            raise MetadataUnplaced("a metadata item is built from other items")
    return extents


def _bounded(start: int, length: int, limit: int) -> tuple[int, int]:
    end = limit if length == 0 else start + length
    if start < 0 or end > limit or start > end:
        raise MetadataUnplaced("a metadata extent lies outside the file")
    return start, end


def _metadata_items(data: bytes, iinf: Box) -> dict[int, bytes]:
    version = data[iinf.payload]
    start = iinf.payload + FULL_BOX_HEADER + (2 if version == 0 else 4)
    found: dict[int, bytes] = {}
    for entry in _boxes(data, start, iinf.end):
        if entry.kind != INFE:
            continue
        reader = Reader(data, entry.payload, entry.end)
        entry_version = reader.take(1)
        reader.take(3)
        if entry_version < 2:
            continue
        item = reader.take(2 if entry_version == 2 else 4)
        reader.take(2)
        kind = data[reader.position : reader.position + 4]
        if kind in METADATA_ITEM_TYPES:
            found[item] = kind
    return found


def _locations(data: bytes, iloc: Box) -> Iterator[tuple[int, int, int, int]]:
    reader = Reader(data, iloc.payload, iloc.end)
    version = reader.take(1)
    reader.take(3)
    sizes = reader.take(1)
    offset_size, length_size = sizes >> 4, sizes & 0x0F
    bases = reader.take(1)
    base_size, index_size = bases >> 4, (bases & 0x0F) if version in (1, 2) else 0
    for _ in range(reader.take(2 if version < 2 else 4)):
        item = reader.take(2 if version < 2 else 4)
        method = reader.take(2) & 0x0F if version in (1, 2) else FILE_OFFSETS
        reader.take(2)
        base = reader.take(base_size)
        for _ in range(reader.take(2)):
            reader.take(index_size)
            offset = reader.take(offset_size)
            yield item, method, base + offset, reader.take(length_size)
