import asyncio
import hashlib
import re
import uuid
from dataclasses import replace
from datetime import timedelta

from app.media.jobs import MediaDeps, submit_job, visible_job
from app.media.runner import RunnerDeps, abandon_job, run_job
from app.models import User
from app.providers.base import MediaResult
from app.providers.media_router import MediaAsk, MediaCall
from app.providers.router import RouterError
from app.schemas.media import MEDIA_S3_KEY_PATTERN, MediaJobRequest

from .fakes import (
    BUNDLE_KEY,
    NOW,
    STAGE_ID,
    USER_ID,
    FakeBudget,
    FakeGenerator,
    FakeLinks,
    FakeObjects,
    MemoryMedia,
    media_call,
    media_result,
    png_bytes,
    stage,
    stage_claims,
)
from .mp4_builder import movie

STUDENT = User(id=USER_ID, name="Meera Rao", email="meera@example.org", role="STUDENT")
RESEARCHER = User(id=USER_ID, name="Meera Rao", email="meera@example.org", role="RESEARCHER")
GENERATED_AT = NOW + timedelta(seconds=36)


async def queued(memory: MemoryMedia, *, kind: str = "IMAGE", user: User = STUDENT) -> uuid.UUID:
    memory.stages[STAGE_ID] = stage()
    memory.claims[STAGE_ID] = stage_claims()
    body = {"kind": kind, "stageId": str(STAGE_ID), "idempotencyKey": f"media:{uuid.uuid4()}"}
    deps = MediaDeps(store=memory, budget=FakeBudget(), links=FakeLinks(), bundle_key=BUNDLE_KEY, now=NOW)
    view, _ = await submit_job(deps, user, MediaJobRequest.model_validate(body))
    await memory.claim(kind, limit=1, worker_id="test")
    return view.id


def runner(memory: MemoryMedia, generator: FakeGenerator, objects: FakeObjects | None = None) -> RunnerDeps:
    return RunnerDeps(
        store=memory,
        generator=generator,
        objects=objects or FakeObjects(),
        bundle_key=BUNDLE_KEY,
        clock=lambda: GENERATED_AT,
    )


async def view_of(memory: MemoryMedia, job_id: uuid.UUID, user: User = STUDENT):
    deps = MediaDeps(
        store=memory, budget=FakeBudget(), links=FakeLinks(), bundle_key=BUNDLE_KEY, now=GENERATED_AT
    )
    return await visible_job(deps, user, job_id)


async def test_a_successful_image_is_named_stored_labelled_and_charged_once() -> None:
    memory, objects = MemoryMedia(), FakeObjects()
    job_id = await queued(memory)
    hold = memory.jobs[job_id].hold_id
    generator = FakeGenerator([media_call(media_result(png_bytes()))])
    assert await run_job(runner(memory, generator, objects), job_id) == "SUCCEEDED"
    assert generator.released == [hold] and memory.jobs[job_id].hold_id is None
    ask: MediaAsk = generator.asks[0]
    assert (ask.units, ask.principal.user_id, ask.principal.role) == (1.0, USER_ID, "STUDENT")
    key, page = objects.puts
    assert re.fullmatch(MEDIA_S3_KEY_PATTERN, key)
    leaf = key.rsplit("/", 1)[-1]
    assert page == f"media/craft/{hashlib.sha256(objects.puts[key][0]).hexdigest()}/{leaf}"
    assert objects.puts[page] == objects.puts[key] and str(USER_ID) not in page
    assert key.endswith(
        "/KalaVigyan_Generated-Image_2026-11-16_1430_Ajrakhpur-Kachchh_Kutch-Ajrakh"
        "_Pa-Alum-Mordant-Printing-For-Red_Image_Step-06.png"
    )
    view = await view_of(memory, job_id)
    assert view.status == "SUCCEEDED" and view.asset is not None and not view.refunded
    assert (view.asset.label.text, view.asset.label.model, view.asset.label.generated_on) == (
        "AI illustration",
        "gemini-3.1-flash-image",
        "2026-11-16",
    )
    assert memory.ledger[f"media:{job_id}"].units == 1 and f"media-refund:{job_id}" not in memory.ledger


async def test_a_blocked_job_is_refunded_at_once_without_a_retry() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    generator = FakeGenerator([RouterError("refusal", "Gemini declined the media")])
    assert await run_job(runner(memory, generator), job_id) == "BLOCKED"
    refund = memory.ledger[f"media-refund:{job_id}"]
    assert (refund.units, refund.resource, refund.user_id) == (-1, "IMAGE", USER_ID)
    assert await memory.units_used(USER_ID, "IMAGE", NOW) == 0
    view = await view_of(memory, job_id)
    assert view.refunded and view.failure is not None and view.failure.reason == "BLOCKED"


async def test_a_failing_job_is_tried_three_times_then_refunded() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    generator = FakeGenerator([RouterError("exhausted", "Every route failed")] * 3)
    deps = runner(memory, generator)
    assert await run_job(deps, job_id) == "QUEUED"
    assert memory.retries[0][2] == GENERATED_AT + timedelta(seconds=15)
    await memory.claim("IMAGE", limit=1, worker_id="test")
    assert await run_job(deps, job_id) == "QUEUED"
    await memory.claim("IMAGE", limit=1, worker_id="test")
    assert await run_job(deps, job_id) == "FAILED"
    assert memory.jobs[job_id].attempts == 3
    assert memory.ledger[f"media-refund:{job_id}"].units == -1
    assert (await view_of(memory, job_id)).refunded


async def test_a_retry_after_a_bad_output_can_still_succeed() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    generator = FakeGenerator(
        [media_call(media_result(b"not a png")), media_call(media_result(png_bytes(1024, 1024)))]
    )
    deps = runner(memory, generator)
    assert await run_job(deps, job_id) == "QUEUED"
    assert memory.retries[0][1] == "output"
    await memory.claim("IMAGE", limit=1, worker_id="test")
    assert await run_job(deps, job_id) == "SUCCEEDED"


async def test_a_tampered_bundle_is_refused_before_any_model_call() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    memory.jobs[job_id] = replace(memory.jobs[job_id], prompt="Draw the temple deity.")
    generator = FakeGenerator([])
    assert await run_job(runner(memory, generator), job_id) == "FAILED"
    assert generator.asks == [] and memory.jobs[job_id].error == "bundle_mismatch"
    assert memory.ledger[f"media-refund:{job_id}"].units == -1
    assert len(generator.released) == 1


async def test_a_timed_out_attempt_is_retried() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)

    class Slow(FakeGenerator):
        async def generate(self, ask: MediaAsk) -> MediaCall:
            await asyncio.sleep(1)
            raise AssertionError("the timeout should have fired")

    deps = replace(runner(memory, Slow()), timeout_seconds=0.01)
    assert await run_job(deps, job_id) == "QUEUED"
    assert memory.retries[0][1] == "timeout"


async def test_a_video_is_stored_silent_with_its_duration() -> None:
    memory, objects = MemoryMedia(), FakeObjects()
    job_id = await queued(memory, kind="VIDEO", user=RESEARCHER)
    clip = MediaResult(movie().data, "video/mp4", 410, 46336, 46336, "v1_x", "gemini-omni-1.2-flash")
    generator = FakeGenerator([media_call(clip, model="gemini-omni-1.2-flash")])
    assert await run_job(runner(memory, generator, objects), job_id) == "SUCCEEDED"
    assert generator.asks[0].units == 8.0
    (key, (data, mime)), (page, copy) = objects.puts.items()
    assert key.endswith("_Video_Step-06.mp4") and mime == "video/mp4" and b"soun" not in data
    assert page.startswith("media/craft/") and copy == (data, mime)
    view = await view_of(memory, job_id, RESEARCHER)
    assert view.asset is not None and view.asset.duration_seconds == 8.0


async def test_an_abandoned_attempt_counts_and_requeues() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    assert await abandon_job(runner(memory, FakeGenerator()), job_id) == "QUEUED"
    assert memory.retries[0][1] == "abandoned"


async def test_a_stage_that_cannot_be_named_fails_before_any_model_call() -> None:
    memory = MemoryMedia()
    job_id = await queued(memory)
    memory.stages[STAGE_ID] = stage(ordinal=100)
    generator = FakeGenerator([])
    assert await run_job(runner(memory, generator), job_id) == "FAILED"
    assert generator.asks == [] and memory.jobs[job_id].error == "unnameable"
    assert memory.ledger[f"media-refund:{job_id}"].units == -1
