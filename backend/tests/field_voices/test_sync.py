import copy
from datetime import UTC, datetime
from typing import Any

import httpx

from app.services.field_voices_reader import field_voices_reader
from app.services.field_voices_sync import PortalReport, sync_portal
from tests.field_voices.fakes import FakeClock, FakeCopier, FakeLedger
from tests.field_voices.fixtures import (
    DR,
    FR,
    STATE,
    Answers,
    caught_up,
    edited,
    empty_page,
    enabled_settings,
    portal_transport,
    recorded,
    resigned,
)

LAST_OF_FIRST_RUN = (datetime(2026, 11, 17, 12, 0, 0, 3, tzinfo=UTC), "fr-media-2")


async def run(
    portal: str,
    answers: Answers,
    ledger: FakeLedger,
    *,
    copier: FakeCopier | None = None,
    clock: FakeClock | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> PortalReport:
    reader = field_voices_reader(enabled_settings(), portal, transport=transport or portal_transport(answers))
    return await sync_portal(reader, ledger, copier or FakeCopier(), clock=(clock or FakeClock()).clock())


def streams(report: PortalReport) -> dict[str, dict[str, Any]]:
    return {stream.stream: stream.as_dict() for stream in report.streams}


async def test_a_first_run_reads_both_views_of_both_streams() -> None:
    ledger, copier = FakeLedger(), FakeCopier()
    report = await run(FR, caught_up(FR), ledger, copier=copier)
    assert report.as_dict()["ok"]
    shown = streams(report)
    assert (shown["transcripts"]["liveApplied"], shown["transcripts"]["goneApplied"]) == (2, 2)
    assert shown["transcripts"]["reconciled"] is True
    assert (shown["images"]["imagesStored"], shown["images"]["reconciled"]) == (1, True)
    assert set(ledger.stream(FR, "transcripts").items) == {"fr-media-1", "fr-media-2"}
    assert ledger.stream(FR, "transcripts").withdrawn == ["fr-media-0", "fr-media-0"]
    assert copier.copied == ["fr-img-1"]
    assert ledger.relinked == [FR]


async def test_a_second_run_changes_nothing_and_copies_nothing() -> None:
    ledger, copier = FakeLedger(), FakeCopier()
    answers = caught_up(DR)
    await run(DR, answers, ledger, copier=copier)
    before = {key: dict(row.items) for key, row in ledger.streams.items()}
    again = streams(await run(DR, answers, ledger, copier=copier))
    assert {key: dict(row.items) for key, row in ledger.streams.items()} == before
    assert (again["transcripts"]["liveApplied"], again["images"]["imagesStored"]) == (0, 0)
    assert copier.copied == ["dr-img-1"]
    assert ledger.stream(DR, "transcripts").cursor == "dr-t-1"


async def test_a_tombstone_in_the_gone_view_withdraws_on_the_next_run() -> None:
    ledger = FakeLedger()
    answers = caught_up(FR)
    await run(FR, answers, ledger)
    withdrawn = {
        "state": "GONE",
        "id": "fr-media-2",
        "updatedAt": "2026-11-18T05:00:00.000001Z",
        "reason": "WITHDRAWN",
        "successorId": None,
    }
    page = empty_page(FR, "transcripts", "gone", "fr-g-1") | {"nextCursor": "fr-g-2", "changes": [withdrawn]}
    answers[(f"{STATE}/transcripts", "gone", "fr-g-1")] = page
    answers[(f"{STATE}/transcripts", "gone", "fr-g-2")] = empty_page(FR, "transcripts", "gone", "fr-g-2")
    answers[(STATE, None, None)]["streams"]["transcripts"]["latestCursor"] = "not-yet"
    await run(FR, answers, ledger)
    assert set(ledger.stream(FR, "transcripts").items) == {"fr-media-1"}
    assert ledger.stream(FR, "transcripts").gone_cursor == "fr-g-2"


async def test_a_disabled_stream_is_hidden_and_not_read() -> None:
    answers = edited(
        caught_up(FR), (STATE, None, None), lambda s: s["streams"]["images"].update(enabled=False)
    )
    ledger = FakeLedger()
    report = streams(await run(FR, answers, ledger))
    assert report["images"]["skipped"] == "disabled"
    assert ledger.stream(FR, "images").hidden
    assert not ledger.stream(FR, "images").items


async def test_a_portal_that_has_not_shipped_is_skipped_not_failed() -> None:
    report = await run(DR, {}, FakeLedger())
    assert (report.skipped, report.as_dict()["ok"]) == ("not_served", True)


async def test_a_refused_page_stops_only_its_stream() -> None:
    def tamper(page: dict[str, Any]) -> None:
        page["changes"][0]["transcript"]["segments"][1]["text"] = "edited after signing"

    answers = edited(caught_up(FR), (f"{STATE}/transcripts", "all", None), tamper)
    ledger = FakeLedger()
    report = await run(FR, answers, ledger)
    shown = streams(report)
    assert (shown["transcripts"]["ok"], shown["transcripts"]["refusedPages"]) == (False, 1)
    assert "revision" in shown["transcripts"]["error"]
    assert shown["images"]["ok"]
    assert not report.as_dict()["ok"]
    assert ledger.stream(FR, "transcripts").cursor is None


async def test_a_digest_mismatch_rereads_the_stream_and_withdraws_what_is_no_longer_listed() -> None:
    ledger = FakeLedger()
    answers = caught_up(FR)
    ledger.stream(FR, "transcripts").items["fr-media-stale"] = "0" * 32
    first = streams(await run(FR, answers, ledger))
    assert first["transcripts"]["reconciled"] is False
    assert ledger.stream(FR, "transcripts").cursor is None
    second = streams(await run(FR, answers, ledger))
    assert second["transcripts"]["withdrawnUnlisted"] == 1
    assert "fr-media-stale" not in ledger.stream(FR, "transcripts").items
    assert second["transcripts"]["reconciled"] is True


async def test_a_rate_limited_call_waits_the_portals_retry_after() -> None:
    answers = caught_up(FR)
    inner = portal_transport(answers)
    calls = {"count": 0}

    async def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        if calls["count"] == 1:
            return httpx.Response(429, headers={"Retry-After": "7"}, json={"detail": "Too many requests."})
        return await inner.handle_async_request(request)

    clock = FakeClock()
    report = await run(FR, answers, FakeLedger(), clock=clock, transport=httpx.MockTransport(handler))
    assert report.as_dict()["ok"]
    assert 7.0 in clock.pauses
    assert all(pause <= 60 for pause in clock.pauses)


async def test_expired_image_links_read_the_page_again() -> None:
    copier = FakeCopier(expired_first=1)
    report = streams(await run(FR, caught_up(FR), FakeLedger(), copier=copier))
    assert (report["images"]["ok"], report["images"]["imagesStored"]) == (True, 1)
    assert copier.copied == ["fr-img-1"]


async def test_a_changed_revision_is_applied_again() -> None:
    ledger = FakeLedger()
    answers = caught_up(DR)
    await run(DR, answers, ledger)

    def renamed(page: dict[str, Any]) -> None:
        page["changes"][0]["caption"] = "Second prototype, indigo lighter"
        resigned(page["changes"][0])

    page = edited(answers, (f"{STATE}/images", "all", None), renamed)[(f"{STATE}/images", "all", None)]
    moved = page | {"cursor": "dr-i-1", "nextCursor": "dr-i-2"}
    moved["changes"][0]["updatedAt"] = "2026-11-18T06:00:00.000001Z"
    answers[(f"{STATE}/images", "all", "dr-i-1")] = moved
    answers[(f"{STATE}/images", "all", "dr-i-2")] = empty_page(DR, "images", "all", "dr-i-2")
    report = streams(await run(DR, answers, ledger))
    assert report["images"]["liveApplied"] == 1
    assert ledger.stream(DR, "images").items["dr-img-1"] == moved["changes"][0]["revision"]


async def test_a_page_that_starts_before_the_page_it_follows_is_refused() -> None:
    def earlier(page: dict[str, Any]) -> None:
        page["changes"][0]["updatedAt"] = "2026-11-17T12:00:00.000001Z"

    answers = edited(caught_up(FR), (f"{STATE}/transcripts", "all", "fr-t-2"), earlier)
    ledger = FakeLedger()
    shown = streams(await run(FR, answers, ledger))
    assert (shown["transcripts"]["ok"], shown["transcripts"]["refusedPages"]) == (False, 1)
    assert "before the page it follows" in shown["transcripts"]["error"]
    assert "fr-media-2" not in ledger.stream(FR, "transcripts").items
    assert ledger.stream(FR, "transcripts").cursor == "fr-t-2"


def next_run_page(answers: Answers, updated_at: str, *, duration_ms: int) -> dict[str, Any]:
    change = copy.deepcopy(recorded("field-transcripts-all-1")["changes"][0])
    change["durationMs"] = duration_ms
    resigned(change)
    change["updatedAt"] = updated_at
    page = empty_page(FR, "transcripts", "all", "fr-t-3") | {"nextCursor": "fr-t-4", "changes": [change]}
    answers[(f"{STATE}/transcripts", "all", "fr-t-3")] = page
    answers[(f"{STATE}/transcripts", "all", "fr-t-4")] = empty_page(FR, "transcripts", "all", "fr-t-4")
    return change


async def test_a_run_keeps_the_last_change_it_read_of_each_view() -> None:
    ledger = FakeLedger()
    await run(FR, caught_up(FR), ledger)
    row = ledger.stream(FR, "transcripts")
    assert (row.cursor, row.last) == ("fr-t-3", LAST_OF_FIRST_RUN)
    assert row.gone_last == (datetime(2026, 11, 17, 12, 0, 0, 2, tzinfo=UTC), "fr-media-0")


async def test_a_run_s_first_page_starting_at_the_last_run_s_last_change_is_refused() -> None:
    ledger = FakeLedger()
    answers = caught_up(FR)
    await run(FR, answers, ledger)
    next_run_page(answers, "2026-11-17T12:00:00.000003Z", duration_ms=1833000)
    shown = streams(await run(FR, answers, ledger))
    assert (shown["transcripts"]["ok"], shown["transcripts"]["refusedPages"]) == (False, 1)
    assert "before the page it follows" in shown["transcripts"]["error"]
    row = ledger.stream(FR, "transcripts")
    assert (row.cursor, row.last) == ("fr-t-3", LAST_OF_FIRST_RUN)


async def test_a_run_s_first_page_after_the_last_run_s_last_change_is_applied() -> None:
    ledger = FakeLedger()
    answers = caught_up(FR)
    await run(FR, answers, ledger)
    change = next_run_page(answers, "2026-11-17T12:00:00.000004Z", duration_ms=1833000)
    shown = streams(await run(FR, answers, ledger))
    assert (shown["transcripts"]["ok"], shown["transcripts"]["liveApplied"]) == (True, 1)
    row = ledger.stream(FR, "transcripts")
    assert row.items["fr-media-1"] == change["revision"]
    assert (row.cursor, row.last) == (
        "fr-t-4",
        (datetime(2026, 11, 17, 12, 0, 0, 4, tzinfo=UTC), "fr-media-1"),
    )


async def test_a_reread_starts_again_from_no_stamp() -> None:
    ledger = FakeLedger()
    ledger.stream(FR, "transcripts").items["fr-media-stale"] = "0" * 32
    await run(FR, caught_up(FR), ledger)
    row = ledger.stream(FR, "transcripts")
    assert (row.cursor, row.last, row.rereading) == (None, None, True)
    assert row.gone_last is not None
