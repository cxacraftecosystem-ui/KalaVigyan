from __future__ import annotations

import asyncio
import logging
import multiprocessing
from collections.abc import Callable
from dataclasses import dataclass, field
from multiprocessing.connection import Connection
from multiprocessing.process import BaseProcess
from typing import Protocol

from app.research.fetcher import FetchRefused

from .extract import Extracted, extract

__all__ = [
    "PARSES_PER_WORKER",
    "PARSE_WORKERS",
    "DocumentParser",
    "ParseFunction",
    "ParseJob",
    "ParseOutcome",
    "ParserPool",
    "extract_document",
    "parse_outcome",
    "serve_parses",
]

PARSE_WORKERS = 2
PARSES_PER_WORKER = 200
STOPPED = "the parser stopped before it answered"
SPAWN = multiprocessing.get_context("spawn")


@dataclass(frozen=True)
class ParseJob:
    url: str
    content_type: str
    body: bytes
    charset: str | None = None


@dataclass(frozen=True)
class ParseOutcome:
    extracted: Extracted | None = None
    reason: str = "PARSE_FAILED"
    detail: str = ""

    def result(self, url: str) -> Extracted:
        if self.extracted is None:
            raise FetchRefused(url, self.reason, self.detail)
        return self.extracted


ParseFunction = Callable[[ParseJob], Extracted]


class DocumentParser(Protocol):
    async def parse(self, job: ParseJob) -> Extracted: ...


def extract_document(job: ParseJob) -> Extracted:
    return extract(job.url, job.content_type, job.body, job.charset)


def parse_outcome(parse: ParseFunction, job: ParseJob) -> ParseOutcome:
    try:
        return ParseOutcome(extracted=parse(job))
    except FetchRefused as refused:
        return ParseOutcome(reason=refused.reason, detail=refused.detail)
    except Exception as error:
        return ParseOutcome(detail=f"the document could not be read ({type(error).__name__})")


def serve_parses(connection: Connection, parse: ParseFunction) -> None:
    logging.getLogger("pypdf").setLevel(logging.ERROR)
    while True:
        try:
            job = connection.recv()
        except EOFError:
            return
        connection.send(parse_outcome(parse, job))


@dataclass
class ParserPool:
    extractor: ParseFunction = extract_document
    size: int = PARSE_WORKERS
    _idle: list[_Worker] = field(default_factory=list)
    _slots: asyncio.Semaphore = field(init=False)

    def __post_init__(self) -> None:
        self._slots = asyncio.Semaphore(self.size)

    async def parse(self, job: ParseJob) -> Extracted:
        async with self._slots:
            worker = (
                self._idle.pop() if self._idle else await asyncio.to_thread(_Worker.started, self.extractor)
            )
            outcome = await self._answer(worker, job)
        return outcome.result(job.url)

    async def aclose(self) -> None:
        idle, self._idle = self._idle, []
        for worker in idle:
            worker.stop()

    async def _answer(self, worker: _Worker, job: ParseJob) -> ParseOutcome:
        kept = False
        try:
            outcome = await asyncio.to_thread(worker.exchange, job)
            kept = worker.reusable()
        finally:
            if kept:
                self._idle.append(worker)
            else:
                worker.stop()
        return outcome


@dataclass
class _Worker:
    process: BaseProcess
    connection: Connection
    parses: int = 0
    broken: bool = False

    @classmethod
    def started(cls, extractor: ParseFunction) -> _Worker:
        ours, theirs = SPAWN.Pipe()
        process = SPAWN.Process(target=serve_parses, args=(theirs, extractor), name="kv-parser", daemon=True)
        process.start()
        theirs.close()
        return cls(process, ours)

    def exchange(self, job: ParseJob) -> ParseOutcome:
        self.parses += 1
        try:
            self.connection.send(job)
            outcome: ParseOutcome = self.connection.recv()
        except EOFError, OSError:
            self.broken = True
            return ParseOutcome(detail=STOPPED)
        return outcome

    def reusable(self) -> bool:
        return not self.broken and self.parses < PARSES_PER_WORKER and self.process.is_alive()

    def stop(self) -> None:
        self.process.kill()
