import io

import boto3
import pytest
from botocore.config import Config
from botocore.response import StreamingBody
from botocore.stub import Stubber

from app.core.errors import ExternalFailure
from app.services.object_store import ObjectStore

BUCKET = "kalavigyan-media-example"
KEY = "media/narration/" + "a" * 64 + "/narration.json"


def stubbed() -> tuple[ObjectStore, Stubber]:
    client = boto3.client(
        "s3",
        region_name="ap-south-1",
        aws_access_key_id="test-only-access-key",
        aws_secret_access_key="test-only-secret-not-real",
        config=Config(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )
    return ObjectStore(bucket=BUCKET, region="ap-south-1", client=client), Stubber(client)


async def test_reading_an_object_returns_its_bytes() -> None:
    store, stub = stubbed()
    body = b'{"schemaVersion":1}'
    stub.add_response(
        "get_object", {"Body": StreamingBody(io.BytesIO(body), len(body))}, {"Bucket": BUCKET, "Key": KEY}
    )
    with stub:
        assert await store.get(KEY) == body


async def test_a_missing_object_reads_as_nothing() -> None:
    store, stub = stubbed()
    stub.add_client_error("get_object", service_error_code="NoSuchKey", http_status_code=404)
    with stub:
        assert await store.get(KEY) is None


async def test_a_refused_read_fails_loudly() -> None:
    store, stub = stubbed()
    stub.add_client_error("get_object", service_error_code="AccessDenied", http_status_code=403)
    with stub, pytest.raises(ExternalFailure) as failure:
        await store.get(KEY)
    assert failure.value.kind == "auth" and "AccessDenied" in str(failure.value)


def put_params(**extra: str) -> dict[str, object]:
    return {
        "Bucket": BUCKET,
        "Key": KEY,
        "Body": b"{}",
        "ContentType": "application/json",
        "ServerSideEncryption": "AES256",
        **extra,
    }


async def test_a_new_object_is_written_only_where_none_is() -> None:
    store, stub = stubbed()
    stub.add_response("put_object", {}, put_params(IfNoneMatch="*"))
    with stub:
        assert await store.put_if_absent(KEY, b"{}", content_type="application/json") is True


async def test_an_object_already_there_is_left_as_it_is() -> None:
    store, stub = stubbed()
    stub.add_client_error("put_object", service_error_code="PreconditionFailed", http_status_code=412)
    stub.add_client_error("put_object", service_error_code="ConditionalRequestConflict", http_status_code=409)
    with stub:
        assert await store.put_if_absent(KEY, b"{}", content_type="application/json") is False
        assert await store.put_if_absent(KEY, b"{}", content_type="application/json") is False


async def test_a_refused_conditional_write_fails_loudly() -> None:
    store, stub = stubbed()
    stub.add_client_error("put_object", service_error_code="AccessDenied", http_status_code=403)
    with stub, pytest.raises(ExternalFailure):
        await store.put_if_absent(KEY, b"{}", content_type="application/json")


async def test_keys_under_a_prefix_are_read_across_pages_in_order() -> None:
    store, stub = stubbed()
    clip = "media/score/" + "b" * 64 + "/clip.json"
    stub.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": clip}], "IsTruncated": True, "NextContinuationToken": "next"},
        {"Bucket": BUCKET, "Prefix": "media/score/"},
    )
    stub.add_response(
        "list_objects_v2",
        {"Contents": [{"Key": KEY}], "IsTruncated": False},
        {"Bucket": BUCKET, "Prefix": "media/score/", "ContinuationToken": "next"},
    )
    with stub:
        assert await store.keys("media/score/") == [KEY, clip]


async def test_a_copy_stays_in_the_bucket_and_is_encrypted() -> None:
    store, stub = stubbed()
    target = "media/craft/" + "c" * 64 + "/KalaVigyan_Generated-Image.png"
    stub.add_response(
        "copy_object",
        {},
        {
            "Bucket": BUCKET,
            "Key": target,
            "CopySource": {"Bucket": BUCKET, "Key": KEY},
            "ServerSideEncryption": "AES256",
        },
    )
    with stub:
        await store.copy(KEY, target)
