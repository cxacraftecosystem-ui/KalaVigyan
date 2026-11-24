import json
from collections.abc import Callable
from pathlib import Path

import httpx
import pytest

from app.providers.base import BilledFailure, ChatRequest, MediaPoll, MediaRequest, ProviderError
from app.providers.elevenlabs_media import IMAGE_POLL_SECONDS, IMAGE_POLLS_MAX, ElevenLabsMediaAdapter
from app.providers.registry import build_adapter

from .fakes import png_bytes
from .mp4_builder import movie

FIXTURES = Path(__file__).parent / "fixtures"
KEY = "test-only-elevenlabs-key-not-a-secret"
GENERATION = "JWr5N6X9ZTqf8jD2LmQb"
CONTENT = f"https://storage.googleapis.com/generations/{GENERATION}"
BYTES_PER_SECOND = 128_000 // 8

Handler = Callable[[httpx.Request], httpx.Response]


def recorded(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def answer(name: str, status: int = 200, headers: dict[str, str] | None = None) -> httpx.Response:
    return httpx.Response(
        status, content=recorded(name), headers={"content-type": "application/json", **(headers or {})}
    )


def adapter(
    handler: Handler, slept: list[float] | None = None
) -> tuple[ElevenLabsMediaAdapter, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    async def sleep(seconds: float) -> None:
        if slept is not None:
            slept.append(seconds)

    client = httpx.AsyncClient(transport=httpx.MockTransport(record))
    made = ElevenLabsMediaAdapter(
        api_key=KEY, base_url=None, preset="elevenlabs", extra={}, learned={}, client=client, sleep=sleep
    )
    return made, seen


def audio(seconds: float) -> bytes:
    return b"\xff\xfb" * round(seconds * BYTES_PER_SECOND / 2)


def audio_handler(seconds: float) -> Handler:
    return lambda request: httpx.Response(
        200, content=audio(seconds), headers={"content-type": "application/octet-stream"}
    )


def flow(*answers: httpx.Response, content: bytes = b"", content_type: str = "image/png") -> Handler:
    queue = list(answers)

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "storage.googleapis.com":
            return httpx.Response(200, content=content, headers={"content-type": content_type})
        return queue.pop(0)

    return handle


def music_ask(seconds: str = "90") -> MediaRequest:
    return MediaRequest(
        model="music_v2_5", prompt="A calm underscore.", kind="MUSIC", output={"seconds": seconds}
    )


def image_ask() -> MediaRequest:
    output = {"aspect_ratio": "1:1", "image_size": "1K"}
    return MediaRequest(model="gemini-3.1-flash-image", prompt="Draw one stage.", kind="IMAGE", output=output)


def video_ask() -> MediaRequest:
    output = {"aspect_ratio": "16:9", "resolution": "720p", "duration": "8s"}
    return MediaRequest(
        model="veo-3.1-fast-generate-001", prompt="Show one stage.", kind="VIDEO", output=output
    )


async def test_music_asks_for_an_instrumental_mp3_of_the_length_in_milliseconds() -> None:
    made, seen = adapter(audio_handler(90))
    result = await made.generate_audio(music_ask())
    [request] = seen
    assert (request.method, str(request.url)) == (
        "POST",
        "https://api.elevenlabs.io/v1/music?output_format=mp3_44100_128",
    )
    assert request.headers["xi-api-key"] == KEY
    assert json.loads(request.content) == {
        "prompt": "A calm underscore.",
        "music_length_ms": 90000,
        "model_id": "music_v2_5",
        "force_instrumental": True,
    }
    assert (result.mime, result.data, result.served_model) == ("audio/mpeg", audio(90), "music_v2_5")
    assert result.output_tokens is None


async def test_a_sound_effect_names_its_duration_influence_and_model_and_never_loops() -> None:
    made, seen = adapter(audio_handler(2))
    request = MediaRequest(
        model="eleven_text_to_sound_v3",
        prompt="Water over stones.",
        kind="SOUND_EFFECT",
        output={"seconds": "2"},
    )
    result = await made.generate_audio(request)
    [sent] = seen
    assert (sent.url.path, sent.url.params["output_format"]) == ("/v1/sound-generation", "mp3_44100_128")
    assert json.loads(sent.content) == {
        "text": "Water over stones.",
        "duration_seconds": 2.0,
        "prompt_influence": 0.5,
        "model_id": "eleven_text_to_sound_v3",
        "loop": False,
    }
    assert result.data == audio(2)


@pytest.mark.parametrize(
    ("kind", "seconds"),
    [("MUSIC", "2.9"), ("MUSIC", "301"), ("SOUND_EFFECT", "0.4"), ("SOUND_EFFECT", "31"), ("MUSIC", "long")],
)
async def test_a_length_off_the_documented_range_is_refused_before_any_call(kind: str, seconds: str) -> None:
    made, seen = adapter(audio_handler(2))
    request = MediaRequest(model="m", prompt="A calm underscore.", kind=kind, output={"seconds": seconds})
    with pytest.raises(ProviderError) as refused:
        await made.generate_audio(request)
    assert refused.value.kind == "bad_request" and seen == []


async def test_a_refused_body_stops_the_route_walk_and_a_rate_limit_waits() -> None:
    made, _ = adapter(lambda request: answer("elevenlabs_validation_error.json", 422))
    with pytest.raises(ProviderError) as refused:
        await made.generate_audio(music_ask())
    assert (refused.value.kind, refused.value.status, refused.value.retryable) == ("bad_request", 422, False)
    limited, _ = adapter(
        lambda request: answer("elevenlabs_validation_error.json", 429, {"retry-after": "3"})
    )
    with pytest.raises(ProviderError) as waited:
        await limited.generate_audio(music_ask())
    assert (waited.value.kind, waited.value.retryable, waited.value.retry_after) == ("rate_limit", True, 3.0)


async def test_an_empty_answer_is_off_the_documented_shape() -> None:
    made, _ = adapter(lambda request: httpx.Response(200, content=b""))
    with pytest.raises(ProviderError) as failed:
        await made.generate_audio(music_ask())
    assert failed.value.kind == "error" and "documented shape" in str(failed.value)


async def test_an_image_is_created_polled_and_fetched_from_its_signed_link_without_the_key() -> None:
    slept: list[float] = []
    picture = png_bytes()
    handler = flow(
        answer("elevenlabs_flow_created.json"),
        answer("elevenlabs_flow_generating.json"),
        answer("elevenlabs_flow_completed_image.json"),
        content=picture,
    )
    made, seen = adapter(handler, slept)
    result = await made.generate_image(image_ask())
    create, first, second, download = seen
    assert (create.method, create.url.path) == ("POST", "/v1/flows/image")
    assert json.loads(create.content) == {
        "model_id": "gemini-3.1-flash-image",
        "prompt": "Draw one stage.",
        "aspect_ratio": "1:1",
        "resolution": "1K",
    }
    assert [first.url.path, second.url.path] == [f"/v1/flows/image/{GENERATION}"] * 2
    assert str(download.url) == CONTENT and "xi-api-key" not in download.headers
    assert slept == [IMAGE_POLL_SECONDS] == [2.0]
    assert (result.data, result.mime, result.provider_ref, result.served_model) == (
        picture,
        "image/png",
        GENERATION,
        None,
    )


async def test_an_image_that_never_finishes_is_given_up_after_the_poll_limit() -> None:
    slept: list[float] = []
    answers = [answer("elevenlabs_flow_created.json")]
    answers += [answer("elevenlabs_flow_generating.json") for _ in range(IMAGE_POLLS_MAX)]
    made, seen = adapter(flow(*answers), slept)
    with pytest.raises(BilledFailure) as unfinished:
        await made.generate_image(image_ask())
    assert (unfinished.value.kind, unfinished.value.retryable) == ("unavailable", True)
    assert len(seen) == 1 + 90 and len(slept) == 90


async def test_a_moderated_generation_is_a_refusal_and_other_failures_try_the_next_route() -> None:
    made, _ = adapter(
        flow(answer("elevenlabs_flow_created.json"), answer("elevenlabs_flow_failed_moderated.json"))
    )
    with pytest.raises(ProviderError) as refused:
        await made.generate_image(image_ask())
    assert refused.value.kind == "refusal" and not isinstance(refused.value, BilledFailure)
    failed = json.loads(recorded("elevenlabs_flow_failed_moderated.json")) | {"failure_reason": "model_error"}
    broken = httpx.Response(200, json=failed)
    made, _ = adapter(flow(answer("elevenlabs_flow_created.json"), broken))
    with pytest.raises(ProviderError) as errored:
        await made.generate_image(image_ask())
    assert (errored.value.kind, errored.value.retryable) == ("error", False)
    assert not isinstance(errored.value, BilledFailure)


async def test_a_finished_generation_whose_download_fails_is_billed_work_lost() -> None:
    queue = [answer("elevenlabs_flow_created.json"), answer("elevenlabs_flow_completed_image.json")]

    def handle(request: httpx.Request) -> httpx.Response:
        if request.url.host == "storage.googleapis.com":
            return httpx.Response(503, content=b"")
        return queue.pop(0)

    made, seen = adapter(handle)
    with pytest.raises(BilledFailure) as lost:
        await made.generate_image(image_ask())
    assert lost.value.retryable and len(seen) == 3


async def test_a_poll_of_a_started_generation_that_fails_is_billed_work_lost() -> None:
    limited = answer("elevenlabs_validation_error.json", 503)
    made, _ = adapter(flow(answer("elevenlabs_flow_created.json"), limited))
    with pytest.raises(BilledFailure) as lost:
        await made.generate_image(image_ask())
    assert (lost.value.kind, lost.value.status) == ("unavailable", 503)


async def test_a_generation_that_was_never_started_is_not_billed() -> None:
    made, _ = adapter(lambda request: answer("elevenlabs_validation_error.json", 503))
    with pytest.raises(ProviderError) as refused:
        await made.generate_image(image_ask())
    assert refused.value.kind == "unavailable" and not isinstance(refused.value, BilledFailure)


async def test_a_content_link_that_is_not_https_is_never_fetched() -> None:
    completed = json.loads(recorded("elevenlabs_flow_completed_image.json"))
    plain = httpx.Response(200, json=completed | {"content_url": "http://storage.googleapis.com/x"})
    made, seen = adapter(flow(answer("elevenlabs_flow_created.json"), plain))
    with pytest.raises(ProviderError) as refused:
        await made.generate_image(image_ask())
    assert refused.value.kind == "error" and len(seen) == 2


async def test_a_generation_answer_for_another_id_is_off_the_documented_shape() -> None:
    other = httpx.Response(200, json={"id": "another", "status": "generating"})
    made, _ = adapter(flow(answer("elevenlabs_flow_created.json"), other))
    with pytest.raises(ProviderError) as refused:
        await made.generate_image(image_ask())
    assert refused.value.kind == "error"


async def test_a_video_asks_for_eight_silent_seconds_at_720p_without_prompt_rewrites() -> None:
    clip = movie().data
    handler = flow(
        answer("elevenlabs_flow_created.json"),
        answer("elevenlabs_flow_generating.json"),
        answer("elevenlabs_flow_completed_video.json"),
        content=clip,
        content_type="video/mp4",
    )
    made, seen = adapter(handler)
    ref = await made.start_video(video_ask())
    assert ref == GENERATION
    assert json.loads(seen[0].content) == {
        "model_id": "veo-3.1-fast-generate-001",
        "prompt": "Show one stage.",
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "duration_secs": "8",
        "generate_audio": False,
        "enhance_prompt": False,
    }
    assert await made.poll_video(ref) == MediaPoll(done=False)
    done = await made.poll_video(ref)
    assert done.done and done.result is not None
    assert (done.result.mime, done.result.data) == ("video/mp4", clip)
    assert seen[1].url.path == f"/v1/flows/video/{GENERATION}"
    assert made.video_poll_seconds == 10.0


async def test_the_registry_builds_the_adapter_only_with_the_elevenlabs_key() -> None:
    built = build_adapter(
        preset="elevenlabs", kind="elevenlabs", api_key=KEY, api_key_name="ELEVENLABS_API_KEY"
    )
    assert isinstance(built, ElevenLabsMediaAdapter)
    with pytest.raises(ProviderError) as unchat:
        await built.chat(ChatRequest(model="music_v2_5", system="", user=""))
    assert unchat.value.kind == "unavailable"
    with pytest.raises(ProviderError) as keyless:
        build_adapter(preset="elevenlabs", kind="elevenlabs", api_key=None, api_key_name="ELEVENLABS_API_KEY")
    assert keyless.value.kind == "auth"
    await built.aclose()
