from __future__ import annotations

from collections.abc import AsyncGenerator, AsyncIterator, Collection, Mapping
from dataclasses import dataclass, field

from fastapi import Request
from starlette.datastructures import FormData
from starlette.formparsers import MultiPartException, MultiPartParser

from app.core.errors import InvalidInput

__all__ = ["TEXT_FIELD_BYTES_MAX", "BodyTooLarge", "FormFile", "UploadedForm", "limited_body", "read_form"]

TEXT_FIELD_BYTES_MAX = 64 * 1024


class BodyTooLarge(InvalidInput):
    pass


@dataclass(frozen=True)
class FormFile:
    content_type: str
    content: bytes


@dataclass(frozen=True)
class UploadedForm:
    files: Mapping[str, FormFile]
    texts: Mapping[str, str] = field(default_factory=dict)

    def file(self, name: str) -> FormFile:
        return self.files[name]

    def text(self, name: str) -> str | None:
        return self.texts.get(name)


async def limited_body(request: Request, limit: int) -> bytes:
    collected = bytearray()
    async for chunk in _limited(request.stream(), limit):
        collected += chunk
    return bytes(collected)


async def read_form(
    request: Request, limit: int, *, files: Collection[str], texts: Collection[str] = ()
) -> UploadedForm:
    parser = MultiPartParser(
        request.headers,
        _limited(request.stream(), limit),
        max_files=len(files),
        max_fields=len(files) + len(texts),
        max_part_size=TEXT_FIELD_BYTES_MAX,
    )
    try:
        form = await parser.parse()
    except MultiPartException as malformed:
        raise InvalidInput(f"The upload's form data is refused: {malformed.message}") from malformed
    try:
        read = {name: await _one_part(form, name) for name in files}
        return UploadedForm(files=read, texts={name: text for name in texts if (text := _text(form, name))})
    finally:
        await form.close()


async def _limited(chunks: AsyncIterator[bytes], limit: int) -> AsyncGenerator[bytes]:
    seen = 0
    async for chunk in chunks:
        seen += len(chunk)
        if seen > limit:
            raise BodyTooLarge(f"The body is over {limit} bytes")
        yield chunk


async def _one_part(form: FormData, name: str) -> FormFile:
    found = form.getlist(name)
    if len(found) != 1:
        raise InvalidInput(f"The upload carries {len(found)} {name!r} parts, not one")
    part = found[0]
    if isinstance(part, str):
        return FormFile(content_type="", content=part.encode("utf-8"))
    bare = (part.content_type or "").partition(";")[0].strip().lower()
    return FormFile(content_type=bare, content=await part.read())


def _text(form: FormData, name: str) -> str | None:
    found = form.getlist(name)
    if not found:
        return None
    if len(found) != 1 or not isinstance(found[0], str):
        raise InvalidInput(f"The upload carries {len(found)} {name!r} fields, not one")
    return found[0]
