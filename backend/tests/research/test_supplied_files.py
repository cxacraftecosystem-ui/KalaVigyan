import pytest
from fpdf import FPDF

from app.core.errors import InvalidInput
from app.services.supplied_sources_pdf import file_text

SENTENCE = "Alum is printed before the madder bath so the red fixes only there."


def pdf_of(text: str) -> bytes:
    document = FPDF(unit="mm", format="A4")
    document.add_page()
    document.set_font("helvetica", "", 11)
    document.multi_cell(180, 6, text)
    return bytes(document.output())


async def test_a_pdf_gives_its_text_layer() -> None:
    assert SENTENCE in " ".join((await file_text(pdf_of(SENTENCE), "pdf")).split())


async def test_a_file_that_is_not_a_pdf_is_refused() -> None:
    with pytest.raises(InvalidInput, match="not a PDF"):
        await file_text(b"<html>not a pdf</html>", "pdf")


async def test_a_text_file_is_read_as_utf8_and_refused_otherwise() -> None:
    assert await file_text("﻿नील की कुण्डी\n".encode(), "text") == "नील की कुण्डी"
    with pytest.raises(InvalidInput, match="not UTF-8"):
        await file_text(b"\xff\xfe\x00broken", "text")
