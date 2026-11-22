from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import quote

from app.core.clock import INDIA_TZ
from app.core.errors import InvalidInput
from app.data.craft_text import to_latin

__all__ = [
    "FILE_MAX",
    "PORTAL",
    "SUBJECT_MAX",
    "MediaName",
    "PlaceParts",
    "artisan_audio_file_name",
    "artisan_audio_key",
    "content_disposition",
    "explainer_file_name",
    "export_key",
    "field",
    "field_voice_file_name",
    "field_voice_key",
    "file_name",
    "generated_media_file_name",
    "lesson_file_name",
    "media_key",
    "molecule_key",
    "narration_file_name",
    "narration_key",
    "page_media_key",
    "place_field",
    "river_topology_file_name",
    "river_topology_key",
    "score_cue_file_name",
    "score_key",
    "score_manifest_key",
    "score_music_file_name",
    "voice_reply_key",
]

PORTAL = "KalaVigyan"
FILE_MAX = 150
SUBJECT_MAX = 40
MEDIA_PREFIX = "media"
EXPORTS_PREFIX = "exports"
NARRATION_FOLDER = "narration"
MOLECULE_FOLDER = "molecules"
RIVER_FOLDER = "rivers"
SCORE_FOLDER = "score"
FIELD_VOICE_FOLDER = "field-voices"
PAGE_MEDIA_FOLDER = "craft"
VOICE_REPLY_FOLDER = "voice-replies"
VOICE_REPLY_LEAF = "reply.mp3"
FIELD_VOICE_EXTENSIONS = ("jpg", "png")
SCORE_MANIFEST_LEAF = "score.json"
RIVER_TOPOLOGY_SUBJECT = "HydroRIVERS-1-0"
NARRATION_PARTS_MAX = 99
LESSON_FILE_WHAT = {"html": "Slides", "pptx": "Slides", "pdf": "Lesson"}
ARTISAN_AUDIO_EXTENSIONS = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav"}
ARTISAN_TURNS_MAX = 99
MEDIA_NAMES = {
    "IMAGE": ("Generated-Image", "Image", "png"),
    "VIDEO": ("Generated-Video", "Video", "mp4"),
}
RESERVED_STEMS = frozenset(
    {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
)
_ZERO_WIDTH = frozenset({"‌", "‍"})


@dataclass(frozen=True)
class PlaceParts:
    locality: str | None = None
    district: str | None = None
    state: str | None = None


@dataclass(frozen=True)
class MediaName:
    kind: str
    generated_at: datetime
    place: PlaceParts
    craft: str
    stage_name: str
    stage_ordinal: int


def field(value: str | None) -> str:
    return "-".join(_field_words(value))


def place_field(place: PlaceParts) -> str:
    return field(_place_text(place))


def file_name(
    *,
    entity: str,
    what: str,
    ext: str,
    moment: datetime,
    place: PlaceParts,
    craft: str | None,
    subject: str | None,
    sequence: str | None,
) -> str:
    local = _ist(moment)
    fixed = (PORTAL, field(entity), local.date().isoformat(), local.strftime("%H%M"))
    return _named(fixed, (field(what), sequence), ext, (_place_text(place), craft, subject))


def lesson_file_name(*, made_at: datetime, craft: str | None, title: str, fmt: str) -> str:
    what = LESSON_FILE_WHAT.get(fmt)
    if what is None:
        raise InvalidInput(f"No lesson file is written as {fmt!r}")
    fixed = (PORTAL, "Lesson", _ist(made_at).date().isoformat())
    return _named(fixed, (what, None), fmt, (None, craft, _capped_subject(title)))


def explainer_file_name(
    *, made_at: datetime, craft: str | None, question: str, version: int, what: str, ext: str
) -> str:
    if version < 1:
        raise InvalidInput(f"Explainer version {version} does not fit v<n>")
    fixed = (PORTAL, "Explainer", _ist(made_at).date().isoformat())
    return _named(fixed, (field(what), f"v{version}"), ext, (None, craft, _capped_subject(question)))


def export_key(owner_id: uuid.UUID, digest: str, leaf: str) -> str:
    if not _hex_digest(digest):
        raise InvalidInput("An export key is filed under the 64-hex SHA-256 of what it was made from")
    return f"{EXPORTS_PREFIX}/{owner_id}/{digest}/{_one_file_name(leaf, 'export')}"


def _named(
    fixed: tuple[str, ...],
    tail: tuple[str, str | None],
    ext: str,
    parts: tuple[str | None, str | None, str | None],
) -> str:
    def render(place_words: list[str], craft_words: list[str], subject_words: list[str]) -> str:
        middle = ("-".join(place_words), "-".join(craft_words), "-".join(subject_words))
        stem = "_".join(part for part in (*fixed, *middle, *tail) if part)
        return f"{_guard(stem)}.{ext}"

    place, craft, subject = parts
    return _fit(render, _field_words(place), _field_words(craft), _field_words(subject))


def generated_media_file_name(name: MediaName) -> str:
    entity, what, ext = _media_parts(name.kind)
    if not 0 <= name.stage_ordinal <= 99:
        raise InvalidInput(f"Stage ordinal {name.stage_ordinal} does not fit Step-NN")
    return file_name(
        entity=entity,
        what=what,
        ext=ext,
        moment=name.generated_at,
        place=name.place,
        craft=name.craft,
        subject=_capped_subject(name.stage_name),
        sequence=f"Step-{name.stage_ordinal:02d}",
    )


def media_key(owner_id: uuid.UUID, leaf: str, *, token: uuid.UUID | None = None) -> str:
    return f"{MEDIA_PREFIX}/{owner_id}/{(token or uuid.uuid4()).hex}/{_one_file_name(leaf, 'media')}"


def narration_file_name(generated_at: datetime, part: int) -> str:
    if not 1 <= part <= NARRATION_PARTS_MAX:
        raise InvalidInput(f"Narration part {part} does not fit Part-NN")
    return _explainer_audio_name(generated_at, "Narration", f"Part-{part:02d}")


def narration_key(cache_id: str, leaf: str) -> str:
    return _hashed_key(NARRATION_FOLDER, cache_id, leaf, "A narration key is filed under its 64-hex cache id")


def score_music_file_name(generated_at: datetime) -> str:
    return _explainer_audio_name(generated_at, "Music", None)


def score_cue_file_name(generated_at: datetime, scene: int) -> str:
    if scene < 1:
        raise InvalidInput(f"Film scene {scene} does not fit Scene-NN")
    return _explainer_audio_name(generated_at, "Sound-Effect", f"Scene-{scene:02d}")


def score_key(cache_id: str, leaf: str) -> str:
    return _hashed_key(SCORE_FOLDER, cache_id, leaf, "A score clip is filed under its 64-hex cache id")


def score_manifest_key(answer_id: uuid.UUID, language: str, *, leaf: str = SCORE_MANIFEST_LEAF) -> str:
    if not language.isascii() or not language.isalpha():
        raise InvalidInput("A score is filed under its answer and language code")
    return f"{MEDIA_PREFIX}/{SCORE_FOLDER}/{answer_id}/{language}/{leaf}"


def molecule_key(pubchem_cid: int, leaf: str) -> str:
    if pubchem_cid < 1:
        raise InvalidInput("A molecule key is filed under its PubChem CID")
    return f"{MEDIA_PREFIX}/{MOLECULE_FOLDER}/{pubchem_cid}/{_one_file_name(leaf, 'molecule')}"


def river_topology_file_name(main_riv: int) -> str:
    if main_riv < 1:
        raise InvalidInput("A river topology is filed under its outlet reach id")
    return (
        "_".join((PORTAL, "Dataset", RIVER_TOPOLOGY_SUBJECT, "River-Topology", f"Basin-{main_riv}")) + ".json"
    )


def river_topology_key(edition: str, main_riv: int, sha256: str) -> str:
    if not edition or not edition.isascii() or not edition.replace("-", "").isalnum():
        raise InvalidInput("A river topology key is filed under the dataset's ASCII edition")
    if not _hex_digest(sha256):
        raise InvalidInput("A river topology key is filed under the 64-hex SHA-256 of its content")
    folder = f"{MEDIA_PREFIX}/{RIVER_FOLDER}/{edition}/{main_riv}/{sha256}"
    return f"{folder}/{river_topology_file_name(main_riv)}"


def field_voice_file_name(*, taken_at: datetime | None, place: PlaceParts, craft: str, ext: str) -> str:
    if ext not in FIELD_VOICE_EXTENSIONS:
        raise InvalidInput(f"A field image is stored as {' or '.join(FIELD_VOICE_EXTENSIONS)}, not {ext!r}")
    fixed: tuple[str, ...] = (PORTAL, "Field-Image")
    if taken_at is not None:
        local = _ist(taken_at)
        fixed = (*fixed, local.date().isoformat(), local.strftime("%H%M"))
    where = PlaceParts(district=place.district, state=place.state)
    return _named(fixed, ("Photo", None), ext, (_place_text(where), craft, None))


def artisan_audio_file_name(
    *, recorded_at: datetime, district: str | None, craft: str, ordinal: int, mime_type: str
) -> str:
    ext = ARTISAN_AUDIO_EXTENSIONS.get(mime_type)
    if ext is None:
        raise InvalidInput(
            f"An artisan recording is one of {', '.join(ARTISAN_AUDIO_EXTENSIONS)}, not {mime_type!r}"
        )
    if not 1 <= ordinal <= ARTISAN_TURNS_MAX:
        raise InvalidInput(f"Turn {ordinal} does not fit T-NN")
    return file_name(
        entity="Artisan-Conversation",
        what="Recording",
        ext=ext,
        moment=recorded_at,
        place=PlaceParts(district=district),
        craft=craft,
        subject=None,
        sequence=f"T{ordinal:02d}",
    )


def artisan_audio_key(owner_id: uuid.UUID, leaf: str, *, token: uuid.UUID | None = None) -> str:
    return (
        f"{MEDIA_PREFIX}/{owner_id}/{(token or uuid.uuid4()).hex}/{_one_file_name(leaf, 'artisan recording')}"
    )


def voice_reply_key(session_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"{MEDIA_PREFIX}/{VOICE_REPLY_FOLDER}/{session_id}/{turn_id}/{VOICE_REPLY_LEAF}"


def field_voice_key(sha256: str, leaf: str) -> str:
    refusal = "A field image is filed under the 64-hex SHA-256 of KalaVigyan's copy"
    return _hashed_key(FIELD_VOICE_FOLDER, sha256, leaf, refusal)


def page_media_key(sha256: str, leaf: str) -> str:
    return _hashed_key(PAGE_MEDIA_FOLDER, sha256, leaf, "A page copy is filed under its 64-hex SHA-256")


def _hashed_key(folder: str, digest: str, leaf: str, refusal: str) -> str:
    if not _hex_digest(digest):
        raise InvalidInput(refusal)
    return f"{MEDIA_PREFIX}/{folder}/{digest}/{_one_file_name(leaf, folder)}"


def _hex_digest(value: str) -> bool:
    return len(value) == 64 and all(ch in "0123456789abcdef" for ch in value)


def content_disposition(leaf: str, *, inline: bool) -> str:
    if not leaf.isascii() or '"' in leaf or "\\" in leaf:
        raise InvalidInput("A download name is ASCII without quotes")
    kind = "inline" if inline else "attachment"
    return f"{kind}; filename=\"{leaf}\"; filename*=UTF-8''{quote(leaf, safe='')}"


def _explainer_audio_name(generated_at: datetime, what: str, sequence: str | None) -> str:
    return file_name(
        entity="Explainer",
        what=what,
        ext="mp3",
        moment=generated_at,
        place=PlaceParts(),
        craft=None,
        subject=None,
        sequence=sequence,
    )


def _one_file_name(leaf: str, what: str) -> str:
    if not leaf or "/" in leaf or not leaf.isascii():
        raise InvalidInput(f"A {what} key ends in one ASCII file name")
    return leaf


def _media_parts(kind: str) -> tuple[str, str, str]:
    parts = MEDIA_NAMES.get(kind)
    if parts is None:
        raise InvalidInput(f"No media name for kind {kind!r}")
    return parts


def _capped_subject(stage_name: str) -> str:
    words = _field_words(stage_name)
    while len(words) > 1 and len("-".join(words)) > SUBJECT_MAX:
        words.pop()
    if words and len(words[0]) > SUBJECT_MAX:
        words[0] = words[0][:SUBJECT_MAX]
    return " ".join(words)


def _field_words(value: str | None) -> list[str]:
    text = to_latin(value or "")
    words = ["".join(ch for ch in word if ch.isascii() and ch.isalnum()) for word in _split_words(text)]
    return [_title_case(word) for word in words if word]


def _split_words(value: str) -> list[str]:
    words: list[str] = []
    current: list[str] = []
    for ch in unicodedata.normalize("NFC", value):
        if ch in _ZERO_WIDTH or unicodedata.category(ch)[0] in ("L", "M") or unicodedata.category(ch) == "Nd":
            current.append(ch)
        elif current:
            words.append("".join(current))
            current = []
    if current:
        words.append("".join(current))
    return words


def _title_case(word: str) -> str:
    if any(ch.isdigit() for ch in word):
        return word
    if 2 <= len(word) <= 3 and word.isalpha() and word.isupper():
        return word
    return word[0].upper() + word[1:].lower()


def _place_text(place: PlaceParts) -> str | None:
    locality = (place.locality or "").strip()
    district = (place.district or "").strip()
    if locality and district and field(locality).casefold() != field(district).casefold():
        return f"{locality} {district}"
    return locality or district or (place.state or "").strip() or None


def _ist(moment: datetime) -> datetime:
    if moment.tzinfo is None:
        raise InvalidInput("A name's time must carry its time zone")
    return moment.astimezone(INDIA_TZ)


def _guard(stem: str) -> str:
    return f"{stem}-File" if stem.upper() in RESERVED_STEMS else stem


def _fit(
    render: Callable[[list[str], list[str], list[str]], str],
    place: list[str],
    craft: list[str],
    subject: list[str],
) -> str:
    def too_long() -> bool:
        return len(render(place, craft, subject)) > FILE_MAX

    for words, floor in ((subject, 1), (craft, 1), (place, 1), (subject, 0), (craft, 0), (place, 0)):
        _shorten(words, floor, too_long)
    if too_long():
        raise InvalidInput("A file name cannot fit in 150 characters")
    return render(place, craft, subject)


def _shorten(words: list[str], floor: int, too_long: Callable[[], bool]) -> None:
    while too_long() and len(words) > floor:
        words.pop()
