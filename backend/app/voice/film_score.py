from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.core.clock import INDIA_TZ
from app.core.errors import InvalidInput, Refused
from app.providers.catalogue import AiTask
from app.providers.elevenlabs import audio_seconds
from app.providers.media_router import MediaAsk, MediaCall
from app.providers.router import Principal
from app.research.explainer import Explainer
from app.schemas.film import (
    FILM_SCORE_SCHEMA_VERSION,
    SCORE_LABEL,
    FilmScore,
    ScoreCue,
    ScoreLabel,
    ScoreMusic,
)
from app.services.naming import (
    content_disposition,
    score_cue_file_name,
    score_key,
    score_manifest_key,
    score_music_file_name,
)

from .film_plan import ScorePlan, score_plan
from .film_scenes import SceneCue, scene_cues
from .narration_cache import AUDIO_TYPE
from .object_lease import LEASE_LEAF, LeasedObjects, held_lease, release_lease, take_lease
from .score_cache import (
    UNNAMED_LEAF,
    ScoreClip,
    ScoredCue,
    ScoredMusic,
    ScoreManifest,
    score_cache_id,
    store_clip,
    store_score,
    stored_clip,
    stored_score,
)
from .score_prompts import SCORE_MUSIC_PROMPT

__all__ = [
    "MAKING_MESSAGE",
    "NOTHING_MESSAGE",
    "SCORE_CONCURRENCY",
    "SCORE_LEASE_SECONDS",
    "SCORE_LENGTH_TOLERANCE_SECONDS",
    "SCORE_LINK_SECONDS",
    "ScoreAsk",
    "ScoreBeingMade",
    "ScoreDeps",
    "ScoreMaker",
    "ScoreRefused",
    "checked_score_audio",
    "current_score",
    "film_score",
    "made_score",
    "planned_score",
    "score_in_making",
]

logger = logging.getLogger(__name__)

SCORE_LINK_SECONDS = 3600
SCORE_CONCURRENCY = 3
SCORE_LENGTH_TOLERANCE_SECONDS = 1.0
SCORE_LEASE_SECONDS = 600
NOTHING_MESSAGE = "There is nothing to play here."
MAKING_MESSAGE = "The music for this film is being made."


class ScoreRefused(Refused):
    pass


class ScoreBeingMade(Refused):
    pass


class ScoreMaker(Protocol):
    async def first_model(self, task: AiTask) -> str | None: ...

    async def generate(self, ask: MediaAsk) -> MediaCall: ...


@dataclass(frozen=True)
class ScoreDeps:
    objects: LeasedObjects
    maker: ScoreMaker
    clock: Callable[[], datetime]
    voice_id: str | None = None


@dataclass(frozen=True)
class ScoreAsk:
    principal: Principal
    explainer: Explainer


@dataclass(frozen=True)
class _Clip:
    task: AiTask
    prompt: str
    seconds: float
    scene: int | None

    @property
    def identity(self) -> tuple[str, str, float]:
        return self.task.value, self.prompt, self.seconds


async def film_score(ask: ScoreAsk, deps: ScoreDeps) -> FilmScore:
    plan = await planned_score(ask, deps)
    return await current_score(ask, deps, plan) or await made_score(ask, deps, plan)


async def planned_score(ask: ScoreAsk, deps: ScoreDeps) -> ScorePlan:
    plan = await score_plan(ask.explainer, deps.objects, deps.voice_id)
    if not plan.scenes:
        raise ScoreRefused("nothing", NOTHING_MESSAGE)
    return plan


async def current_score(ask: ScoreAsk, deps: ScoreDeps, plan: ScorePlan) -> FilmScore | None:
    explainer = ask.explainer
    manifest = await stored_score(deps.objects, explainer.answer_id, explainer.understood.language)
    return _served(manifest, deps) if manifest is not None and plan.matches(manifest) else None


async def score_in_making(ask: ScoreAsk, deps: ScoreDeps) -> bool:
    held = await held_lease(deps.objects, _lease_key(ask))
    return held is not None and deps.clock() < held.lapses_at(SCORE_LEASE_SECONDS)


async def made_score(ask: ScoreAsk, deps: ScoreDeps, plan: ScorePlan) -> FilmScore:
    key = _lease_key(ask)
    tried = await take_lease(deps.objects, key, plan.digest, now=deps.clock(), seconds=SCORE_LEASE_SECONDS)
    if not tried.ours:
        raise ScoreBeingMade("making", MAKING_MESSAGE)
    try:
        manifest = await _made_score(ask, deps, plan)
    finally:
        await release_lease(deps.objects, key)
    return _served(manifest, deps)


def _lease_key(ask: ScoreAsk) -> str:
    return score_manifest_key(ask.explainer.answer_id, ask.explainer.understood.language, leaf=LEASE_LEAF)


def checked_score_audio(call: MediaCall, seconds: float) -> bytes:
    audio = call.result.data
    if call.result.mime != AUDIO_TYPE or not audio:
        raise InvalidInput(f"{call.model} answered {call.result.mime} instead of MP3 audio")
    heard = audio_seconds(len(audio))
    if abs(heard - seconds) > SCORE_LENGTH_TOLERANCE_SECONDS:
        raise InvalidInput(f"{call.model} made {heard:.1f} s of audio where {seconds:g} s was asked")
    return audio


async def _made_score(ask: ScoreAsk, deps: ScoreDeps, plan: ScorePlan) -> ScoreManifest:
    models = {task: await deps.maker.first_model(task) for task in (AiTask.MUSIC, AiTask.SOUND_EFFECT)}
    bed = _Clip(AiTask.MUSIC, SCORE_MUSIC_PROMPT, plan.bed, None)
    cued = scene_cues(plan.scenes) if models[AiTask.SOUND_EFFECT] else []
    if not cued:
        logger.info("film score of answer %s has no sound-effect cue", ask.explainer.answer_id)
    planned = [bed, *(_Clip(AiTask.SOUND_EFFECT, c.cue.prompt, c.cue.seconds, c.scene.number) for c in cued)]
    music, *cue_clips = await _made_clips(_Making(ask, deps, models), planned)
    manifest = ScoreManifest(
        schema_version=1,
        answer_id=ask.explainer.answer_id,
        language=ask.explainer.understood.language,
        scenes_hash=plan.digest,
        music=ScoredMusic(key=music.key, duration_seconds=music.duration_seconds, model=music.model),
        cues=[_scored_cue(cue, clip) for cue, clip in zip(cued, cue_clips, strict=True)],
        created_at=deps.clock(),
    )
    await store_score(deps.objects, manifest)
    return manifest


async def _made_clips(making: _Making, planned: list[_Clip]) -> list[ScoreClip]:
    unique: dict[tuple[str, str, float], _Clip] = {}
    for clip in planned:
        unique.setdefault(clip.identity, clip)
    made = await asyncio.gather(*(making.clip(clip) for clip in unique.values()), return_exceptions=True)
    failure = next((outcome for outcome in made if isinstance(outcome, BaseException)), None)
    if failure is not None:
        raise failure
    clips = dict(zip(unique, made, strict=True))
    return [clips[clip.identity] for clip in planned]


class _Making:
    def __init__(self, ask: ScoreAsk, deps: ScoreDeps, models: dict[AiTask, str | None]) -> None:
        self.ask = ask
        self.deps = deps
        self.models = models
        self._gate = asyncio.Semaphore(SCORE_CONCURRENCY)

    async def clip(self, clip: _Clip) -> ScoreClip:
        model = self.models[clip.task]
        if model is not None:
            cache_id = score_cache_id(clip.task.value, model, clip.prompt, clip.seconds)
            found = await stored_clip(self.deps.objects, cache_id)
            if found is not None:
                await self.deps.objects.delete(score_key(cache_id, UNNAMED_LEAF))
                return found
        async with self._gate:
            call = await self.deps.maker.generate(
                MediaAsk(
                    task=clip.task,
                    prompt=clip.prompt,
                    output={"seconds": f"{clip.seconds:g}"},
                    units=clip.seconds,
                    principal=self.ask.principal,
                )
            )
        return await self._kept(clip, call)

    async def _kept(self, clip: _Clip, call: MediaCall) -> ScoreClip:
        audio = checked_score_audio(call, clip.seconds)
        cache_id = score_cache_id(clip.task.value, call.model, clip.prompt, clip.seconds)
        now = self.deps.clock()
        leaf = score_music_file_name(now) if clip.scene is None else score_cue_file_name(now, clip.scene)
        key = score_key(cache_id, leaf)
        await self.deps.objects.put(key, audio, content_type=AUDIO_TYPE)
        made = ScoreClip(
            schema_version=1,
            cache_id=cache_id,
            task=clip.task.value,
            model=call.model,
            duration_seconds=clip.seconds,
            key=key,
        )
        await store_clip(self.deps.objects, made)
        return made


def _scored_cue(cue: SceneCue, clip: ScoreClip) -> ScoredCue:
    return ScoredCue(
        block_id=cue.scene.block_id,
        offset_seconds=cue.cue.offset_seconds,
        key=clip.key,
        duration_seconds=clip.duration_seconds,
        model=clip.model,
    )


class _Links:
    def __init__(self, deps: ScoreDeps) -> None:
        self.deps = deps
        self.now = deps.clock()
        self.expiries: list[datetime] = []

    def __call__(self, key: str) -> str:
        signed = self.deps.objects.presigned_get(
            key,
            disposition=content_disposition(key.rsplit("/", 1)[-1], inline=True),
            seconds=SCORE_LINK_SECONDS,
            now=self.now,
        )
        self.expiries.append(signed.expires_at)
        return signed.url


def _served(manifest: ScoreManifest, deps: ScoreDeps) -> FilmScore:
    link = _Links(deps)
    music = manifest.music
    played = (
        None
        if music is None
        else ScoreMusic(audio_url=link(music.key), duration_seconds=music.duration_seconds, model=music.model)
    )
    cues = [
        ScoreCue(
            block_id=cue.block_id,
            offset_seconds=cue.offset_seconds,
            audio_url=link(cue.key),
            duration_seconds=cue.duration_seconds,
            model=cue.model,
        )
        for cue in manifest.cues
    ]
    made = [*([music.model] if music else []), *(cue.model for cue in manifest.cues)]
    label = ScoreLabel(
        text=SCORE_LABEL,
        models=list(dict.fromkeys(made)),
        generated_on=manifest.created_at.astimezone(INDIA_TZ).date(),
    )
    return FilmScore(
        schema_version=FILM_SCORE_SCHEMA_VERSION,
        answer_id=manifest.answer_id,
        language=manifest.language,
        music=played,
        cues=cues,
        label=label,
        url_expires_at=min(link.expiries),
    )
