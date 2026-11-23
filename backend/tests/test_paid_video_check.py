import base64
import json
from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from app.providers.gemini_media import GeminiMediaWire
from app.scripts.paid_check_ledger import CapLedger, Recorder
from app.scripts.paid_check_runs import STANDING_GROUPS, chosen_checks, groups_of
from app.scripts.paid_check_steps import CheckResult, PaidCheck
from app.scripts.paid_check_video import VIDEO_MODEL, VideoTimes, video_check, video_estimate
from app.scripts.paid_checks import run_checks

from .media.mp4_builder import movie

API = "https://generativelanguage.googleapis.com/v1beta"
REF = "v1_ChdvbW5pLWludGVyYWN0aW9uLTAwMDM"
OPEN = {"id": REF, "status": "in_progress", "model": VIDEO_MODEL, "steps": []}


def finished(clip: bytes) -> dict[str, object]:
    block = {"type": "video", "mime_type": "video/mp4", "data": base64.b64encode(clip).decode()}
    return {
        "id": REF,
        "status": "completed",
        "model": VIDEO_MODEL,
        "steps": [{"type": "model_output", "content": [block]}],
        "usage": {"total_input_tokens": 410, "total_output_tokens": 46336},
    }


class Interactions:
    def __init__(self, polls: list[dict[str, object]], *, deleted: int = 200) -> None:
        self.polls = polls
        self.deleted = deleted
        self.asked: list[tuple[str, str]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.asked.append((request.method, request.url.path))
        if request.method == "POST":
            return httpx.Response(200, json=OPEN)
        if request.method == "DELETE":
            return httpx.Response(self.deleted, json={})
        return httpx.Response(200, json=self.polls.pop(0))


class Clock:
    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


async def no_wait(seconds: float) -> None:
    return None


async def checked(interactions: Interactions, *, step: float = 1.0) -> tuple[CheckResult, Interactions]:
    recorder = Recorder()
    transport = httpx.MockTransport(interactions)
    times = VideoTimes(wait_seconds=10.0, poll_seconds=5.0, sleep=no_wait, clock=Clock(step))
    async with httpx.AsyncClient(transport=transport, event_hooks={"response": [recorder]}) as client:
        wire = GeminiMediaWire(api_key="test-only-gemini-key", client=client)
        return await video_check(wire, recorder, times), interactions


def test_the_clip_is_estimated_at_seven_cents_a_second_for_eight_seconds() -> None:
    assert video_estimate() == Decimal("0.56")


def test_a_run_makes_only_the_named_checks_and_the_clip_only_when_named() -> None:
    assert "video" not in STANDING_GROUPS and groups_of("video") == ("video",)
    assert groups_of("narration, video,video") == ("narration", "video")
    for refused in ("films", " , "):
        with pytest.raises(ValueError):
            groups_of(refused)

    async def made() -> CheckResult:
        return CheckResult({})

    checks = [
        PaidCheck(name, Decimal("0.01"), made) for name in ("narration_en", "narration_hi", "gemini_video")
    ]
    assert [check.name for check in chosen_checks(checks, ("video",))] == ["gemini_video"]
    assert [check.name for check in chosen_checks(checks, ("narration",))] == ["narration_en", "narration_hi"]
    with pytest.raises(ValueError, match="music_bed"):
        chosen_checks(checks, ("music",))


async def test_a_silent_eight_second_clip_keeps_every_shape_and_is_deleted() -> None:
    clip = movie(audio=False).data
    result, interactions = await checked(Interactions([OPEN, finished(clip)]))
    assert interactions.asked == [
        ("POST", "/v1beta/interactions"),
        ("GET", f"/v1beta/interactions/{REF}"),
        ("GET", f"/v1beta/interactions/{REF}"),
        ("DELETE", f"/v1beta/interactions/{REF}"),
    ]
    found = result.findings
    assert (found["polls"], found["durationSeconds"], found["width"], found["height"]) == (2, 8.0, 1280, 720)
    assert (found["silentAsAsked"], found["pipelineStores"], found["pipelineProblem"]) == (True, True, None)
    assert (found["deleteStatus"], found["videoTokens"], found["outputTokens"]) == (200, None, 46336)
    assert set(result.fixtures) == {
        "video_started_recorded.json",
        "video_polling_recorded.json",
        "video_completed_recorded.json",
        "video_deleted_recorded.json",
        "gemini_video.mp4",
    }
    assert json.loads(result.fixtures["video_polling_recorded.json"])["status"] == "in_progress"
    assert result.fixtures["gemini_video.mp4"] == clip


async def test_a_clip_with_sound_or_past_eight_seconds_says_so_and_is_still_deleted() -> None:
    clip = movie(audio=True, seconds=8.5).data
    result, interactions = await checked(Interactions([finished(clip)]))
    found = result.findings
    assert (found["polls"], found["durationSeconds"], found["silentAsAsked"]) == (1, 8.5, False)
    assert found["pipelineStores"] is False and "at most 8 s, not 8.5 s" in found["pipelineProblem"]
    assert "video_polling_recorded.json" not in result.fixtures
    assert interactions.asked[-1] == ("DELETE", f"/v1beta/interactions/{REF}")


async def test_a_clip_still_open_when_the_wait_ends_is_deleted_and_counted_at_its_estimate(
    tmp_path: Path,
) -> None:
    result, interactions = await checked(Interactions([OPEN, OPEN, OPEN], deleted=404), step=2.0)
    found = result.findings
    assert (found["timedOut"], found["polls"], found["deleteStatus"]) == (True, 2, 404)
    assert "deleteRefused" in found and interactions.asked[-1][0] == "DELETE"

    async def again() -> CheckResult:
        return result

    report = await run_checks(
        [PaidCheck("gemini_video", video_estimate(), again)], CapLedger(Decimal(5)), tmp_path
    )
    assert report["spend"] == [{"check": "gemini_video", "estimateUsd": "0.560000", "countedUsd": "0.560000"}]
