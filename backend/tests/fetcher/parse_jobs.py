from __future__ import annotations

import os
import time
from pathlib import Path

from app.fetcher.extract import Extracted
from app.fetcher.parsing import ParseJob
from app.research.fetcher import FetchRefused

PROCESS_ID = "process-id"
SLOW = "slow"
REFUSE = "refuse"
RAISE = "raise"
DIE = "die"
SLOW_SECONDS = 1.5
REFUSAL_DETAIL = "content past 60 bytes by page 2"


def scripted_parse(job: ParseJob) -> Extracted:
    if job.content_type == SLOW:
        time.sleep(SLOW_SECONDS)
        Path(job.body.decode()).write_text("finished", encoding="utf-8")
    if job.content_type == REFUSE:
        raise FetchRefused(job.url, "PDF_LIMIT", REFUSAL_DETAIL)
    if job.content_type == RAISE:
        raise ZeroDivisionError
    if job.content_type == DIE:
        os._exit(3)
    return Extracted(text=str(os.getpid()), truncated=False)
