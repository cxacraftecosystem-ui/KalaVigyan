from datetime import UTC, datetime
from pathlib import Path

from app.research.fetcher import ContentType, FetchedPage, PageMetadata

__all__ = ["CREATED", "FIRST_PAGE", "PAPER_TITLE", "STUDY_URL", "fetched"]

STUDY_URL = "https://www.jeb.co.in/journal_issues/200701_jan07/paper_22.pdf"
FIRST_PAGE = (Path(__file__).parent / "fixtures" / "jeb_sanganer_first_page.txt").read_text(encoding="utf-8")
PAPER_TITLE = "Mutagenicity assessment of textile dyes from Sanganer (Rajasthan)"
CREATED = "2009-11-11"
FETCHED_AT = datetime(2026, 11, 22, 10, 0, tzinfo=UTC)


def fetched(
    metadata: PageMetadata, *, text: str = FIRST_PAGE, content_type: ContentType = "application/pdf"
) -> FetchedPage:
    return FetchedPage(
        url=STUDY_URL,
        final_url=STUDY_URL,
        status=200,
        content_type=content_type,
        bytes=len(text),
        sha256="0" * 64,
        fetched_at=FETCHED_AT,
        text=text,
        truncated=False,
        metadata=metadata,
    )
