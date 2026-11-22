import asyncio
import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import boto3
import httpx
import pytest
from botocore.config import Config
from botocore.stub import Stubber

from app.core.errors import ExternalFailure, InvalidInput
from app.data.export_assets import (
    APA_STYLE_ID,
    APA_STYLE_UPDATED,
    EXPORTS_DIR,
    SCRIPT_FONT_FAMILIES,
    apa_style_path,
    font_files,
)
from app.research.export_links import EXPORT_LINK_SECONDS
from app.services.export_pictures import PICTURE_MAX_SIDE, export_pictures, normalised
from app.services.export_store import (
    EXPORT_BUILDS_AT_ONCE,
    BuiltExport,
    ExportFile,
    export_digest,
    stored_export_link,
)
from app.services.naming import explainer_file_name, export_key, lesson_file_name
from app.services.object_store import ObjectStore
from app.sources.images.picture_files import picture_files

from ..contracts.golden import golden_json
from .lesson_fixtures import FakeBucket, golden_pack, picture_bytes

NOW = datetime(2026, 11, 18, 10, 0, tzinfo=UTC)
OWNER = uuid.UUID(int=7)
UNREAD = uuid.UUID(int=9)
VENDORED_SHA256 = {
    "reveal/reveal.js": "aa1bbbf2617b23a623b23612cb3c5bdb63de512e652bf20fcfa832b045d37844",
    "reveal/reveal.css": "615ee850cbbb98a0f688b60ed37b21819a3f54c9f3e6f20e33e63693ab74a0c0",
    "reveal/LICENSE.txt": "b2883e4b610bfa1b4d8fff84c4d4b825cc7d553cbd9fec4777c04068a2859dc0",
    "csl/apa.csl": "46f7fab4a72e2e6f1aa8cd4981387d8da7ec51d604c2a7134902c999d97d357e",
    "fonts/NotoSans-Regular.ttf": "f3961a9cde016d41a4879aecda1474d3a36d6bf54fa0e4643de029cc2248b0e8",
    "fonts/NotoSansDevanagari-Regular.ttf": "9c7d935139ea6a1e6ad9dbac4f6d27ece1e04bca8123c8888d00a0f9df4724cd",
    "fonts/NotoNaskhArabic-Regular.ttf": "c34fdbd98af4dbc45ca192a23d2eeb77032add83086f5fe32957d23b3f36b221",
    "fonts/OFL.txt": "f2095b08bed08b23a6fe26112fcd679a2bee3f002eef077eb05d215ed1051bd8",
}


async def test_a_file_is_built_once_and_reused_through_a_short_lived_link() -> None:
    bucket = FakeBucket()
    builds: list[int] = []

    async def build() -> BuiltExport:
        builds.append(1)
        return BuiltExport(b"%PDF-1.7")

    export = ExportFile(
        owner_id=OWNER,
        fmt="pdf",
        file_name="KalaVigyan_Lesson_2026-11-18_Mordants_Lesson.pdf",
        made_from={"pack": 1},
    )
    first = await stored_export_link(bucket, export, build, now=NOW, builds=one_at_a_time())
    second = await stored_export_link(bucket, export, build, now=NOW, builds=one_at_a_time())
    assert builds == [1] and first == second
    key = f"exports/{OWNER}/{export_digest('pdf', {'pack': 1})}/{export.file_name}"
    assert list(bucket.stored) == [key] and bucket.stored[key][1] == "application/pdf"
    assert first.expires_at == NOW + timedelta(seconds=EXPORT_LINK_SECONDS) and EXPORT_LINK_SECONDS <= 300
    assert bucket.signed[0][1].startswith('attachment; filename="KalaVigyan_Lesson_')


async def test_a_changed_explainer_is_filed_under_a_new_key() -> None:
    bucket = FakeBucket()

    async def build() -> BuiltExport:
        return BuiltExport(b"x")

    for made_from in ({"explainer": "v1"}, {"explainer": "v1 changed"}):
        export = ExportFile(owner_id=OWNER, fmt="pdf", file_name="a.pdf", made_from=made_from)
        await stored_export_link(bucket, export, build, now=NOW, builds=one_at_a_time())
    assert len(bucket.stored) == 2


def one_at_a_time() -> asyncio.Semaphore:
    return asyncio.Semaphore(1)


async def test_a_file_made_while_a_picture_was_unread_is_never_reused() -> None:
    bucket = FakeBucket()
    builds: list[frozenset[uuid.UUID]] = []
    unread = [frozenset({UNREAD}), frozenset({UNREAD}), frozenset()]

    async def build() -> BuiltExport:
        builds.append(unread[len(builds)])
        return BuiltExport(b"%PDF-1.7", builds[-1])

    export = ExportFile(owner_id=OWNER, fmt="pdf", file_name="a.pdf", made_from={"pack": 1})
    for _ in range(4):
        await stored_export_link(bucket, export, build, now=NOW, builds=one_at_a_time())
    partial = hashlib.sha256(
        b'["kalavigyan-export/v1","pdf",{"madeFrom":{"pack":1},'
        b'"unread":["00000000-0000-0000-0000-000000000009"]}]'
    ).hexdigest()
    complete = hashlib.sha256(b'["kalavigyan-export/v1","pdf",{"pack":1}]').hexdigest()
    assert len(builds) == 3
    assert sorted(bucket.stored) == sorted(
        [f"exports/{OWNER}/{partial}/a.pdf", f"exports/{OWNER}/{complete}/a.pdf"]
    )
    assert [signed[0] for signed in bucket.signed] == [
        f"exports/{OWNER}/{partial}/a.pdf",
        f"exports/{OWNER}/{partial}/a.pdf",
        f"exports/{OWNER}/{complete}/a.pdf",
        f"exports/{OWNER}/{complete}/a.pdf",
    ]


async def test_no_more_builds_run_at_once_than_the_limit() -> None:
    bucket, release = FakeBucket(), asyncio.Event()
    started: list[int] = []

    async def build() -> BuiltExport:
        started.append(1)
        await release.wait()
        return BuiltExport(b"x")

    limit = asyncio.Semaphore(EXPORT_BUILDS_AT_ONCE)
    exports = [
        ExportFile(owner_id=OWNER, fmt="pdf", file_name="a.pdf", made_from={"pack": n})
        for n in range(EXPORT_BUILDS_AT_ONCE + 1)
    ]
    running = [
        asyncio.create_task(stored_export_link(bucket, one, build, now=NOW, builds=limit)) for one in exports
    ]
    for _ in range(5):
        await asyncio.sleep(0)
    assert len(started) == EXPORT_BUILDS_AT_ONCE == 2
    release.set()
    await asyncio.gather(*running)
    assert len(started) == 3 and len(bucket.stored) == 3


async def test_a_second_first_request_waits_and_reuses_the_first_build() -> None:
    bucket = FakeBucket()
    builds: list[int] = []

    async def build() -> BuiltExport:
        builds.append(1)
        await asyncio.sleep(0)
        return BuiltExport(b"x")

    export = ExportFile(owner_id=OWNER, fmt="pdf", file_name="a.pdf", made_from={"pack": 1})
    limit = one_at_a_time()
    await asyncio.gather(
        stored_export_link(bucket, export, build, now=NOW, builds=limit),
        stored_export_link(bucket, export, build, now=NOW, builds=limit),
    )
    assert builds == [1] and len(bucket.stored) == 1


def test_the_digest_is_the_sha256_of_the_canonical_inputs() -> None:
    expected = hashlib.sha256(b'["kalavigyan-export/v1","pdf",{"a":1,"b":"\xc3\xa0"}]').hexdigest()
    assert export_digest("pdf", {"b": "à", "a": 1}) == expected


@pytest.mark.parametrize(
    "row", golden_json("naming-golden.json")["lessonFiles"], ids=lambda row: row["fileName"]
)
def test_every_golden_lesson_file_name_is_reproduced(row: dict) -> None:
    made_at = datetime.fromisoformat(row["madeAt"])
    assert (
        lesson_file_name(made_at=made_at, craft=row["craft"], title=row["title"], fmt=row["format"])
        == row["fileName"]
    )


@pytest.mark.parametrize(
    "row", golden_json("naming-golden.json")["explainerFiles"], ids=lambda row: row["fileName"]
)
def test_every_golden_explainer_file_name_is_reproduced(row: dict) -> None:
    name = explainer_file_name(
        made_at=datetime.fromisoformat(row["madeAt"]),
        craft=row["craft"],
        question=row["question"],
        version=row["version"],
        what=row["what"],
        ext=row["ext"],
    )
    assert name == row["fileName"]


@pytest.mark.parametrize(
    "row", golden_json("naming-golden.json")["exportKeys"], ids=lambda row: row["key"][:40]
)
def test_every_golden_export_key_is_reproduced(row: dict) -> None:
    assert export_key(uuid.UUID(row["ownerId"]), row["sha256"], row["fileName"]) == row["key"]
    with pytest.raises(InvalidInput):
        export_key(uuid.UUID(row["ownerId"]), "not-a-digest", row["fileName"])


@pytest.mark.parametrize(("relative", "digest"), sorted(VENDORED_SHA256.items()))
def test_the_vendored_export_files_are_the_recorded_ones(relative: str, digest: str) -> None:
    assert hashlib.sha256((EXPORTS_DIR / relative).read_bytes()).hexdigest() == digest


def test_the_apa_style_is_the_pinned_csl_style_with_its_licence_and_no_comments() -> None:
    text = apa_style_path().read_text(encoding="utf-8")
    assert f"<id>{APA_STYLE_ID}</id>" in text and f"<updated>{APA_STYLE_UPDATED}</updated>" in text
    assert "<!--" not in text and 'license="http://creativecommons.org/licenses/by-sa/3.0/"' in text


def test_every_answer_script_has_a_regular_and_a_bold_font() -> None:
    for script in SCRIPT_FONT_FAMILIES:
        files = font_files(script)
        assert files.regular.is_file() and files.bold.is_file()


def test_a_picture_is_flattened_to_a_bounded_jpeg() -> None:
    picture = normalised(picture_bytes("PNG", (3200, 1600)))
    assert picture is not None and (picture.width, picture.height) == (PICTURE_MAX_SIDE, 800)
    assert picture.data[:3] == b"\xff\xd8\xff"
    assert normalised(b"not an image") is None


async def test_pictures_are_read_only_from_the_open_image_hosts() -> None:
    asked: list[str] = []

    def answer(request: httpx.Request) -> httpx.Response:
        asked.append(str(request.url))
        if request.url.host == "upload.wikimedia.org":
            return httpx.Response(200, content=picture_bytes(), headers={"content-type": "image/png"})
        return httpx.Response(200, content=b"<html>", headers={"content-type": "text/html"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(answer)) as client:
        files = picture_files(client)
        assert (await files.picture("https://upload.wikimedia.org/a.png"))[:4] == b"\x89PNG"
        with pytest.raises(InvalidInput):
            await files.picture("https://evil.example/a.png")
        with pytest.raises(ExternalFailure):
            await files.picture("https://api.openverse.org/v1/images/x/thumb/")
    assert asked == ["https://upload.wikimedia.org/a.png", "https://api.openverse.org/v1/images/x/thumb/"]


async def test_a_picture_that_cannot_be_read_is_left_out_of_the_pack_s_files() -> None:
    pack = golden_pack()
    media = [slide.image for slide in pack.slides if slide.image is not None]

    class Refusing:
        async def picture(self, url: str) -> bytes:
            raise ExternalFailure("picture_files answered 404", service="picture_files")

    pictures = await export_pictures(media, Refusing())
    assert pictures.found == {} and pictures.unread == frozenset(one.id for one in media)


async def test_the_bucket_answers_whether_an_export_is_already_filed() -> None:
    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="test-only-access-key",
        aws_secret_access_key="test-only-secret-not-real",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
    store = ObjectStore(bucket="kalavigyan-media-example", region="ap-south-1", client=client)
    key = f"exports/{OWNER}/{'a' * 64}/a.pdf"
    stub = Stubber(client)
    stub.add_response("head_object", {}, {"Bucket": "kalavigyan-media-example", "Key": key})
    stub.add_client_error("head_object", service_error_code="404", http_status_code=404)
    stub.add_client_error("head_object", service_error_code="403", http_status_code=403)
    with stub:
        assert await store.exists(key) is True
        assert await store.exists(key) is False
        with pytest.raises(ExternalFailure):
            await store.exists(key)
