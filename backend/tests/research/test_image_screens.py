import base64
import json
import uuid

import pytest
from pydantic import ValidationError

from app.core.errors import InvalidInput
from app.research.image_contributions import ImageBatch
from app.research.image_contributions_tasks import PictureAim, is_picture_detail, picture_aim, picture_detail
from app.research.image_intake_fetch import decoded_base64
from app.research.image_screens import (
    Near,
    VisionVerdict,
    screen_flags,
    screen_reasons,
    signed_fingerprint,
    unscreened,
    verdict_of,
    vision_prompt,
    vision_verdict,
)
from app.research.open_work import parse_task_key

STAGE = uuid.UUID("5ca1ab1e-0000-4000-8000-000000000001")
ASSET = uuid.UUID("5ca1ab1e-0000-4000-8000-000000000002")
BATCH = {
    "craftSlug": "Kutch-Ajrakh",
    "origin": "AI_GENERATED",
    "generator": "ChatGPT, gpt-image-1",
    "rightsConfirmed": True,
    "termsVersion": "2026-11-19",
    "pictures": [
        {
            "claimIds": [str(uuid.UUID(int=21))],
            "prompt": "An indigo vat at dawn",
            "caption": "The vat at dawn",
            "altText": "A clay vat with a blue film",
            "stageId": str(STAGE),
        },
        {
            "claimIds": [str(uuid.UUID(int=22))],
            "prompt": "A block being printed",
            "caption": "Printing the resist",
            "altText": "A carved block on red cloth",
            "slot": "MASTHEAD",
        },
    ],
}


def answer(**fields: object) -> str:
    return json.dumps({"idDocument": False, "face": False, "unsafe": False, "note": ""} | fields)


def test_an_identity_card_and_unsafe_content_are_flagged_with_the_screen_s_note() -> None:
    assert vision_verdict(
        answer(idDocument=True, note="A card with a photo and a number"), ai_made=False
    ) == (
        ("ID_DOCUMENT",),
        "A card with a photo and a number",
    )
    assert vision_verdict(answer(unsafe=True), ai_made=False) == (("UNSAFE",), None)


def test_a_face_is_flagged_only_in_an_ai_made_picture() -> None:
    assert vision_verdict(answer(face=True, note="A woman's face"), ai_made=False) == ((), None)
    assert vision_verdict(answer(face=True, note="A woman's face"), ai_made=True) == (
        ("FACE_IN_AI_IMAGE",),
        "A woman's face",
    )


@pytest.mark.parametrize("text", ["not json", "[]", json.dumps({"idDocument": "maybe"})])
def test_an_answer_off_the_schema_is_not_read(text: str) -> None:
    assert vision_verdict(text, ai_made=False) is None


def test_the_prompt_asks_about_ids_faces_and_unsafe_content_and_names_an_ai_picture() -> None:
    system, user = vision_prompt(ai_made=True)
    assert "Answer in the JSON schema" in system
    assert "Aadhaar" in user and "PAN" in user and "passport" in user and "face and a number" in user
    assert "The picture is AI-made." in user
    assert "AI-made" not in vision_prompt(ai_made=False)[1]


def test_a_close_stored_picture_flags_and_a_far_one_does_not() -> None:
    clear = VisionVerdict(ran=True)
    assert screen_flags(clear, Near(ASSET, 9, live=True, contributed=True)) == ("NEAR_DUPLICATE",)
    assert screen_flags(clear, Near(ASSET, 13, live=True, contributed=True)) == ()
    assert screen_flags(VisionVerdict(ran=True, flags=("UNSAFE",)), None) == ("UNSAFE",)


def test_the_verdict_is_clear_flagged_or_unscreened() -> None:
    assert verdict_of(()) == "CLEAR"
    assert verdict_of(("ID_DOCUMENT", "NEAR_DUPLICATE")) == "FLAGGED"
    assert verdict_of(unscreened("No vision route is set up").flags) == "UNSCREENED"


def test_the_reasons_say_each_flag_and_the_screen_s_note() -> None:
    assert screen_reasons(("ID_DOCUMENT",), "A PAN card") == [
        "It may show an identity document, or a card with a face and a number.",
        "A PAN card",
    ]
    assert screen_reasons((), "ignored") == []


def test_a_fingerprint_is_stored_as_a_signed_64_bit_integer() -> None:
    assert signed_fingerprint(5) == 5
    assert signed_fingerprint((1 << 64) - 1) == -1
    assert signed_fingerprint(1 << 63) == -(1 << 63)
    with pytest.raises(ValueError):
        signed_fingerprint(1 << 64)


def test_a_picture_task_names_a_stage_a_material_or_a_slot_and_its_key_parses() -> None:
    assert picture_detail(PictureAim(stage_id=STAGE)) == f"stage-{STAGE}"
    assert picture_detail(PictureAim(material_id=STAGE)) == f"material-{STAGE}"
    assert picture_detail(PictureAim(slot="RECORD")) == "slot-record"
    assert picture_detail(PictureAim()) is None
    assert picture_aim(f"stage-{STAGE}") == PictureAim(stage_id=STAGE)
    assert picture_aim("slot-masthead") == PictureAim(slot="MASTHEAD")
    assert not is_picture_detail("stage-not-a-uuid") and not is_picture_detail("slot-cover")
    key = parse_task_key(f"MISSING_PICTURE:craft:Kutch-Ajrakh:stage-{STAGE}")
    assert (key.kind, key.subject_kind, key.slug, key.detail) == (
        "MISSING_PICTURE",
        "craft",
        "Kutch-Ajrakh",
        f"stage-{STAGE}",
    )
    with pytest.raises(InvalidInput):
        parse_task_key("MISSING_PICTURE:craft:Kutch-Ajrakh:slot-cover")


def test_a_batch_shares_one_declaration_and_each_picture_keeps_its_own_words() -> None:
    batch = ImageBatch.model_validate(BATCH)
    first, second = batch.declarations()
    assert (first.generator, first.prompt, first.stage_id, first.slot) == (
        "ChatGPT, gpt-image-1",
        "An indigo vat at dawn",
        STAGE,
        None,
    )
    assert (second.caption, second.slot, second.stage_id) == ("Printing the resist", "MASTHEAD", None)


@pytest.mark.parametrize(
    ("changes", "says"),
    [
        ({"generator": None}, "Picture 1: An AI-made image names its tool"),
        ({"origin": "PHOTOGRAPH"}, "Picture 1: Only an AI-made image carries a tool"),
        ({"pictures": []}, "at least 1"),
    ],
)
def test_a_batch_whose_declaration_does_not_fit_a_picture_is_refused(
    changes: dict[str, object], says: str
) -> None:
    with pytest.raises(ValidationError, match=says):
        ImageBatch.model_validate(BATCH | changes)


def test_a_picture_shows_one_target_at_most() -> None:
    picture = BATCH["pictures"][0] | {"slot": "RECORD"}  # type: ignore[operator]
    with pytest.raises(ValidationError, match="one stage, one material or one picture slot"):
        ImageBatch.model_validate(BATCH | {"pictures": [picture]})


def test_a_picture_in_the_call_is_read_from_base64_or_a_data_uri_and_capped() -> None:
    raw = b"\x89PNG\r\n\x1a\nrest"
    encoded = base64.b64encode(raw).decode("ascii")
    assert decoded_base64(encoded) == raw
    assert decoded_base64(f"data:image/png;base64,{encoded}") == raw
    with pytest.raises(InvalidInput, match="not valid base64"):
        decoded_base64("@@@@")
    with pytest.raises(InvalidInput, match="at most 1 MB"):
        decoded_base64(base64.b64encode(bytes(2 * 1024 * 1024)).decode("ascii"), limit=1024 * 1024)
