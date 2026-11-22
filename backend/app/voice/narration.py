from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Iterator
from dataclasses import dataclass

from app.core.errors import InvalidInput
from app.providers.elevenlabs import NARRATION_MAX_CHARACTERS, NARRATION_MODEL, TimedSpeech, audio_seconds
from app.research.blocks import BlockBase
from app.research.explainer import Explainer, explainer_blocks
from app.research.knowledge_pieces import piece_content_hash
from app.research.vocabulary import CANONICAL_LANGUAGE, HYPOTHESIS_LEVEL
from app.schemas.listen import ListenWord

__all__ = [
    "CHARACTERS_PER_MINUTE",
    "NARRATION_VERSION",
    "PART_CHARACTERS",
    "SENTENCE_GAP",
    "NarrationPart",
    "SpokenBlock",
    "SpokenSentence",
    "estimated_seconds",
    "narration_cache_id",
    "narration_parts",
    "part_duration",
    "part_words",
    "spoken_blocks",
]

NARRATION_VERSION = 2
PART_CHARACTERS = 2_000
CHARACTERS_PER_MINUTE = 1_000
SENTENCE_GAP = " "
TIME_PLACES = 3
WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class SpokenSentence:
    sentence_id: str
    text: str
    language: str


@dataclass(frozen=True)
class SpokenBlock:
    block_id: str
    content_hash: str
    sentences: tuple[SpokenSentence, ...]


@dataclass(frozen=True)
class NarrationPart:
    language: str
    sentences: tuple[SpokenSentence, ...]

    @property
    def text(self) -> str:
        return SENTENCE_GAP.join(sentence.text for sentence in self.sentences)


def spoken_blocks(explainer: Explainer, section_id: str | None) -> list[SpokenBlock]:
    language = explainer.understood.language
    spoken = (_spoken(block, language) for block in _read_blocks(explainer, section_id))
    return [block for block in spoken if block is not None]


def narration_parts(block: SpokenBlock, *, limit: int = PART_CHARACTERS) -> list[NarrationPart]:
    if not 0 < limit <= NARRATION_MAX_CHARACTERS:
        raise InvalidInput(f"A narration part holds 1 to {NARRATION_MAX_CHARACTERS} characters")
    runs: list[list[SpokenSentence]] = []
    for sentence in block.sentences:
        if len(sentence.text) > limit:
            raise InvalidInput(f"Sentence {sentence.sentence_id} is longer than one narration part")
        if runs and _joins(runs[-1], sentence, limit):
            runs[-1].append(sentence)
        else:
            runs.append([sentence])
    return [NarrationPart(language=run[0].language, sentences=tuple(run)) for run in runs]


def part_words(part: NarrationPart, speech: TimedSpeech) -> list[ListenWord]:
    if len(speech.starts) != len(part.text) or len(speech.ends) != len(part.text):
        raise InvalidInput("A narration's timings cover exactly the text of its part")
    words: list[ListenWord] = []
    offset, previous = 0, 0.0
    for sentence in part.sentences:
        for match in WORD.finditer(sentence.text):
            first, last = offset + match.start(), offset + match.end() - 1
            start = max(previous, round(speech.starts[first], TIME_PLACES))
            end = max(start, round(speech.ends[last], TIME_PLACES))
            words.append(
                ListenWord(sentence_id=sentence.sentence_id, text=match.group(), start=start, end=end)
            )
            previous = start
        offset += len(sentence.text) + len(SENTENCE_GAP)
    return words


def part_duration(speech: TimedSpeech) -> float:
    return round(max(audio_seconds(len(speech.audio)), *speech.ends), TIME_PLACES)


def narration_cache_id(content_hash: str, *, language: str, voice_id: str) -> str:
    parts = (
        "kalavigyan-narration",
        str(NARRATION_VERSION),
        NARRATION_MODEL,
        voice_id,
        language,
        content_hash,
    )
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def estimated_seconds(characters: int) -> int:
    return math.ceil(characters * 60 / CHARACTERS_PER_MINUTE)


def _read_blocks(explainer: Explainer, section_id: str | None) -> Iterator[BlockBase]:
    if section_id is None:
        yield from explainer_blocks(explainer)
        return
    for section in explainer.sections:
        if section.id == section_id:
            yield from section.blocks


def _spoken(block: BlockBase, language: str) -> SpokenBlock | None:
    sentences = tuple(
        SpokenSentence(
            sentence_id=sentence.id,
            text=sentence.text,
            language=language if sentence.translated else CANONICAL_LANGUAGE,
        )
        for sentence in block.cited_sentences()
        if sentence.level != HYPOTHESIS_LEVEL
    )
    if not sentences:
        return None
    return SpokenBlock(block_id=block.id, content_hash=piece_content_hash(block), sentences=sentences)


def _joins(run: list[SpokenSentence], sentence: SpokenSentence, limit: int) -> bool:
    if run[0].language != sentence.language:
        return False
    length = sum(len(spoken.text) for spoken in run) + len(SENTENCE_GAP) * len(run)
    return length + len(sentence.text) <= limit
