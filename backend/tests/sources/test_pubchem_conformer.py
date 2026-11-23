import httpx
import pytest

from app.core.errors import ExternalFailure, InvalidInput
from app.sources.http import RatePolicy
from app.sources.reference.pubchem import CONFORMER_MAX_BYTES, PUBCHEM_RATE, PubChemAdapter

from .recorded import FakeClock, Recorder, Reply, fixed_clock, recorded, source_http

CONFORMER_PATH = "pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/6293/record/SDF"
RECORDED = recorded("pubchem_conformer.sdf")
PUBCHEM_REQUESTS_PER_SECOND = 5


def pubchem(routes: dict, *, policy: RatePolicy | None = None, clock: FakeClock | None = None):
    recorder = Recorder(routes)
    http = source_http(recorder, "pubchem", policy=policy, clock=clock)
    return PubChemAdapter(http, clock=fixed_clock()), recorder


def answering(body: bytes) -> PubChemAdapter:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body, headers={"content-type": "chemical/x-mdl-sdfile"})

    recorder = Recorder({})
    http = source_http(recorder, "pubchem")
    http.client = httpx.AsyncClient(transport=httpx.MockTransport(handle))
    return PubChemAdapter(http, clock=fixed_clock())


async def test_the_recorded_3d_conformer_is_answered_as_pubchem_sent_it() -> None:
    adapter, recorder = pubchem({CONFORMER_PATH: Reply("pubchem_conformer.sdf")})
    sdf = await adapter.conformer(6293)
    assert sdf == RECORDED.decode("ascii")
    assert sdf.split("\n")[0] == "6293" and "V2000" in sdf.split("\n")[3]
    (request,) = recorder.requests
    assert (request.url.path, dict(request.url.params)) == (
        "/rest/pug/compound/cid/6293/record/SDF",
        {"record_type": "3d"},
    )


async def test_a_compound_without_a_3d_conformer_is_none() -> None:
    adapter, _ = pubchem({CONFORMER_PATH: Reply("pubchem_conformer_missing.txt", status=404)})
    assert await adapter.conformer(6293) is None


async def test_the_same_conformer_is_asked_once_within_the_cache_window() -> None:
    adapter, recorder = pubchem({CONFORMER_PATH: Reply("pubchem_conformer.sdf")})
    assert await adapter.conformer(6293) == await adapter.conformer(6293)
    assert len(recorder.requests) == 1


async def test_conformer_requests_keep_to_pubchem_s_five_a_second() -> None:
    assert 1 / PUBCHEM_RATE.min_interval < PUBCHEM_REQUESTS_PER_SECOND
    clock = FakeClock()
    routes = {
        CONFORMER_PATH: Reply("pubchem_conformer.sdf"),
        CONFORMER_PATH.replace("6293", "6294"): Reply("pubchem_conformer_missing.txt", status=404),
    }
    adapter, _ = pubchem(routes, policy=PUBCHEM_RATE, clock=clock)
    await adapter.conformer(6293)
    await adapter.conformer(6294)
    assert clock.slept == [PUBCHEM_RATE.min_interval]


def swapped(old: bytes, new: bytes) -> bytes:
    assert old in RECORDED
    return RECORDED.replace(old, new, 1)


@pytest.mark.parametrize(
    ("body", "problem"),
    [
        (swapped(b"6293\n", b"6294\n"), "names another record"),
        (swapped(b"10523D", b"10522D"), "not a 3D molfile"),
        (RECORDED.rstrip().removesuffix(b"$$$$"), "does not end its record"),
        (swapped(b"6293\n", "6293é\n".encode()), "not ASCII"),
        (RECORDED + b" " * CONFORMER_MAX_BYTES, "over"),
    ],
    ids=["another CID", "a 2D record", "unterminated", "not ASCII", "too large"],
)
async def test_a_body_that_is_not_this_compound_s_3d_record_fails_loudly(body: bytes, problem: str) -> None:
    with pytest.raises(ExternalFailure, match=problem):
        await answering(body).conformer(6293)


async def test_a_cid_is_a_positive_number() -> None:
    adapter, recorder = pubchem({})
    with pytest.raises(InvalidInput):
        await adapter.conformer(0)
    assert recorder.requests == []


SYNONYMS_PATH = "pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/6293/synonyms/JSON"


async def test_a_compound_s_synonyms_are_read_from_pubchem_in_its_order_up_to_the_limit() -> None:
    adapter, recorder = pubchem({SYNONYMS_PATH: Reply("pubchem_synonyms.json")})
    names = await adapter.synonyms(6293, limit=8)
    assert names == [
        "Alizarin",
        "72-48-0",
        "1,2-dihydroxyanthracene-9,10-dione",
        "1,2-Dihydroxyanthraquinone",
        "Mordant Red 11",
        "1,2-Dihydroxy-9,10-anthracenedione",
        "ALIZARINE",
        "Turkey Red",
    ]
    (request,) = recorder.requests
    assert request.url.path == "/rest/pug/compound/cid/6293/synonyms/JSON"


async def test_a_compound_pubchem_has_no_synonyms_for_has_none() -> None:
    adapter, _ = pubchem({SYNONYMS_PATH: Reply("pubchem_not_found.json", status=404)})
    assert await adapter.synonyms(6293) == []
    with pytest.raises(InvalidInput):
        await adapter.synonyms(0)
