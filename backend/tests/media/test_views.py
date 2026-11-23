import json
import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from app.media.records import AssetRecord, JobRecord
from app.media.views import job_view
from app.providers.base import MediaResult
from app.providers.media_router import media_cost
from app.providers.router import RouteChoice
from app.services.object_store import ObjectStore, PresignedGet

from ..contracts.golden import golden_text
from .fakes import ALUM_CLAIM, PA_CLAIM, PA_TEXT, USER_ID, stage

GOLDEN = json.loads(golden_text("media.job.golden.json"))
ASSET_ID = uuid.UUID("8ff6abf0-198d-5196-8a87-3ef7dd5fc432")
JOB_ID = uuid.UUID("9af1da3c-f6c8-547b-b0e8-ca47cd798604")
READ_AT = datetime(2026, 11, 16, 9, 0, 41, tzinfo=UTC)


class GoldenLinks:
    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        assert disposition == (
            f"inline; filename=\"{key.rsplit('/', 1)[1]}\"; filename*=UTF-8''{key.rsplit('/', 1)[1]}"
        )
        return PresignedGet(url=GOLDEN["asset"]["url"], expires_at=now + timedelta(seconds=seconds))


def test_the_view_of_stored_rows_reproduces_the_golden_job_byte_for_byte() -> None:
    leaf = GOLDEN["asset"]["fileName"]
    job = JobRecord(
        id=JOB_ID,
        kind="IMAGE",
        status="SUCCEEDED",
        requested_by=USER_ID,
        stage_id=uuid.UUID(GOLDEN["stage"]["id"]),
        claim_ids=(PA_CLAIM, ALUM_CLAIM),
        style_hint=None,
        prompt="Draw one stage.",
        prompt_hash="b" * 64,
        model="gemini-3.1-flash-image",
        alt_text=PA_TEXT,
        attempts=1,
        asset_id=ASSET_ID,
        hold_id=None,
        bundle=None,
        error=None,
        created_at=datetime(2026, 11, 16, 9, 0, 5, tzinfo=UTC),
        updated_at=READ_AT,
    )
    asset = AssetRecord(
        id=ASSET_ID,
        job_id=JOB_ID,
        s3_key=f"media/{USER_ID}/{ASSET_ID.hex}/{leaf}",
        mime="image/png",
        width=1024,
        height=1024,
        duration_seconds=None,
        model="gemini-3.1-flash-image",
        alt_text=PA_TEXT,
        visibility="PRIVATE",
        created_at=READ_AT,
    )
    view = job_view(job, stage(), asset, links=GoldenLinks(), now=READ_AT)
    dumped = json.dumps(view.model_dump(mode="json", by_alias=True), indent=2, ensure_ascii=False) + "\n"
    assert dumped == golden_text("media.job.golden.json")


def test_presigned_links_use_the_bucket_s_regional_host_and_carry_the_disposition() -> None:
    import boto3
    from botocore.config import Config

    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="test-only-access-key",
        aws_secret_access_key="test-only-secret-not-real",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
    links = ObjectStore(bucket="kalavigyan-media-example", region="ap-south-1", client=client)
    found = links.presigned_get(
        "media/u/0/KalaVigyan_A.png",
        disposition='inline; filename="KalaVigyan_A.png"',
        seconds=900,
        now=READ_AT,
    )
    assert found.url.startswith("https://kalavigyan-media-example.s3.ap-south-1.amazonaws.com/media/u/0/")
    assert "X-Amz-Expires=900" in found.url and "response-content-disposition=inline" in found.url
    assert found.expires_at == READ_AT + timedelta(seconds=900)


def choice(model: str) -> RouteChoice:
    return RouteChoice(
        ordinal=1,
        provider="GEMINI",
        provider_id=None,
        preset="gemini",
        kind="gemini",
        base_url=None,
        key_name="GEMINI_API_KEY",
        model=model,
    )


def test_billed_tokens_decide_the_cost_at_the_published_prices() -> None:
    image = MediaResult(b"", "image/png", 300, 1120, 1120, None, None)
    assert media_cost(choice("gemini-3.1-flash-image"), image, units=1.0, overrides={}) == Decimal("0.067350")
    clip = MediaResult(b"", "video/mp4", 500, 46336, 46336, None, None)
    assert media_cost(choice("gemini-omni-1.2-flash"), clip, units=8.0, overrides={}) == Decimal("0.556782")
    unknown = MediaResult(b"", "image/png", None, None, None, None, None)
    assert media_cost(choice("gemini-nano-banana-2.1"), unknown, units=1.0, overrides={}) == Decimal(
        "0.033600"
    )


def test_image_tokens_are_priced_at_the_image_rate_and_the_rest_of_the_output_at_the_text_rate() -> None:
    recorded = MediaResult(b"", "image/jpeg", 57, 1389, 1120, None, None)
    image = choice("gemini-3.1-flash-image")
    assert media_cost(image, recorded, units=1.0, overrides={}) == Decimal("0.068036")
    unsplit = MediaResult(b"", "image/jpeg", 57, 1389, None, None, None)
    assert media_cost(image, unsplit, units=1.0, overrides={}) == Decimal("0.083369")
    set_by_hand = {"gemini-3.1-flash-image": {"in": 0.5, "out": 3, "media": 30}}
    assert media_cost(image, recorded, units=1.0, overrides=set_by_hand) == Decimal("0.034436")
