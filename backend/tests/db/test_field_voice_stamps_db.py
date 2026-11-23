from datetime import UTC, datetime

import pytest

from app.models import FieldVoiceStream
from app.services.field_voices_feed import FieldVoicesPage, parse_page
from tests.db.field_voices_rows import KeptStore, ledger_for, rolled_back, synced
from tests.field_voices.fixtures import FR

pytestmark = pytest.mark.db

TRANSCRIPTS_LAST = (datetime(2026, 11, 17, 12, 0, 0, 3, tzinfo=UTC), "fr-media-2")
TRANSCRIPTS_GONE_LAST = (datetime(2026, 11, 17, 12, 0, 0, 2, tzinfo=UTC), "fr-media-0")
IMAGES_LAST = (datetime(2026, 11, 17, 12, 0, 1, 1, tzinfo=UTC), "fr-img-1")


def empty_page_of_gone_view(cursor: str) -> FieldVoicesPage:
    payload = {
        "schemaVersion": 2,
        "portal": FR,
        "generatedAt": "2026-11-18T09:00:01Z",
        "stream": "transcripts",
        "view": "gone",
        "cursor": cursor,
        "nextCursor": cursor,
        "hasMore": False,
        "changes": [],
    }
    return parse_page(payload, portal=FR, asked=("transcripts", "gone", cursor))


async def test_the_ledger_keeps_each_view_s_last_change_beside_its_cursor_and_clears_it_with_the_cursor() -> (
    None
):
    async with rolled_back() as session:
        store = KeptStore()
        assert (await synced(session, store))["ok"]
        ledger = ledger_for(session, store)
        transcripts = await ledger.cursors(FR, "transcripts")
        assert (transcripts.cursor, transcripts.last) == ("fr-t-3", TRANSCRIPTS_LAST)
        assert (transcripts.gone_cursor, transcripts.gone_last) == ("fr-g-1", TRANSCRIPTS_GONE_LAST)
        images = await ledger.cursors(FR, "images")
        assert (images.cursor, images.last, images.gone_last) == ("fr-i-1", IMAGES_LAST, None)
        await ledger.apply_page(empty_page_of_gone_view("fr-g-1"), {})
        kept = await ledger.cursors(FR, "transcripts")
        assert (kept.gone_cursor, kept.gone_last) == ("fr-g-1", TRANSCRIPTS_GONE_LAST)
        await ledger.restart(FR, "transcripts")
        row = await session.get(FieldVoiceStream, (FR, "TRANSCRIPTS"), populate_existing=True)
        assert row is not None
        assert (row.cursor, row.lastAt, row.lastId) == (None, None, None)
        assert (row.goneCursor, row.goneLastAt, row.goneLastId) == ("fr-g-1", *TRANSCRIPTS_GONE_LAST)
