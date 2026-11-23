from __future__ import annotations

import json

import httpx
import pytest
from app.research.fetcher import FetchRefused
from curation_support import SOURCES, FakeHttp, fetched, pdf_with_text

from curation.fetching import rendered
from curation.polite import FetchFailed, PoliteHttp
from curation.reading import TEXT_MAX_CHARS, ReadFailed, content_type_of, read_source, source_text
from curation.wayback import latest_snapshot, latest_snapshot_query, raw_snapshot_url

LIVE = "https://example.org/test/resist"
SNAPSHOT = "https://web.archive.org/web/20250101000000id_/https://example.org/test/resist"
ARTICLE_LINES = [
    "The resist paste of lime and gum is pressed onto the cloth with a carved block, and the printed areas "
    "stay pale when the cloth goes into the indigo vat.",
    "After the indigo bath the cloth is washed in running water, which removes the paste and shows the "
    "pattern in pale lines on a deep blue ground.",
    "Printers say the work is slowest in the monsoon, when the cloth takes many days to dry between the "
    "printing stages.",
]


def article() -> bytes:
    return (SOURCES / "resist-article.html").read_bytes()


def cdx(*captures: tuple[str, str]) -> bytes:
    return json.dumps([["timestamp", "original"], *[list(capture) for capture in captures]]).encode()


def test_html_keeps_the_main_text_and_drops_scripts_navigation_and_hidden_text() -> None:
    content_type, text, truncated = source_text(fetched(LIVE, article(), "text/html"))
    lines = text.split("\n")
    assert (content_type, truncated) == ("text/html", False)
    assert all(line in lines for line in ARTICLE_LINES)
    for unseen in ("script text", "Hidden text", "Shop", "Copyright notice"):
        assert unseen not in text


def test_plain_text_joins_hyphenated_line_breaks() -> None:
    body = (SOURCES / "printing-village.txt").read_bytes()
    _, text, _ = source_text(fetched(LIVE, body))
    assert text.split("\n")[2] == (
        "The printed cloth is dried in the open sun on the sand beside the workshops, "
        "where the light is strong for most of the year."
    )


def test_pdf_text_is_read_through_pypdf() -> None:
    body = pdf_with_text("Ajrakh is printed on both sides of the cloth.")
    assert source_text(fetched(LIVE, body, "application/pdf")) == (
        "application/pdf",
        "Ajrakh is printed on both sides of the cloth.",
        False,
    )


def test_content_types_are_sniffed_when_the_server_mislabels_them() -> None:
    assert content_type_of(fetched(LIVE, b"%PDF-1.7 rest", "application/octet-stream")) == "application/pdf"
    assert content_type_of(fetched(LIVE, b"  <html><p>x</p></html>", "")) == "text/html"
    assert content_type_of(fetched(LIVE, b"plain words", "application/xhtml+xml")) == "text/html"
    with pytest.raises(FetchRefused):
        content_type_of(fetched(LIVE, b"\x89PNG", "image/png"))


def test_a_refused_live_page_is_read_from_the_latest_snapshot() -> None:
    http = FakeHttp(
        {
            LIVE: FetchFailed(LIVE, "HTTP 403"),
            latest_snapshot_query(LIVE): fetched(
                "cdx", cdx(("20240101000000", LIVE), ("20250101000000", LIVE))
            ),
            SNAPSHOT: fetched(SNAPSHOT, article(), "text/html"),
        }
    )
    reading = read_source(http, LIVE)
    assert (reading.route, reading.read_url, reading.url) == ("ARCHIVE", SNAPSHOT, LIVE)
    assert http.asked == [LIVE, latest_snapshot_query(LIVE), SNAPSHOT]
    assert rendered(reading)[7] == f"archivedUrl: {SNAPSHOT}"


def test_a_page_without_main_text_falls_back_to_the_given_snapshot() -> None:
    empty = b"<html><head><title>App</title></head><body><script>render();</script></body></html>"
    given = "https://web.archive.org/web/20230505000000/https://example.org/test/resist"
    raw = "https://web.archive.org/web/20230505000000id_/https://example.org/test/resist"
    http = FakeHttp({LIVE: fetched(LIVE, empty, "text/html"), raw: fetched(raw, article(), "text/html")})
    reading = read_source(http, LIVE, archived_url=given)
    assert (reading.route, reading.read_url) == ("ARCHIVE", raw)
    assert http.asked == [LIVE, raw]


def test_a_source_without_a_snapshot_reports_both_failures() -> None:
    http = FakeHttp({LIVE: FetchFailed(LIVE, "HTTP 403"), latest_snapshot_query(LIVE): fetched("cdx", b"[]")})
    with pytest.raises(ReadFailed) as failure:
        read_source(http, LIVE)
    assert failure.value.reasons == ["live page: HTTP 403", "archive: the Wayback Machine has no snapshot"]


def test_a_snapshot_url_is_read_directly_in_its_raw_form() -> None:
    http = FakeHttp({SNAPSHOT: fetched(SNAPSHOT, article(), "text/html")})
    reading = read_source(http, "http://web.archive.org/web/20250101000000/https://example.org/test/resist")
    assert (reading.route, reading.read_url) == ("ARCHIVE", SNAPSHOT)


def test_fetch_output_numbers_every_line() -> None:
    http = FakeHttp({LIVE: fetched(LIVE, (SOURCES / "printing-village.txt").read_bytes())})
    lines = rendered(read_source(http, LIVE))
    assert lines[0] == f"url: {LIVE}"
    assert lines[1] == f"read: LIVE {LIVE}"
    assert lines[6] == "lines: 3"
    assert lines[7] == "-" * 40
    assert lines[8:] == [
        "1  Recorded test page on a printing village",
        "2  In the village, about 40 families of Khatri printers now work on ajrakh cloth for local and urban "
        "buyers.",
        "3  The printed cloth is dried in the open sun on the sand beside the workshops, where the light is "
        "strong for most of the year.",
    ]


def test_the_latest_snapshot_is_the_last_capture() -> None:
    assert latest_snapshot(cdx(("20200101000000", LIVE), ("20250101000000", LIVE)).decode()) == SNAPSHOT
    assert latest_snapshot("[]") is None
    assert latest_snapshot("") is None
    assert "limit=-1" in latest_snapshot_query(LIVE)
    assert "filter=statuscode%3A200" in latest_snapshot_query(LIVE)
    assert raw_snapshot_url(
        "https://web.archive.org/web/20250101000000if_/https://example.org/test/resist"
    ) == (SNAPSHOT)
    assert raw_snapshot_url(LIVE) == LIVE


def mock_http(handler: httpx.MockTransport, *, max_bytes: int = 1000, **options: object) -> PoliteHttp:
    return PoliteHttp(
        client=httpx.Client(transport=handler, follow_redirects=True), max_bytes=max_bytes, **options
    )


def test_polite_http_reports_failures_and_caps_the_body() -> None:
    def answer(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/missing":
            return httpx.Response(404)
        if request.url.path == "/declared":
            return httpx.Response(200, headers={"content-length": "5000"}, content=b"x" * 5000)
        if request.url.path == "/streamed":
            return httpx.Response(200, content=iter([b"x" * 600, b"x" * 600]))
        if request.url.path == "/moved":
            return httpx.Response(301, headers={"location": "https://example.org/final"})
        return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, content=b"<p>ok</p>")

    with mock_http(httpx.MockTransport(answer), delay_seconds=0) as http:
        with pytest.raises(FetchFailed, match="HTTP 404"):
            http.get("https://example.org/missing")
        with pytest.raises(FetchFailed, match="declares 5000 bytes"):
            http.get("https://example.org/declared")
        with pytest.raises(FetchFailed, match="passed the 1000 byte cap"):
            http.get("https://example.org/streamed")
        page = http.get("https://example.org/moved")
    assert (page.final_url, page.media_type, page.charset, page.body) == (
        "https://example.org/final",
        "text/html",
        "utf-8",
        b"<p>ok</p>",
    )


def test_polite_http_waits_between_requests_to_one_host() -> None:
    ticks = iter([0.0, 0.5, 2.0, 2.1, 4.0, 4.0])
    slept: list[float] = []
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"ok"))
    with mock_http(transport, delay_seconds=1.5, clock=lambda: next(ticks), sleep=slept.append) as http:
        http.get("https://example.org/a")
        http.get("https://example.org/b")
        http.get("https://other.example.org/c")
        http.get("https://example.org/d")
    assert slept == [1.0]


def test_a_long_plain_text_source_is_read_past_the_live_fetcher_s_cap() -> None:
    body = ("Indigo is reduced in the vat. " * 10_000).encode("utf-8")
    _, text, truncated = source_text(fetched(LIVE, body))
    assert len(text) > 290_000 and not truncated
    assert TEXT_MAX_CHARS > len(text) > 200_000
