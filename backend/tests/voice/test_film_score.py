import hashlib
import uuid
from decimal import Decimal
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.providers.base import MediaResult
from app.providers.budget import SpendState
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaCall
from app.providers.router import RouterError
from app.research.blocks_play import SimulationBlock
from app.research.explainer import Explainer
from app.schemas.film import FilmScore
from app.services.naming import score_key, score_manifest_key
from app.voice.film_score import ScoreRefused, checked_score_audio, film_score
from app.voice.score_cache import CLIP_LEAF
from app.voice.score_prompts import SCORE_CUES, SCORE_MUSIC_PROMPT

from ..contracts.golden import dumped, golden_text
from ..contracts.phase_c_golden import phase_c
from ..media.audio_routes import budgeted, elevenlabs_route, mp3, studio_router
from .listen_fakes import BUCKET_HOST, MemoryObjects, golden_explainer
from .score_fakes import SERVED_AT, MemoryMaker, score_ask, score_deps

ANSWER = golden_explainer().answer_id
TABLE_PROMPTS = {SCORE_MUSIC_PROMPT, *(cue.prompt for cue in SCORE_CUES.values())}
SFX = "eleven_text_to_sound_v3"


def clip_id(task: str, model: str, prompt: str, seconds: str) -> str:
    parts = ("kalavigyan-score", "film-score/v1", task, model, prompt, seconds)
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def manifests(objects: MemoryObjects) -> list[str]:
    return sorted(key for key in objects.stored if key.endswith("/score.json"))


def in_hindi(explainer: Explainer) -> Explainer:
    understood = explainer.understood.model_copy(update={"language": "hi"})
    return explainer.model_copy(update={"understood": understood})


def with_hidden_simulation(*, alone: bool) -> Explainer:
    simulation = SimulationBlock.model_validate(phase_c()["sections"][0]["blocks"][0])
    hidden = simulation.model_copy(update={"hidden": True})
    explainer = golden_explainer()
    first, *rest = explainer.sections
    if alone:
        return explainer.model_copy(update={"sections": [first.model_copy(update={"blocks": [hidden]})]})
    shown = first.model_copy(update={"blocks": [*first.blocks, hidden]})
    return explainer.model_copy(update={"sections": [shown, *rest]})


def made_call(data: bytes, mime: str = "audio/mpeg") -> MediaCall:
    result = MediaResult(data, mime, None, None, None, None, "music_v2_5")
    return MediaCall(result, "ELEVENLABS", "music_v2_5", uuid.uuid4(), Decimal(0))


async def test_the_phase_a_score_is_made_once_then_served_from_the_cache_as_the_golden() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert maker.tasks() == ["MUSIC", "SOUND_EFFECT", "SOUND_EFFECT"]
    assert [call.output for call in maker.calls] == [{"seconds": "90"}, {"seconds": "2"}, {"seconds": "3"}]
    assert [call.units for call in maker.calls] == [90.0, 2.0, 3.0]
    again = await film_score(score_ask(golden_explainer()), score_deps(objects, maker, SERVED_AT))
    assert len(maker.calls) == 3
    assert dumped(FilmScore, again) == golden_text("film.score.golden.json")
    assert manifests(objects) == [score_manifest_key(ANSWER, "en")]


async def test_audio_is_content_addressed_so_another_language_reuses_the_cues() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    score = await film_score(score_ask(in_hindi(golden_explainer())), score_deps(objects, maker))
    assert maker.tasks() == ["MUSIC", "SOUND_EFFECT", "SOUND_EFFECT"]
    water = clip_id("SOUND_EFFECT", SFX, SCORE_CUES["prose", "GEOGRAPHY"].prompt, "3")
    assert (score.language, len(score.cues)) == ("hi", 2)
    assert score.cues[1].audio_url.startswith(f"{BUCKET_HOST}/media/score/{water}/")
    assert manifests(objects) == sorted([score_manifest_key(ANSWER, "en"), score_manifest_key(ANSWER, "hi")])


async def test_a_refused_reservation_adds_no_score_and_no_audio() -> None:
    objects, maker = MemoryObjects(), MemoryMaker(refusing=True)
    with pytest.raises(RouterError) as refused:
        await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert refused.value.kind == "ceiling"
    assert objects.stored == {}


async def test_a_failed_call_adds_nothing_and_the_next_ask_reuses_what_was_made() -> None:
    objects, maker = MemoryObjects(), MemoryMaker(failing=AiTask.SOUND_EFFECT)
    with pytest.raises(RouterError):
        await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert manifests(objects) == []
    tapping = clip_id("SOUND_EFFECT", SFX, SCORE_CUES["process_ladder", None].prompt, "2")
    assert not any(key.startswith(f"media/score/{tapping}/") for key in objects.stored)
    music = clip_id("MUSIC", "music_v2_5", SCORE_MUSIC_PROMPT, "90")
    assert score_key(music, CLIP_LEAF) in objects.stored
    maker.failing = None
    maker.calls.clear()
    score = await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert maker.tasks() == ["SOUND_EFFECT", "SOUND_EFFECT"] and score.music is not None


async def test_audio_of_the_wrong_length_is_never_stored() -> None:
    objects, maker = MemoryObjects(), MemoryMaker(heard_seconds=5.0)
    with pytest.raises(InvalidInput, match=r"5.0 s of audio where 90 s"):
        await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert not any(kind == "audio/mpeg" for _, kind in objects.stored.values())
    assert manifests(objects) == []


async def test_through_the_media_router_a_master_admin_is_never_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    routes = {AiTask.MUSIC: [elevenlabs_route("music_v2_5")], AiTask.SOUND_EFFECT: [elevenlabs_route(SFX)]}
    found = budgeted(monkeypatch, routes)
    found.spend = SpendState(
        month_usd=Decimal(5000), media_month_usd=Decimal(5000), user_day_usd=Decimal(5000)
    )
    objects: MemoryObjects = MemoryObjects()
    calls: list[Any] = []
    with pytest.raises(RouterError) as refused:
        await film_score(score_ask(golden_explainer()), score_deps(objects, studio_router(calls)))
    assert refused.value.kind == "ceiling" and calls == [] and objects.stored == {}
    master = score_ask(golden_explainer(), role="MASTER_ADMIN")
    score = await film_score(master, score_deps(objects, studio_router(calls)))
    assert [call.kind for call in calls] == ["MUSIC", "SOUND_EFFECT", "SOUND_EFFECT"]
    assert score.label.models == ["music_v2_5", SFX]
    assert [entry["allowed"] for entry in found.reserved][-3:] == [True, True, True]


async def test_only_fixed_table_prompts_are_sent_never_the_explainer_s_words() -> None:
    maker = MemoryMaker()
    explainer = golden_explainer()
    await film_score(score_ask(explainer), score_deps(MemoryObjects(), maker))
    assert {call.prompt for call in maker.calls} <= TABLE_PROMPTS
    named = {"kutch", "ajrakh", "kachchh", "bagru", "gujarat", "sindh", "alizarin", "indigo", "madder"}
    sentences = [
        s.text for section in explainer.sections for b in section.blocks for s in b.cited_sentences()
    ]
    for prompt in TABLE_PROMPTS:
        words = set(prompt.casefold().replace(",", " ").replace(".", " ").split())
        assert not words & named and not any(ch.isdigit() for ch in prompt)
        assert not any(sentence in prompt or prompt in sentence for sentence in sentences)


async def test_without_a_sound_effect_route_the_score_is_the_music_bed_alone() -> None:
    maker = MemoryMaker()
    maker.models[AiTask.SOUND_EFFECT] = None
    score = await film_score(score_ask(golden_explainer()), score_deps(MemoryObjects(), maker))
    assert maker.tasks() == ["MUSIC"] and score.cues == [] and score.label.models == ["music_v2_5"]


async def test_a_changed_explainer_or_a_damaged_manifest_is_scored_again() -> None:
    objects, maker = MemoryObjects(), MemoryMaker()
    await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    shorter = golden_explainer().model_copy(update={"sections": golden_explainer().sections[:2]})
    await film_score(score_ask(shorter), score_deps(objects, maker))
    assert maker.tasks()[3:] == ["MUSIC"]
    assert maker.calls[3].units == 70.0
    objects.stored[score_manifest_key(ANSWER, "en")] = (b"{}", "application/json")
    await film_score(score_ask(golden_explainer()), score_deps(objects, maker))
    assert len(maker.calls) == 4


async def test_a_hidden_simulation_is_no_scene_and_an_explainer_with_nothing_else_is_refused() -> None:
    maker = MemoryMaker()
    score = await film_score(
        score_ask(with_hidden_simulation(alone=False)), score_deps(MemoryObjects(), maker)
    )
    assert [cue.block_id for cue in score.cues] == ["s1.b1", "s2.b1"]
    with pytest.raises(ScoreRefused) as refused:
        await film_score(score_ask(with_hidden_simulation(alone=True)), score_deps(MemoryObjects(), maker))
    assert refused.value.reason == "nothing"


def test_audio_is_checked_for_its_type_and_its_length_within_a_second() -> None:
    assert checked_score_audio(made_call(mp3(2.9)), 2.0) == mp3(2.9)
    for refused in (made_call(mp3(3.1)), made_call(mp3(2.0), "audio/wav"), made_call(b"")):
        with pytest.raises(InvalidInput):
            checked_score_audio(refused, 2.0)
