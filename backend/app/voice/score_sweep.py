from __future__ import annotations

import logging
import re
from collections import Counter
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Literal, Protocol

from pydantic import Field, ValidationError

from app.research.base import ContractModel
from app.services.naming import score_key
from app.services.object_store import media_bucket

from .object_lease import LeasedObjects
from .score_cache import CLIP_LEAF, UNNAMED_LEAF, ScoreManifest

__all__ = [
    "SCORE_PREFIX",
    "UNNAMED_DAYS",
    "ScoreSweep",
    "SweptObjects",
    "UnnamedMark",
    "daily_score_sweep",
    "swept_scores",
]

logger = logging.getLogger(__name__)

SCORE_PREFIX = "media/score/"
UNNAMED_DAYS = 90
MANIFEST_SUFFIX = "/score.json"
MARK_TYPE = "application/json"
CLIP_FOLDER = re.compile(r"^media/score/([0-9a-f]{64})/[^/]+$")


class SweptObjects(LeasedObjects, Protocol):
    async def keys(self, prefix: str) -> list[str]: ...


class UnnamedMark(ContractModel):
    schema_version: Literal[1]
    cache_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    unnamed_since: date


@dataclass(frozen=True)
class ScoreSweep:
    clips: int
    named: int
    marked: int
    waiting: int
    deleted: int
    unreadable: int

    def report(self) -> dict[str, Any]:
        return {"ok": True, **asdict(self)}


async def daily_score_sweep(*, today: date) -> dict[str, Any]:
    objects = media_bucket()
    if objects is None:
        return {"ok": False, "error": "S3_BUCKET is not set"}
    return (await swept_scores(objects, today=today)).report()


async def swept_scores(objects: SweptObjects, *, today: date) -> ScoreSweep:
    keys = await objects.keys(SCORE_PREFIX)
    named, unreadable = await _named_clips(objects, [key for key in keys if key.endswith(MANIFEST_SUFFIX)])
    folders = _clip_folders(keys)
    counts: Counter[str] = Counter()
    for cache_id, folder in folders.items():
        counts[await _swept(objects, cache_id, folder, named=cache_id in named, today=today)] += 1
    return ScoreSweep(
        clips=len(folders),
        named=counts["named"],
        marked=counts["marked"],
        waiting=counts["waiting"],
        deleted=counts["deleted"],
        unreadable=unreadable,
    )


async def _swept(objects: SweptObjects, cache_id: str, folder: set[str], *, named: bool, today: date) -> str:
    mark_key = score_key(cache_id, UNNAMED_LEAF)
    if named:
        if mark_key in folder:
            await objects.delete(mark_key)
        return "named"
    mark = await _stored_mark(objects, mark_key) if mark_key in folder else None
    if mark is None:
        fresh = UnnamedMark(schema_version=1, cache_id=cache_id, unnamed_since=today)
        await objects.put(
            mark_key, fresh.model_dump_json(by_alias=True).encode("utf-8"), content_type=MARK_TYPE
        )
        return "marked"
    if (
        today - mark.unnamed_since < timedelta(days=UNNAMED_DAYS)
        or await _stored_mark(objects, mark_key) is None
    ):
        return "waiting"
    clip_key = score_key(cache_id, CLIP_LEAF)
    for key in [clip_key, *sorted(folder - {clip_key, mark_key}), mark_key]:
        await objects.delete(key)
    logger.info("score clip %s was named by no score for %d days and is deleted", cache_id, UNNAMED_DAYS)
    return "deleted"


async def _named_clips(objects: SweptObjects, manifest_keys: Iterable[str]) -> tuple[set[str], int]:
    named: set[str] = set()
    unreadable = 0
    for key in manifest_keys:
        raw = await objects.get(key)
        try:
            manifest = ScoreManifest.model_validate_json(raw or b"")
        except ValidationError as error:
            logger.warning("score %s is off its stored shape and names no clip: %s", key, error)
            unreadable += 1
            continue
        clips = [*([manifest.music.key] if manifest.music else []), *(cue.key for cue in manifest.cues)]
        named |= {found.group(1) for clip in clips if (found := CLIP_FOLDER.match(clip))}
    return named, unreadable


def _clip_folders(keys: Iterable[str]) -> dict[str, set[str]]:
    folders: dict[str, set[str]] = {}
    for key in keys:
        found = CLIP_FOLDER.match(key)
        if found is not None:
            folders.setdefault(found.group(1), set()).add(key)
    return folders


async def _stored_mark(objects: SweptObjects, mark_key: str) -> UnnamedMark | None:
    raw = await objects.get(mark_key)
    if raw is None:
        return None
    try:
        return UnnamedMark.model_validate_json(raw)
    except ValidationError as error:
        logger.warning("%s is unreadable and is written again: %s", mark_key, error)
        return None
