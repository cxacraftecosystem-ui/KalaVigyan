import base64
import uuid

from app.providers.picture_vision import provider_content
from app.research.image_screens import VisionRequest

PREVIEW = b"\xff\xd8preview"
REQUEST = VisionRequest(
    preview=PREVIEW, mime="image/jpeg", ai_made=False, user_id=uuid.UUID(int=1), role="RESEARCHER"
)
ENCODED = base64.b64encode(PREVIEW).decode("ascii")


def test_gemini_gets_the_picture_as_inline_bytes_beside_the_question() -> None:
    assert provider_content("gemini", REQUEST, "Is it an ID?") == [
        {
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": PREVIEW}},
                {"text": "Is it an ID?"},
            ],
        }
    ]


def test_anthropic_gets_a_base64_image_block_before_the_question() -> None:
    assert provider_content("anthropic", REQUEST, "Is it an ID?") == [
        {"type": "image", "source": {"type": "base64", "media_type": "image/jpeg", "data": ENCODED}},
        {"type": "text", "text": "Is it an ID?"},
    ]


def test_openai_shaped_routes_get_a_data_url() -> None:
    for kind in ("openai", "openai_compatible"):
        assert provider_content(kind, REQUEST, "Is it an ID?") == [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ENCODED}"}},
            {"type": "text", "text": "Is it an ID?"},
        ]
