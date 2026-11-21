import io
import json

import pytest
from PIL import Image
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.errors import InvalidInput
from app.models import FieldImage
from app.research.field_photo_reviews import (
    PhotoCrop,
    PhotoDecisionRequest,
    master_flags,
    photo_flags,
    photo_risk,
)
from app.research.image_intake_pixels import cropped
from app.research.image_screens import vision_verdict
from app.services.field_photo_scope import shown_field_photos
from tests.pictures import picture

SEEN = "a" * 64


def request(**fields: object) -> PhotoDecisionRequest:
    return PhotoDecisionRequest.model_validate({"seenSha256": SEEN} | fields)


@pytest.mark.parametrize(
    ("fields", "problem"),
    [
        ({"decision": "HIDE"}, "Say why the photograph stays hidden."),
        ({"decision": "SHOW", "reason": "POOR_QUALITY"}, "Only a photograph kept hidden takes a reason."),
        ({"decision": "HIDE", "reason": "OTHER", "note": "no"}, "Say in a note why it stays hidden."),
        ({"decision": "CROP"}, "A crop gives the region to keep, and only a crop does."),
        (
            {"decision": "SHOW", "crop": {"left": 0, "top": 0, "width": 100, "height": 100}},
            "A crop gives the region to keep, and only a crop does.",
        ),
        (
            {"decision": "HIDE", "reason": "NOT_AGREED", "clearFlags": True},
            "A flag is cleared only to show the whole photograph.",
        ),
        ({"decision": "SHOW", "clearFlags": True}, "Say in a note why the screen's flag is wrong."),
    ],
)
def test_an_incomplete_decision_says_what_it_lacks(fields: dict[str, object], problem: str) -> None:
    with pytest.raises(ValidationError) as refused:
        request(**fields)
    assert problem in str(refused.value)


def test_a_complete_decision_is_accepted() -> None:
    assert request(decision="SHOW").decision == "SHOW"
    assert request(decision="HIDE", reason="IDENTITY_DOCUMENT").reason == "IDENTITY_DOCUMENT"
    assert request(decision="HIDE", reason="OTHER", note="A family wedding").note == "A family wedding"
    assert request(decision="SHOW", clearFlags=True, note="It is a printed block, not a card").clear_flags
    cut = request(decision="CROP", crop={"left": 10, "top": 20, "width": 300, "height": 200})
    assert cut.crop is not None and cut.crop.box() == (10, 20, 300, 200)


def test_a_crop_keeps_at_least_sixty_four_pixels_a_side() -> None:
    with pytest.raises(ValidationError):
        PhotoCrop(left=0, top=0, width=63, height=400)


def test_a_crop_lies_inside_the_photograph_and_leaves_some_of_it_out() -> None:
    crop = PhotoCrop(left=100, top=50, width=800, height=600)
    assert crop.inside(900, 650) and not crop.inside(899, 650) and not crop.inside(900, 649)
    assert crop.leaves_out(900, 650)
    assert not PhotoCrop(left=0, top=0, width=900, height=650).leaves_out(900, 650)


def test_an_identity_document_always_needs_a_master_admin_and_a_face_only_when_no_one_is_named() -> None:
    assert master_flags(["ID_DOCUMENT", "FACE"], someone_named=True) == ("ID_DOCUMENT",)
    assert master_flags(["FACE", "UNSAFE"], someone_named=True) == ()
    assert master_flags(["FACE", "UNSAFE"], someone_named=False) == ("FACE",)
    assert master_flags(None, someone_named=False) == ()


def test_identity_documents_sort_before_faces_before_everything_else() -> None:
    assert [photo_risk(flags) for flags in (["FACE", "ID_DOCUMENT"], ["FACE"], ["UNSAFE"], None, [])] == [
        "IDENTITY",
        "FACE",
        "CHECK",
        "CHECK",
        "CLEAR",
    ]


def test_a_photograph_within_twelve_bits_of_another_is_a_near_duplicate() -> None:
    assert photo_flags(("UNSAFE", "ID_DOCUMENT"), 12) == ("ID_DOCUMENT", "UNSAFE", "NEAR_DUPLICATE")
    assert photo_flags(("FACE",), 13) == ("FACE",)
    assert photo_flags((), None) == ()


def answer(**fields: object) -> str:
    return json.dumps({"idDocument": False, "face": False, "unsafe": False, "note": ""} | fields)


def test_a_face_is_flagged_in_a_field_photograph_when_the_screen_is_asked_about_faces() -> None:
    seen = answer(face=True, note="A man at the table")
    assert vision_verdict(seen, ai_made=False, faces=True) == (("FACE",), "A man at the table")
    assert vision_verdict(seen, ai_made=False) == ((), None)
    assert vision_verdict(seen, ai_made=True, faces=True) == (("FACE_IN_AI_IMAGE",), "A man at the table")


def test_a_crop_is_a_new_copy_of_the_region_kept_in_the_photograph_s_format() -> None:
    original = picture(800, 600, seed=3, kind="JPEG")
    made = cropped(original, (100, 50, 400, 300), "image/jpeg")
    assert (made.mime, made.width, made.height) == ("image/jpeg", 400, 300)
    with Image.open(io.BytesIO(made.data)) as opened:
        assert (opened.format, opened.size) == ("JPEG", (400, 300))
        assert not opened.getexif()
    png = cropped(picture(640, 480, seed=4), (0, 0, 320, 240), "image/png")
    assert (png.mime, png.width, png.height) == ("image/png", 320, 240)


def test_a_region_outside_the_photograph_is_refused() -> None:
    with pytest.raises(InvalidInput):
        cropped(picture(800, 600, seed=3, kind="JPEG"), (500, 0, 400, 300), "image/jpeg")


def test_a_held_photograph_is_shown_only_when_its_current_copy_was_decided_shown() -> None:
    text = str(select(FieldImage.id).where(*shown_field_photos()).compile(dialect=postgresql.dialect()))
    assert '"FieldImage"."artisanLinked" IS false' in text and text.count("EXISTS") >= 3
    assert '"imageSha256" = "FieldImage".sha256' in text
    assert "decision IN" in text
