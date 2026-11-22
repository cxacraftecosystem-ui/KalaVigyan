import asyncio
import subprocess
import sys
import threading
from collections.abc import Sequence
from pathlib import Path

from app.core.errors import ExternalFailure
from app.research.citation_export import CslItem
from app.services.apa_references import apa_references
from app.services.export_files import ExportTools, explainer_pdf_link, lesson_file_link
from app.services.export_store import EXPORT_BUILDS_AT_ONCE

from .lesson_fixtures import BUILT_AT, FakeBucket, first_version, golden_pack

OWNER = first_version().explainer.answer_id
BACKEND = Path(__file__).resolve().parents[2]
EXPORT_LIBRARIES = ("pptx", "fpdf", "uharfbuzz", "citeproc", "PIL", "fontTools")


class NoPictures:
    async def picture(self, url: str) -> bytes:
        raise ExternalFailure(f"{url} is not read in this test")


class ThreadedApa:
    def __init__(self) -> None:
        self.threads: list[int] = []

    def __call__(self, items: Sequence[CslItem]) -> list[str]:
        self.threads.append(threading.get_ident())
        return apa_references(items)


def tools_with(apa: ThreadedApa) -> ExportTools:
    return ExportTools(
        objects=FakeBucket(),
        pictures=NoPictures(),
        apa=apa,
        clock=lambda: BUILT_AT,
        builds=asyncio.Semaphore(EXPORT_BUILDS_AT_ONCE),
    )


async def test_a_lesson_file_writes_its_apa_references_off_the_event_loop() -> None:
    apa = ThreadedApa()
    pack = golden_pack()
    await lesson_file_link(tools_with(apa), OWNER, pack, {}, "html")
    assert apa.threads and threading.get_ident() not in apa.threads


async def test_the_report_pdf_writes_its_apa_references_off_the_event_loop() -> None:
    apa = ThreadedApa()
    link = await explainer_pdf_link(tools_with(apa), OWNER, first_version(), {})
    assert link.file_name.endswith(".pdf")
    assert apa.threads and threading.get_ident() not in apa.threads


def test_the_api_loads_no_export_library_until_a_file_is_made() -> None:
    probe = (
        "import sys, app.api.router; "
        f"print(','.join(name for name in {EXPORT_LIBRARIES!r} if name in sys.modules))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe], cwd=BACKEND, capture_output=True, text=True, check=True, timeout=120
    )
    assert loaded.stdout.strip() == ""


async def test_a_lesson_file_made_while_its_picture_was_unread_is_made_again_next_time() -> None:
    apa = ThreadedApa()
    tools = tools_with(apa)
    first = await lesson_file_link(tools, OWNER, golden_pack(), {}, "html")
    again = await lesson_file_link(tools, OWNER, golden_pack(), {}, "html")
    assert len(apa.threads) == 2 and first.url == again.url
