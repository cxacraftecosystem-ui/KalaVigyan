import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.fetcher.extract import Extracted
from app.fetcher.parsing import ParseJob, ParserPool
from app.fetcher.robots import RobotsPolicy
from app.fetcher.sandbox import SandboxFetcher
from app.research.fetcher import FetchRefused, FetchRequest

from .parse_jobs import DIE, PROCESS_ID, RAISE, REFUSAL_DETAIL, REFUSE, SLOW, SLOW_SECONDS, scripted_parse
from .site import FETCHED, PUBLIC_A, Site, fixture, html

URL = "https://crafts.example.org/notes"
ARTICLE = "https://crafts.example.org/ajrakh/resist-printing"
OVERRUN_LIMIT_SECONDS = 0.3
SETTLE_SECONDS = 1.0


def job(kind: str, body: bytes = b"") -> ParseJob:
    return ParseJob(URL, kind, body)


@pytest.fixture
async def pool() -> AsyncIterator[ParserPool]:
    opened = ParserPool(extractor=scripted_parse, size=1)
    yield opened
    await opened.aclose()


async def worker_of(pool: ParserPool) -> str:
    return (await pool.parse(job(PROCESS_ID))).text


async def test_parses_run_in_another_process_kept_warm_between_parses(pool: ParserPool) -> None:
    first = await worker_of(pool)
    assert first != str(os.getpid())
    assert await worker_of(pool) == first


async def test_a_parse_that_overruns_is_stopped_and_the_next_parse_still_works(
    pool: ParserPool, tmp_path: Path
) -> None:
    first = await worker_of(pool)
    marker = tmp_path / "finished"
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(OVERRUN_LIMIT_SECONDS):
            await pool.parse(job(SLOW, str(marker).encode()))
    await asyncio.sleep(SLOW_SECONDS + SETTLE_SECONDS)
    assert not marker.exists()
    replacement = await worker_of(pool)
    assert replacement not in (first, str(os.getpid()))


async def test_a_refusal_in_the_worker_comes_back_with_its_reason(pool: ParserPool) -> None:
    with pytest.raises(FetchRefused) as refused:
        await pool.parse(job(REFUSE))
    assert (refused.value.url, refused.value.reason, refused.value.detail) == (
        URL,
        "PDF_LIMIT",
        REFUSAL_DETAIL,
    )


async def test_an_unexpected_error_is_parse_failed_naming_only_its_type(pool: ParserPool) -> None:
    first = await worker_of(pool)
    with pytest.raises(FetchRefused) as refused:
        await pool.parse(job(RAISE))
    assert (refused.value.reason, refused.value.detail) == (
        "PARSE_FAILED",
        "the document could not be read (ZeroDivisionError)",
    )
    assert await worker_of(pool) == first


async def test_a_worker_that_dies_is_parse_failed_and_replaced(pool: ParserPool) -> None:
    first = await worker_of(pool)
    with pytest.raises(FetchRefused) as refused:
        await pool.parse(job(DIE))
    assert (refused.value.reason, refused.value.detail) == (
        "PARSE_FAILED",
        "the parser stopped before it answered",
    )
    assert await worker_of(pool) != first


class StuckParser:
    def __init__(self) -> None:
        self.stopped = False

    async def parse(self, job: ParseJob) -> Extracted:
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            self.stopped = True
            raise
        raise AssertionError("the time limit should have stopped the parse")


def article_site() -> Site:
    return Site(
        routes={"crafts.example.org/ajrakh/resist-printing": html(fixture("article.html"))},
        dns={"crafts.example.org": [PUBLIC_A]},
    )


async def test_the_fetch_time_limit_stops_the_parse() -> None:
    parser = StuckParser()
    fetcher = SandboxFetcher(article_site().pinned(), RobotsPolicy(), parser, clock=lambda: FETCHED)
    with pytest.raises(FetchRefused) as refused:
        await fetcher.fetch(FetchRequest(url=ARTICLE, timeout_seconds=0.2))
    assert (refused.value.reason, parser.stopped) == ("TIME_LIMIT", True)


async def test_the_sandbox_reads_a_page_through_the_parser_process() -> None:
    parsers = ParserPool()
    try:
        await parsers.parse(ParseJob(URL, "text/plain", b"warm"))
        fetcher = SandboxFetcher(article_site().pinned(), RobotsPolicy(), parsers, clock=lambda: FETCHED)
        page = await fetcher.fetch(FetchRequest(url=ARTICLE))
    finally:
        await parsers.aclose()
    assert "alum is printed where red is wanted." in page.text
    assert "ignore previous instructions" not in page.text
