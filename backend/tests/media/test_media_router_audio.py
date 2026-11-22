import uuid
from decimal import Decimal
from typing import Any

import pytest

from app.providers.base import MediaPoll, MediaRequest, MediaResult
from app.providers.budget import SpendState
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaRouter
from app.providers.router import Principal, RouterError

from .audio_routes import SoundStudio, budgeted, elevenlabs_route, mp3, no_session, studio_router
from .mp4_builder import movie


def ask(task: AiTask, seconds: float, role: str = "STUDENT") -> MediaAsk:
    principal = Principal(user_id=uuid.uuid4(), role=role)
    return MediaAsk(task, "A calm underscore.", {"seconds": f"{seconds:g}"}, seconds, principal)


async def test_music_is_made_as_audio_and_reserved_and_settled_per_second(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = budgeted(monkeypatch, {AiTask.MUSIC: [elevenlabs_route("music_v2_5")]})
    calls: list[MediaRequest] = []
    made = await studio_router(calls).generate(ask(AiTask.MUSIC, 90))
    assert [(call.kind, call.model, call.output) for call in calls] == [
        ("MUSIC", "music_v2_5", {"seconds": "90"})
    ]
    assert found.reserved == [{"model": "music_v2_5", "estimate": Decimal("0.412500"), "allowed": True}]
    assert made.cost_usd == Decimal("0.412500") == found.settled[0]["cost_usd"]
    assert (found.settled[0]["outcome"], found.settled[0]["units"]) == ("OK", 90)
    assert made.result.data == mp3(90) and made.provider == "ELEVENLABS"


async def test_a_sound_effect_costs_its_seconds_at_the_published_minute_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = budgeted(monkeypatch, {AiTask.SOUND_EFFECT: [elevenlabs_route("eleven_text_to_sound_v3")]})
    made = await studio_router([]).generate(ask(AiTask.SOUND_EFFECT, 3))
    assert found.reserved[0]["estimate"] == Decimal("0.006000") == made.cost_usd


async def test_past_the_media_cap_a_student_is_refused_before_any_call_and_a_master_admin_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    found = budgeted(monkeypatch, {AiTask.MUSIC: [elevenlabs_route("music_v2_5")]})
    found.spend = SpendState(month_usd=Decimal(900), media_month_usd=Decimal(200), user_day_usd=Decimal(50))
    calls: list[MediaRequest] = []
    with pytest.raises(RouterError) as refused:
        await studio_router(calls).generate(ask(AiTask.MUSIC, 30))
    assert (refused.value.kind, refused.value.reason, calls) == ("ceiling", "MONTHLY_CEILING", [])
    made = await studio_router(calls).generate(ask(AiTask.MUSIC, 30, role="MASTER_ADMIN"))
    assert [entry["allowed"] for entry in found.reserved] == [False, True]
    assert len(calls) == 1 and made.cost_usd == Decimal("0.137500")


async def test_a_video_route_is_polled_no_faster_than_its_adapter_allows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    budgeted(monkeypatch, {AiTask.VIDEO: [elevenlabs_route("veo-3.1-fast-generate-001")]})
    clip = MediaResult(movie().data, "video/mp4", None, None, None, "v1", None)
    polls = [MediaPoll(done=False), MediaPoll(done=True, result=clip)]

    class Clips(SoundStudio):
        video_poll_seconds = 10.0

        async def start_video(self, req: MediaRequest) -> str:
            return "v1"

        async def poll_video(self, ref: str) -> MediaPoll:
            return polls.pop(0)

    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    router = MediaRouter(
        session_factory=no_session, adapter_factory=lambda choice, key: Clips([]), sleep=sleep
    )
    video = MediaAsk(
        AiTask.VIDEO, "Show one stage.", {"duration": "8s"}, 8.0, Principal(uuid.uuid4(), "STUDENT")
    )
    made: Any = await router.generate(video)
    assert slept == [10.0] and made.cost_usd == Decimal("0.800000")
