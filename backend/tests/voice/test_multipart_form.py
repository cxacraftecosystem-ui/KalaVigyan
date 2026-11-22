from typing import Any

import httpx
import pytest
from starlette.requests import Request

from app.api.multipart_form import BodyTooLarge, read_form
from app.core.errors import InvalidInput

AUDIO = b"\x1aE\xdf\xa3\r\n\r\n--not-the-boundary\r\n\x00\xff" * 50
LIMIT = 64 * 1024
CHUNK = 97


def sent(content_type: str, body: bytes) -> Request:
    chunks = [body[at : at + CHUNK] for at in range(0, len(body), CHUNK)] or [b""]
    messages = [
        {"type": "http.request", "body": chunk, "more_body": at < len(chunks) - 1}
        for at, chunk in enumerate(chunks)
    ]

    async def receive() -> dict[str, Any]:
        return messages.pop(0)

    scope = {
        "type": "http",
        "method": "POST",
        "path": "/upload",
        "headers": [(b"content-type", content_type.encode())],
    }
    return Request(scope, receive)


def encoded(files: Any, data: dict[str, str] | None = None) -> Request:
    request = httpx.Request("POST", "https://api.test/upload", files=files, data=data)
    return sent(request.headers["content-type"], request.read())


async def test_the_recording_comes_back_byte_for_byte() -> None:
    form = await read_form(
        encoded({"audio": ("KalaVigyan_Voice-Session.webm", AUDIO, "audio/webm")}), LIMIT, files=["audio"]
    )
    assert (form.file("audio").content, form.file("audio").content_type) == (AUDIO, "audio/webm")


async def test_a_codecs_parameter_is_read_as_the_bare_type() -> None:
    form = await read_form(
        encoded({"audio": ("a.webm", b"abc", "audio/webm;codecs=opus")}), LIMIT, files=["audio"]
    )
    assert form.file("audio").content_type == "audio/webm"


async def test_a_part_sent_as_a_field_is_read_as_its_bytes_and_a_text_field_as_its_text() -> None:
    files = {
        "declaration": (None, '{"caption":"Alum"}', "application/json"),
        "audio": ("a.webm", b"abc", "audio/webm"),
    }
    form = await read_form(
        encoded(files, {"continued": "true"}), LIMIT, files=["declaration", "audio"], texts=["continued"]
    )
    assert (form.file("declaration").content, form.text("continued")) == (b'{"caption":"Alum"}', "true")
    alone = await read_form(
        encoded({"audio": ("a.webm", b"abc", "audio/webm")}), LIMIT, files=["audio"], texts=["continued"]
    )
    assert alone.text("continued") is None


async def test_a_missing_or_doubled_part_is_refused() -> None:
    with pytest.raises(InvalidInput, match="0 'audio' parts"):
        await read_form(encoded({"file": ("a.webm", b"abc", "audio/webm")}), LIMIT, files=["audio"])
    doubled = [("audio", ("a", b"1", "audio/webm")), ("audio", ("b", b"2", "audio/webm"))]
    with pytest.raises(InvalidInput, match="Too many files"):
        await read_form(encoded(doubled), LIMIT, files=["audio"])


async def test_a_body_that_is_not_form_data_or_is_cut_short_is_refused() -> None:
    with pytest.raises(InvalidInput):
        await read_form(sent("audio/webm", AUDIO), LIMIT, files=["audio"])
    whole = httpx.Request(
        "POST", "https://api.test/upload", files={"audio": ("a.webm", b"abc", "audio/webm")}
    )
    with pytest.raises(InvalidInput):
        await read_form(sent(whole.headers["content-type"], whole.read()[:-10]), LIMIT, files=["audio"])


async def test_a_body_over_its_limit_stops_being_read() -> None:
    with pytest.raises(BodyTooLarge):
        await read_form(encoded({"audio": ("a.webm", AUDIO, "audio/webm")}), len(AUDIO) // 2, files=["audio"])
