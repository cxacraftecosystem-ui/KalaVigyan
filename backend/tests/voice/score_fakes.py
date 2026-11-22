from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.core.errors import SPEND_REFUSAL_KIND
from app.providers.base import MediaResult
from app.providers.catalogue import AiTask
from app.providers.media_router import MediaAsk, MediaCall
from app.providers.router import Principal, RouterError
from app.research.explainer import Explainer
from app.voice.film_score import ScoreAsk, ScoreDeps, ScoreMaker

from ..media.audio_routes import mp3
from .listen_fakes import LEARNER, MemoryObjects

__all__ = ["MADE_AT", "SERVED_AT", "MemoryMaker", "score_ask", "score_deps"]

MADE_AT = datetime(2026, 11, 18, 5, 0, tzinfo=UTC)
SERVED_AT = datetime(2026, 11, 18, 10, 30, tzinfo=UTC)
MODELS: dict[AiTask, str | None] = {
    AiTask.MUSIC: "music_v2_5",
    AiTask.SOUND_EFFECT: "eleven_text_to_sound_v3",
}


@dataclass
class MemoryMaker:
    models: dict[AiTask, str | None] = field(default_factory=lambda: dict(MODELS))
    calls: list[MediaAsk] = field(default_factory=list)
    failing: AiTask | None = None
    refusing: bool = False
    heard_seconds: float | None = None

    async def first_model(self, task: AiTask) -> str | None:
        return self.models.get(task)

    async def generate(self, ask: MediaAsk) -> MediaCall:
        self.calls.append(ask)
        if self.refusing:
            raise RouterError(SPEND_REFUSAL_KIND, "The monthly budget for images and video has been reached.")
        model = self.models.get(ask.task)
        if model is None or self.failing == ask.task:
            raise RouterError("exhausted", f"Every route for {ask.task.value} failed")
        audio = mp3(self.heard_seconds if self.heard_seconds is not None else ask.units)
        result = MediaResult(audio, "audio/mpeg", None, None, None, None, model)
        return MediaCall(result, "ELEVENLABS", model, uuid.uuid4(), Decimal("0.01"))

    def tasks(self) -> list[str]:
        return [call.task.value for call in self.calls]


def score_ask(explainer: Explainer, role: str = "STUDENT") -> ScoreAsk:
    return ScoreAsk(principal=Principal(user_id=LEARNER, role=role), explainer=explainer)


def score_deps(
    objects: MemoryObjects, maker: ScoreMaker, at: datetime = MADE_AT, voice_id: str | None = None
) -> ScoreDeps:
    return ScoreDeps(objects=objects, maker=maker, clock=lambda: at, voice_id=voice_id)
