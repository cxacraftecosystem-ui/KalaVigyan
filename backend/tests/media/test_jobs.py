import uuid
from dataclasses import replace
from datetime import timedelta

import pytest

from app.media.bundle import opened_bundle
from app.media.heartbeat import worker_listening
from app.media.jobs import MediaDeps, MediaRefused, idempotency_hash, media_options, submit_job, visible_job
from app.media.records import AssetRecord
from app.models import User
from app.providers.router import RouterError
from app.schemas.media import MediaJobRequest

from .fakes import (
    ALUM_CLAIM,
    BUNDLE_KEY,
    NOW,
    OTHER_STAGE_ID,
    PA_CLAIM,
    STAGE_ID,
    THIN_STAGE_ID,
    USER_ID,
    FakeBudget,
    FakeLinks,
    MemoryMedia,
    claim,
    stage,
    stage_claims,
)

SECONDS_TO_IST_MIDNIGHT = 9 * 3600 + 29 * 60 + 55


def learner(role: str = "STUDENT", user_id: uuid.UUID = USER_ID) -> User:
    return User(id=user_id, name="Meera Rao", email="meera@example.org", role=role)


def store() -> MemoryMedia:
    memory = MemoryMedia()
    for stage_id in (STAGE_ID, OTHER_STAGE_ID, THIN_STAGE_ID):
        memory.stages[stage_id] = stage(stage_id)
    memory.claims[STAGE_ID] = stage_claims()
    memory.claims[OTHER_STAGE_ID] = stage_claims()
    memory.claims[THIN_STAGE_ID] = [claim(uuid.UUID(int=5), "Only one cited fact.")]
    return memory


def deps(memory: MemoryMedia, budget: FakeBudget | None = None, **changes: object) -> MediaDeps:
    base = MediaDeps(
        store=memory, budget=budget or FakeBudget(), links=FakeLinks(), bundle_key=BUNDLE_KEY, now=NOW
    )
    return replace(base, **changes)


def ask(key: str = "media:00000000-0000-4000-8000-000000000001", **changes: object) -> MediaJobRequest:
    body = {"kind": "IMAGE", "stageId": str(STAGE_ID), "idempotencyKey": key, **changes}
    return MediaJobRequest.model_validate(body)


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_options_list_kinds_with_units_left_and_stages_with_two_claims() -> None:
    options = await media_options(deps(store()), learner(), "Kutch-Ajrakh")
    assert [(k.kind, k.remaining_today) for k in options.kinds] == [("IMAGE", 5)]
    assert [s.stage_id for s in options.stages] == [STAGE_ID, OTHER_STAGE_ID]
    researcher = await media_options(deps(store()), learner("RESEARCHER"), "Kutch-Ajrakh")
    assert [(k.kind, k.remaining_today) for k in researcher.kinds] == [("IMAGE", 30), ("VIDEO", 5)]
    admin = await media_options(deps(store()), learner("MASTER_ADMIN"), "Kutch-Ajrakh")
    assert [k.remaining_today for k in admin.kinds] == [None, None]


async def test_by_default_every_kind_is_offered_with_no_count_of_what_is_left() -> None:
    student = await media_options(deps(store()), learner(), "Kutch-Ajrakh")
    researcher = await media_options(deps(store()), learner("RESEARCHER"), "Kutch-Ajrakh")
    assert [(k.kind, k.remaining_today) for k in student.kinds] == [("IMAGE", None)]
    assert [(k.kind, k.remaining_today) for k in researcher.kinds] == [("IMAGE", None), ("VIDEO", None)]


async def test_by_default_no_daily_count_refuses_a_job() -> None:
    memory = store()
    for n in range(12):
        view, created = await submit_job(deps(memory), learner(), ask(f"media:key-number-{n:08d}"))
        memory.jobs[view.id] = replace(memory.jobs[view.id], status="SUCCEEDED")
        assert created
    assert len(memory.jobs) == 12


async def test_options_offer_nothing_when_media_cannot_be_made() -> None:
    closed = await media_options(deps(store(), FakeBudget(open=False)), learner(), "Kutch-Ajrakh")
    unkeyed = await media_options(deps(store(), bundle_key=None), learner(), "Kutch-Ajrakh")
    assert closed.kinds == [] and closed.stages == []
    assert unkeyed.kinds == [] and unkeyed.stages == []
    with pytest.raises(MediaRefused) as missing:
        await media_options(deps(store()), learner(), "No-Such-Craft")
    assert missing.value.reason == "not_found"


async def test_a_worker_silent_for_over_five_minutes_offers_and_queues_nothing() -> None:
    silent = store()
    silent.worker_heard_at = NOW - timedelta(minutes=5, seconds=1)
    assert (await media_options(deps(silent), learner(), "Kutch-Ajrakh")).kinds == []
    with pytest.raises(MediaRefused) as refused:
        await submit_job(deps(silent), learner(), ask())
    assert refused.value.reason == "not_configured" and silent.jobs == {}
    silent.worker_heard_at = NOW - timedelta(minutes=5)
    assert [k.kind for k in (await media_options(deps(silent), learner(), "Kutch-Ajrakh")).kinds] == ["IMAGE"]
    never = store()
    never.worker_heard_at = None
    assert (await media_options(deps(never), learner(), "Kutch-Ajrakh")).kinds == []


def test_a_heartbeat_is_read_as_listening_for_five_minutes_and_never_when_unreadable() -> None:
    beat = {"at": "2026-11-16T09:00:05Z", "worker": "box:41"}
    assert worker_listening(beat, now=NOW + timedelta(minutes=5))
    assert not worker_listening(beat, now=NOW + timedelta(minutes=5, seconds=1))
    assert not worker_listening(None, now=NOW)
    assert not worker_listening({"at": "yesterday"}, now=NOW)


async def test_a_new_job_reserves_one_unit_holds_dollars_and_seals_its_bundle() -> None:
    memory, budget = store(), FakeBudget()
    view, created = await submit_job(deps(memory, budget), learner(), ask())
    assert created and view.status == "QUEUED" and view.poll_after_seconds == 3
    assert view.claim_ids == [PA_CLAIM, ALUM_CLAIM]
    job = memory.jobs[view.id]
    assert memory.ledger[f"media:{view.id}"].units == 1
    assert len(budget.holds) == 1 and budget.holds[0].units == 1.0 and job.hold_id is not None
    assert opened_bundle(BUNDLE_KEY, job.bundle, job, now=NOW) == "STUDENT"
    assert memory.queued == [view.id]


async def test_the_same_key_answers_the_same_job_and_another_body_is_a_conflict() -> None:
    memory = store()
    first, _ = await submit_job(deps(memory), learner(), ask())
    again, created = await submit_job(deps(memory), learner(), ask())
    assert again.id == first.id and not created
    assert len(memory.ledger) == 1
    with pytest.raises(MediaRefused) as conflict:
        await submit_job(deps(memory), learner(), ask(stageId=str(OTHER_STAGE_ID)))
    assert conflict.value.reason == "key_conflict"
    assert idempotency_hash(USER_ID, "k" * 16) != idempotency_hash(uuid.uuid4(), "k" * 16)


async def test_refusals_follow_the_contract_order() -> None:
    memory = store()
    with pytest.raises(MediaRefused) as video:
        await submit_job(deps(memory), learner(), ask(kind="VIDEO"))
    with pytest.raises(MediaRefused) as unknown:
        await submit_job(deps(memory), learner(), ask(stageId=str(uuid.uuid4())))
    with pytest.raises(MediaRefused) as thin:
        await submit_job(deps(memory), learner(), ask(stageId=str(THIN_STAGE_ID)))
    assert (video.value.reason, unknown.value.reason, thin.value.reason) == (
        "capability",
        "not_found",
        "too_few_claims",
    )
    hidden = store()
    hidden.stages[STAGE_ID] = stage(active=False)
    with pytest.raises(MediaRefused, match="isn't available"):
        await submit_job(deps(hidden), learner(), ask())
    assert (await submit_job(deps(hidden), learner("PROFESSOR"), ask()))[1]


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_a_spent_allowance_refuses_until_midnight_ist() -> None:
    memory = store()
    for n in range(5):
        view, _ = await submit_job(deps(memory), learner(), ask(f"media:key-number-{n:08d}"))
        memory.jobs[view.id] = replace(memory.jobs[view.id], status="SUCCEEDED")
    with pytest.raises(MediaRefused) as spent:
        await submit_job(deps(memory), learner(), ask("media:key-number-00000099"))
    assert spent.value.reason == "no_units"
    assert spent.value.retry_after == SECONDS_TO_IST_MIDNIGHT


async def test_three_open_jobs_make_a_fourth_wait() -> None:
    memory = store()
    for n in range(3):
        await submit_job(deps(memory), learner(), ask(f"media:open-job-{n:010d}"))
    with pytest.raises(MediaRefused) as busy:
        await submit_job(deps(memory), learner(), ask("media:open-job-0000000009"))
    assert (busy.value.reason, busy.value.retry_after) == ("busy", 30)


async def test_a_budget_refusal_is_the_router_s_sentence_and_spends_nothing() -> None:
    memory = store()
    budget = FakeBudget(
        refuse_hold=RouterError("ceiling", "The monthly budget for images and video has been reached.")
    )
    with pytest.raises(MediaRefused) as refused:
        await submit_job(deps(memory, budget), learner(), ask())
    assert refused.value.reason == "budget" and "monthly budget" in refused.value.message
    assert memory.ledger == {} and memory.jobs == {}


async def test_a_shared_asset_with_the_same_prompt_is_returned_free_and_at_once() -> None:
    memory = store()
    producer, _ = await submit_job(deps(memory), learner("PROFESSOR", uuid.uuid4()), ask())
    asset_id = uuid.uuid4()
    memory.assets[asset_id] = AssetRecord(
        id=asset_id,
        job_id=producer.id,
        s3_key=f"media/{USER_ID}/{'0' * 32}/KalaVigyan_Generated-Image_2026-11-16_1430_Kutch-Ajrakh_Pa_Image_Step-06.png",
        mime="image/png",
        width=1024,
        height=1024,
        duration_seconds=None,
        model="gemini-3.1-flash-image",
        alt_text="Alt.",
        visibility="CRAFT_SHARED",
        created_at=NOW,
    )
    budget = FakeBudget()
    view, created = await submit_job(deps(memory, budget), learner(), ask("media:second-learner-key"))
    assert not created and view.cached and view.status == "SUCCEEDED" and view.attempts == 0
    assert not view.refunded and view.asset is not None and view.asset.id == asset_id
    assert f"media:{view.id}" not in memory.ledger and budget.holds == []
    memory.assets[asset_id] = replace(memory.assets[asset_id], visibility="PRIVATE")
    with pytest.raises(MediaRefused) as unshared:
        await visible_job(deps(memory), learner(), view.id)
    assert unshared.value.reason == "unshared"


async def test_a_job_is_visible_to_its_requester_only() -> None:
    memory = store()
    view, _ = await submit_job(deps(memory), learner(), ask())
    assert (await visible_job(deps(memory), learner(), view.id)).id == view.id
    with pytest.raises(MediaRefused) as other:
        await visible_job(deps(memory), learner(user_id=uuid.uuid4()), view.id)
    assert other.value.reason == "not_found"
