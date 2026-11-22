from datetime import datetime, timedelta

import pytest

from app.providers.catalogue import AiTask
from app.providers.router import RouterError
from app.research.explainer import Explainer
from app.schemas.listen import ListenWord
from app.services.naming import narration_key, score_key, score_manifest_key
from app.voice.film_score import (
    SCORE_LEASE_SECONDS,
    ScoreBeingMade,
    ScoreRefused,
    film_score,
    planned_score,
    score_in_making,
)
from app.voice.narration import narration_cache_id, spoken_blocks
from app.voice.narration_cache import NarratedPart, NarrationManifest, store_manifest
from app.voice.object_lease import LEASE_LEAF, ObjectLease
from app.voice.score_cache import UNNAMED_LEAF

from .listen_fakes import VOICE_ID, MemoryObjects, golden_explainer
from .score_fakes import MADE_AT, MemoryMaker, score_ask, score_deps

ANSWER = golden_explainer().answer_id
LEASE = score_manifest_key(ANSWER, "en", leaf=LEASE_LEAF)
HEARD = {"s1.b1": 60.0, "s2.b1": 40.0, "s3.b1": 40.0}


async def narrated(objects: MemoryObjects, explainer: Explainer, seconds: dict[str, float]) -> None:
    for block in spoken_blocks(explainer, None):
        if block.block_id not in seconds:
            continue
        cache_id = narration_cache_id(block.content_hash, language="en", voice_id=VOICE_ID)
        word = ListenWord(sentence_id=block.sentences[0].sentence_id, text="Ajrakh", start=0.0, end=0.4)
        part = NarratedPart(
            key=narration_key(cache_id, "part.mp3"),
            language="en",
            duration_seconds=seconds[block.block_id],
            words=[word],
        )
        manifest = NarrationManifest(
            schema_version=1,
            cache_id=cache_id,
            model="eleven_v4",
            voice_id=VOICE_ID,
            language="en",
            content_hash=block.content_hash,
            parts=[part],
        )
        await store_manifest(objects, manifest)


def leased(objects: MemoryObjects, taken_at: datetime) -> None:
    lease = ObjectLease(schema_version=1, cache_id="d" * 64, taken_at=taken_at)
    objects.stored[LEASE] = (lease.model_dump_json(by_alias=True).encode(), "application/json")


async def test_the_bed_is_cut_from_the_heard_narration_once_every_block_has_been_heard() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    await narrated(objects, golden_explainer(), HEARD)
    score = await film_score(score_ask(golden_explainer()), score_deps(objects, maker, voice_id=VOICE_ID))
    assert maker.calls[0].output == {"seconds": "150"}
    assert score.music is not None and score.music.duration_seconds == 150.0


async def test_a_score_cut_from_the_estimate_is_made_again_when_the_narration_is_heard() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    deps = score_deps(objects, maker, voice_id=VOICE_ID)
    await film_score(score_ask(golden_explainer()), deps)
    assert maker.calls[0].output == {"seconds": "90"}
    await narrated(objects, golden_explainer(), {"s1.b1": 60.0})
    await film_score(score_ask(golden_explainer()), deps)
    assert len(maker.calls) == 2
    await narrated(objects, golden_explainer(), HEARD)
    await film_score(score_ask(golden_explainer()), deps)
    assert maker.tasks()[2:] == ["MUSIC"] and maker.calls[2].output == {"seconds": "150"}


async def test_a_score_another_ask_is_making_is_not_made_twice() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    leased(objects, MADE_AT - timedelta(seconds=SCORE_LEASE_SECONDS - 1))
    deps = score_deps(objects, maker)
    assert await score_in_making(score_ask(golden_explainer()), deps)
    with pytest.raises(ScoreBeingMade):
        await film_score(score_ask(golden_explainer()), deps)
    assert maker.calls == [] and LEASE in objects.stored


async def test_a_lapsed_lease_is_taken_over_and_every_lease_is_released() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    leased(objects, MADE_AT - timedelta(seconds=SCORE_LEASE_SECONDS))
    deps = score_deps(objects, maker)
    assert not await score_in_making(score_ask(golden_explainer()), deps)
    await film_score(score_ask(golden_explainer()), deps)
    assert maker.tasks() == ["MUSIC", "SOUND_EFFECT"] and LEASE not in objects.stored
    failed = MemoryObjects()
    with pytest.raises(RouterError, match="Every route"):
        await film_score(score_ask(golden_explainer()), score_deps(failed, MemoryMaker(failing=AiTask.MUSIC)))
    assert LEASE not in failed.stored


async def test_a_clip_used_again_loses_its_unnamed_mark() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    first = await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    cache_id = first.cues[0].audio_url.split("/media/score/")[1].split("/")[0]
    objects.stored[score_key(cache_id, UNNAMED_LEAF)] = (b"{}", "application/json")
    shorter = golden_explainer().model_copy(update={"sections": golden_explainer().sections[:2]})
    await film_score(score_ask(shorter), score_deps(objects, maker))
    assert score_key(cache_id, UNNAMED_LEAF) not in objects.stored


async def test_an_explainer_with_nothing_to_play_has_no_plan() -> None:
    explainer = golden_explainer()
    empty = explainer.model_copy(update={"sections": [], "lede": None})
    with pytest.raises(ScoreRefused, match="nothing to play"):
        await planned_score(score_ask(empty), score_deps(MemoryObjects(), MemoryMaker()))
