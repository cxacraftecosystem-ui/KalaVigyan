import pytest

from app.fetcher.extract import content_type_of, extract
from app.fetcher.pdf import pdf_text
from app.research.fetcher import FETCH_TEXT_MAX_CHARS, FetchRefused, PageMetadata

from .pdf_fixture import pdf_with_pages, pdf_with_resources
from .site import fixture

URL = "https://crafts.example.org/ajrakh/resist-printing"
PDF_URL = "https://crafts.example.org/notes.pdf"
ARTICLE_PARAGRAPHS = [
    "Ajrakh printers in Kutch soak cotton in a solution of camel dung, soda ash and castor oil before the first printing.",
    "The resist paste of lime and gum arabic keeps the dye away from the printed areas, and alum is printed where red is wanted.",
    "After printing, the cloth is boiled with alizarin, which forms a red lake only where the alum mordant was applied.",
    "Indigo vats are fermented separately with jaggery and lime for about ten days.",
]


def test_the_article_text_is_the_main_content_in_reading_order() -> None:
    extracted = extract(URL, "text/html", fixture("article.html"), None)
    positions = [extracted.text.index(paragraph) for paragraph in ARTICLE_PARAGRAPHS]
    assert positions == sorted(positions)
    assert "Home" not in extracted.text.split("\n")
    assert extracted.truncated is False


def test_the_article_metadata_comes_from_its_head_and_licence_link() -> None:
    extracted = extract(URL, "text/html", fixture("article.html"), None)
    assert extracted.metadata == PageMetadata(
        title="Ajrakh resist printing",
        authors=["Meera Shah"],
        published="2024-03-18",
        licence="CC BY 4.0",
        canonical_url="https://crafts.example.org/ajrakh/resist-printing",
        site_name="Craft Notes",
        language="en",
    )


def test_a_page_with_no_main_text_fails_to_parse() -> None:
    with pytest.raises(FetchRefused) as refused:
        extract(URL, "text/html", b"<html><body><script>alert(1)</script></body></html>", None)
    assert refused.value.reason == "PARSE_FAILED"


def test_plain_text_keeps_indic_joiners_and_drops_invisible_controls() -> None:
    body = "अज्\u200dरख\u202e ছাপা\u200b \U000e0049\U000e0047gone\x07".encode()
    text = extract(URL, "text/plain", body, "utf-8").text
    assert text == "अज्\u200dरख ছাপা gone"


def test_text_past_the_cap_is_cut_and_marked_truncated() -> None:
    extracted = extract(URL, "text/plain", b"a" * (FETCH_TEXT_MAX_CHARS + 1), None)
    assert (len(extracted.text), extracted.truncated) == (FETCH_TEXT_MAX_CHARS, True)


def test_an_unknown_charset_falls_back_to_utf8() -> None:
    assert extract(URL, "text/plain", "kalamkārī".encode(), "x-unknown").text == "kalamkārī"


@pytest.mark.parametrize(
    ("declared", "kept"),
    [
        ("text/html", "text/html"),
        ("application/xhtml+xml", "text/html"),
        ("application/pdf", "application/pdf"),
        ("text/plain", "text/plain"),
    ],
)
def test_accepted_content_types(declared: str, kept: str) -> None:
    assert content_type_of(URL, declared, b"<p>Alum</p>") == kept


@pytest.mark.parametrize(
    ("declared", "body", "kept"),
    [
        ("application/octet-stream", b"%PDF-1.7 rest", "application/pdf"),
        ("binary/octet-stream", b"%PDF-1.4 rest", "application/pdf"),
        ("text/html", b"%PDF-1.4 rest", "text/html"),
        ("text/plain", b"%PDF-1.4 rest", "text/plain"),
    ],
)
def test_only_an_octet_stream_is_read_as_a_pdf_by_its_signature(
    declared: str, body: bytes, kept: str
) -> None:
    assert content_type_of(URL, declared, body) == kept


@pytest.mark.parametrize(
    ("declared", "body"),
    [
        ("image/png", b"%PDF-1.4 rest"),
        ("application/octet-stream", b"PK zipped"),
        ("binary/octet-stream", b" %PDF-1.4 rest"),
        ("application/javascript", b"%PDF-1.4 rest"),
        ("", b"%PDF-1.4 rest"),
    ],
)
def test_other_content_types_are_refused(declared: str, body: bytes) -> None:
    with pytest.raises(FetchRefused) as refused:
        content_type_of(URL, declared, body)
    assert refused.value.reason == "CONTENT_TYPE"


def test_pdf_pages_are_joined_with_their_metadata() -> None:
    body = pdf_with_pages(
        ["Alum fixes the red dye.", "Indigo needs a reduced (leuco) vat."],
        title="Mordants and vats",
        author="R. Iyer",
        created="D:20190704120000Z",
    )
    text, truncated, metadata = pdf_text(PDF_URL, body)
    assert text == "Alum fixes the red dye.\n\nIndigo needs a reduced (leuco) vat."
    assert truncated is False
    assert metadata == PageMetadata(title="Mordants and vats", authors=["R. Iyer"], published="2019-07-04")


def test_pages_past_the_page_cap_are_left_out_and_marked() -> None:
    body = pdf_with_pages([f"Page {n} text." for n in range(1, 5)])
    text, truncated, _ = pdf_text(PDF_URL, body, max_pages=3)
    assert text == "Page 1 text.\n\nPage 2 text.\n\nPage 3 text."
    assert truncated is True


def test_content_past_the_decompressed_cap_is_refused() -> None:
    body = pdf_with_pages(["Alum fixes the red dye.", "Indigo needs a reduced vat."])
    with pytest.raises(FetchRefused) as refused:
        pdf_text(PDF_URL, body, max_decompressed=60)
    assert refused.value.reason == "PDF_LIMIT"


@pytest.mark.parametrize("body", [b"not a pdf at all", b"%PDF-1.4\n%%EOF\n"])
def test_a_broken_pdf_fails_to_parse(body: bytes) -> None:
    with pytest.raises(FetchRefused) as refused:
        pdf_text(PDF_URL, body)
    assert refused.value.reason == "PARSE_FAILED"


FORM_TEXT = "Indigo vats ferment for ten days. " * 40


def test_a_form_drawn_on_the_page_is_read_and_counted_toward_the_decompressed_cap() -> None:
    body = pdf_with_resources("Alum fixes the red dye.", form_text=FORM_TEXT)
    text, _, _ = pdf_text(PDF_URL, body, max_decompressed=5000)
    assert "Indigo vats ferment for ten days." in text
    with pytest.raises(FetchRefused) as refused:
        pdf_text(PDF_URL, body, max_decompressed=1000)
    assert (refused.value.reason, refused.value.detail) == ("PDF_LIMIT", "content past 1000 bytes by page 1")


def test_a_font_s_unicode_map_counts_toward_the_decompressed_cap() -> None:
    body = pdf_with_resources("Alum fixes the red dye.", to_unicode=b"% filler\n" * 250)
    with pytest.raises(FetchRefused) as refused:
        pdf_text(PDF_URL, body, max_decompressed=1000)
    assert refused.value.reason == "PDF_LIMIT"


def test_an_image_text_extraction_never_decodes_is_not_counted() -> None:
    body = pdf_with_resources("Alum fixes the red dye.", image=bytes(5000))
    text, truncated, _ = pdf_text(PDF_URL, body, max_decompressed=1000)
    assert (text.strip(), truncated) == ("Alum fixes the red dye.", False)


def test_text_is_cut_at_the_fetcher_cap_unless_the_caller_names_a_larger_one() -> None:
    body = b"a" * (FETCH_TEXT_MAX_CHARS + 1)
    cut = extract("https://example.org/long.txt", "text/plain", body, "utf-8")
    assert (len(cut.text), cut.truncated) == (FETCH_TEXT_MAX_CHARS, True)
    whole = extract(
        "https://example.org/long.txt", "text/plain", body, "utf-8", max_chars=FETCH_TEXT_MAX_CHARS + 1
    )
    assert (len(whole.text), whole.truncated) == (FETCH_TEXT_MAX_CHARS + 1, False)
