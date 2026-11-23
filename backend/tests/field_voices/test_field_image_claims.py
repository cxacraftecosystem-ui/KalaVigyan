import uuid

from app.research.image_relevance import ClaimText, illustrated_claims
from app.services.field_voices_illustrations import photo_described

RESIST = uuid.UUID("00000000-0000-4000-8000-000000000001")
STOLE = uuid.UUID("00000000-0000-4000-8000-000000000002")
PRINTED = uuid.UUID("00000000-0000-4000-8000-000000000003")

RECORDED_GROUPS = [
    ("PROCESS_STEP", "Ajrakh printing · First resist printing"),
    ("PERSON", "Asha Demo"),
    ("PRODUCT", "Ajrakh stole"),
    ("WORKSHOP", "Ajrakh documentation visit"),
]


def test_a_photo_is_described_by_its_caption_and_the_labels_of_what_it_shows_not_who_or_when() -> None:
    assert photo_described("Printing the first resist", RECORDED_GROUPS) == (
        "Printing the first resist\nAjrakh printing · First resist printing\nAjrakh stole"
    )
    assert photo_described(None, [("PERSON", "Asha Demo")]) == ""


def test_a_photo_illustrates_the_claims_sharing_two_of_its_words_but_not_the_craft_s_name() -> None:
    claims = [
        ClaimText(STOLE, "The finished stole is washed in the river."),
        ClaimText(RESIST, "The first resist paste is pressed with a wooden block."),
        ClaimText(PRINTED, "Ajrakh cloth is printed first in Kutch."),
    ]
    found = illustrated_claims("Printing the first resist", claims, leave_out="Ajrakh Print of Kutch")
    assert found is not None and (found.claim_ids, found.shared) == ((RESIST,), 2)
    unnamed = illustrated_claims("Printing the first resist", claims, leave_out="")
    assert unnamed is not None and unnamed.claim_ids == (RESIST, PRINTED)
    assert illustrated_claims("Ajrakh stole", claims, leave_out="Ajrakh") is None
