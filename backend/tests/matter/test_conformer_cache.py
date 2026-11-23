import json
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.services.molecule_conformers import CONFORMER_LEAF, ConformerCache
from app.services.naming import molecule_key
from app.sources.reference.pubchem import PubChemAdapter

from ..sources.recorded import Recorder, Reply, fixed_clock, recorded, source_http
from ..voice.listen_fakes import MemoryObjects

CHECKED_AT = datetime(2026, 11, 17, 10, 0, tzinfo=UTC)
PUG = "pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid"
ALIZARIN_KEY = "media/molecules/6293/conformer.json"
ALIZARIN_SDF = recorded("pubchem_conformer.sdf").decode("ascii").strip()


def pubchem(routes: dict[str, Reply]) -> tuple[PubChemAdapter, Recorder]:
    recorder = Recorder(routes)
    return PubChemAdapter(source_http(recorder, "pubchem"), clock=fixed_clock()), recorder


def cache(objects: MemoryObjects, routes: dict[str, Reply]) -> tuple[ConformerCache, Recorder]:
    adapter, recorder = pubchem(routes)
    return ConformerCache(objects=objects, source=adapter, clock=lambda: CHECKED_AT), recorder


def test_a_conformer_is_filed_under_its_cid() -> None:
    assert molecule_key(6293, CONFORMER_LEAF) == ALIZARIN_KEY
    with pytest.raises(InvalidInput):
        molecule_key(0, CONFORMER_LEAF)
    with pytest.raises(InvalidInput):
        molecule_key(6293, "nested/conformer.json")


async def test_a_miss_fetches_through_the_pubchem_adapter_and_keeps_the_record() -> None:
    objects = MemoryObjects()
    first, recorder = cache(objects, {f"{PUG}/6293/record/SDF": Reply("pubchem_conformer.sdf")})
    assert await first.conformer(6293) == ALIZARIN_SDF
    assert len(recorder.requests) == 1
    body, content_type = objects.stored[ALIZARIN_KEY]
    assert content_type == "application/json"
    assert json.loads(body) == {
        "schemaVersion": 1,
        "pubchemCid": 6293,
        "sdf": ALIZARIN_SDF,
        "checkedAt": "2026-11-17T10:00:00Z",
    }


async def test_a_cache_hit_makes_no_second_call() -> None:
    objects = MemoryObjects()
    first, _ = cache(objects, {f"{PUG}/6293/record/SDF": Reply("pubchem_conformer.sdf")})
    await first.conformer(6293)
    second, recorder = cache(objects, {})
    assert await second.conformer(6293) == ALIZARIN_SDF
    assert recorder.requests == []


async def test_a_missing_conformer_is_kept_as_missing_and_not_asked_again() -> None:
    objects = MemoryObjects()
    first, _ = cache(objects, {f"{PUG}/24856/record/SDF": Reply("pubchem_conformer_missing.txt", status=404)})
    assert await first.conformer(24856) is None
    assert json.loads(objects.stored["media/molecules/24856/conformer.json"][0])["sdf"] is None
    second, recorder = cache(objects, {})
    assert await second.conformer(24856) is None
    assert recorder.requests == []


@pytest.mark.parametrize(
    "stored",
    [
        b"not json",
        json.dumps(
            {"schemaVersion": 1, "pubchemCid": 6294, "sdf": None, "checkedAt": "2026-11-17T10:00:00Z"}
        ).encode(),
    ],
    ids=["off its shape", "another compound"],
)
async def test_a_stored_record_that_is_not_this_compound_s_is_fetched_again(stored: bytes) -> None:
    objects = MemoryObjects(stored={ALIZARIN_KEY: (stored, "application/json")})
    again, recorder = cache(objects, {f"{PUG}/6293/record/SDF": Reply("pubchem_conformer.sdf")})
    assert await again.conformer(6293) == ALIZARIN_SDF
    assert len(recorder.requests) == 1
    assert json.loads(objects.stored[ALIZARIN_KEY][0])["pubchemCid"] == 6293


TODAY = datetime(2026, 11, 23, 10, 0, tzinfo=UTC)
INDIGO_KEY = "media/molecules/10215/conformer.json"
PUBCHEM_AWAY = ExternalFailure("PubChem is away", status=503, service="pubchem")


@dataclass
class AskedSource:
    sdf: str | None = None
    failure: ExternalFailure | None = None
    asked: list[int] = field(default_factory=list)

    async def conformer(self, cid: int) -> str | None:
        self.asked.append(cid)
        if self.failure is not None:
            raise self.failure
        return self.sdf


def kept(cid: int, sdf: str | None, checked_at: str) -> MemoryObjects:
    record = {"schemaVersion": 1, "pubchemCid": cid, "sdf": sdf, "checkedAt": checked_at}
    return MemoryObjects(
        stored={molecule_key(cid, CONFORMER_LEAF): (json.dumps(record).encode(), "application/json")}
    )


def today(objects: MemoryObjects, source: AskedSource) -> ConformerCache:
    return ConformerCache(objects=objects, source=source, clock=lambda: TODAY)


@pytest.mark.parametrize(
    ("checked_at", "asked"),
    [
        ("2026-07-01T10:00:00Z", [10215]),
        ("2026-08-25T09:59:59Z", [10215]),
        ("2026-08-25T10:00:00Z", []),
        ("2026-10-01T10:00:00Z", []),
    ],
    ids=["145 days", "a second over 90 days", "exactly 90 days", "53 days"],
)
async def test_a_kept_miss_is_asked_again_only_when_older_than_ninety_days(
    checked_at: str, asked: list[int]
) -> None:
    source = AskedSource(sdf=None)
    objects = kept(10215, None, checked_at)
    assert await today(objects, source).conformer(10215) is None
    assert source.asked == asked
    rewritten = "2026-11-23T10:00:00Z" if asked else checked_at
    assert json.loads(objects.stored[INDIGO_KEY][0])["checkedAt"] == rewritten


async def test_a_stale_miss_pubchem_now_draws_is_kept_as_a_conformer() -> None:
    objects = kept(6293, None, "2026-07-01T10:00:00Z")
    source = AskedSource(sdf=ALIZARIN_SDF)
    assert await today(objects, source).conformer(6293) == ALIZARIN_SDF
    assert source.asked == [6293]
    assert json.loads(objects.stored[ALIZARIN_KEY][0]) == {
        "schemaVersion": 1,
        "pubchemCid": 6293,
        "sdf": ALIZARIN_SDF,
        "checkedAt": "2026-11-23T10:00:00Z",
    }


async def test_a_kept_conformer_is_never_asked_again_however_old() -> None:
    objects = kept(6293, ALIZARIN_SDF, "2020-01-01T10:00:00Z")
    source = AskedSource(sdf=None)
    assert await today(objects, source).conformer(6293) == ALIZARIN_SDF
    assert source.asked == []


async def test_a_stale_miss_pubchem_cannot_answer_stands_and_is_asked_again_next_time(
    caplog: pytest.LogCaptureFixture,
) -> None:
    objects = kept(10215, None, "2026-07-01T10:00:00Z")
    source = AskedSource(failure=PUBCHEM_AWAY)
    cache = today(objects, source)
    with caplog.at_level(logging.WARNING, logger="app.services.molecule_conformers"):
        assert await cache.conformer(10215) is None
        assert await cache.conformer(10215) is None
    assert source.asked == [10215, 10215]
    assert json.loads(objects.stored[INDIGO_KEY][0])["checkedAt"] == "2026-07-01T10:00:00Z"
    assert "the kept miss of CID 10215 stands" in caplog.text


async def test_pubchem_failing_on_a_cid_never_asked_still_fails() -> None:
    source = AskedSource(failure=PUBCHEM_AWAY)
    with pytest.raises(ExternalFailure):
        await today(MemoryObjects(), source).conformer(10215)
