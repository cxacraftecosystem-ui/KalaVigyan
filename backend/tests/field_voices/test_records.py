from typing import Any

from app.services.field_voices_feed import Live, parse_page
from app.services.field_voices_items import ImageItem, TranscriptItem
from app.services.field_voices_photos import photo_plan
from app.services.field_voices_records import recording_plan, sentences_within, source_values
from tests.field_voices.fixtures import DR, FR, recorded

PUBLIC, PASSAGE, WINDOW = "PUBLIC", "PASSAGE", "WINDOW"


def item(name: str, portal: str, index: int = 0) -> Any:
    body = recorded(name)
    page = parse_page(body, portal=portal, asked=(body["stream"], body["view"], body["cursor"]))
    change = page.changes[index]
    assert isinstance(change, Live)
    return change


def fr_recording() -> TranscriptItem:
    found = item("field-transcripts-all-1", FR).item
    assert isinstance(found, TranscriptItem)
    return found


def test_only_artisan_and_designer_turns_of_forty_characters_are_quotes() -> None:
    plan = recording_plan(fr_recording(), portal=FR)
    quotable = [(s.portal_segment_id, s.role, s.quotable) for s in plan.segments]
    assert quotable == [
        ("fr-turn-1", "RESEARCHER", False),
        ("fr-turn-2", "ARTISAN", True),
        ("fr-turn-3", "ARTISAN", False),
        ("fr-turn-4", None, False),
    ]


def test_quotes_are_passages_and_the_full_transcript_is_windows_and_both_are_public() -> None:
    plan = recording_plan(fr_recording(), portal=FR)
    public = [chunk for chunk in plan.chunks if chunk.kind == PASSAGE]
    assert [(chunk.lang, chunk.locator) for chunk in public] == [("gu", "0:06–0:33"), ("en", "0:06–0:33")]
    assert public[1].text.endswith("Call me on [number].")
    windows = [chunk for chunk in plan.chunks if chunk.kind == WINDOW]
    assert [chunk.lang for chunk in windows] == ["und", "en"]
    original = windows[0].text.splitlines()
    assert original[0].startswith("Field Researcher Demo: ")
    assert original[1].startswith("Asha Demo: ")
    assert original[3].startswith("Speaker 3: ")
    assert windows[0].locator == "0:00–13:10"
    assert all(chunk.acl == PUBLIC for chunk in plan.chunks)
    assert {chunk.kind for chunk in plan.chunks} == {PASSAGE, WINDOW}
    assert plan.chunks.index(public[0]) == 0


def test_a_text_transcript_is_only_a_window() -> None:
    change = item("field-transcripts-all-2", FR)
    plan = recording_plan(change.item, portal=FR)
    assert not any(segment.quotable for segment in plan.segments)
    assert [(chunk.acl, chunk.kind, chunk.locator) for chunk in plan.chunks] == [
        (PUBLIC, WINDOW, "paragraph 1")
    ]


def test_the_source_is_a_field_interview_credited_by_name_workshop_and_date() -> None:
    recording = fr_recording()
    plan = recording_plan(recording, portal=FR)
    assert plan.title == "Field interview, Ajrakh documentation visit, 14 March 2026"
    assert plan.authors == ("Asha Demo",)
    assert plan.credit == "Asha Demo · Ajrakh documentation visit, 14 March 2026 · Field Repository"
    values = source_values(
        plan, recording, portal=FR, url=None, revision="r" * 32, retrieved_at=recording.recorded_at
    )
    assert (values["kind"], values["reliability"], values["sensitivity"]) == (
        "FIELD_TESTIMONY",
        "A",
        "ATTRIBUTE_REQUIRED",
    )
    assert values["evidenceKind"] == "FIELD_INTERVIEW"
    assert values["externalIds"] == {
        "fieldRepository": {"mediaId": "fr-media-1", "recordingId": "fr-rec-1", "revision": "r" * 32}
    }


def test_a_workshop_title_is_never_shown_beside_an_unnamed_person() -> None:
    plan = recording_plan(item("field-transcripts-all-2", FR).item, portal=FR)
    assert plan.workshop_line == "a workshop in Kachchh, Gujarat, March 2026"
    assert plan.title == "Field recording, a workshop in Kachchh, Gujarat, March 2026, 15 March 2026"


def test_a_design_workshop_recording_is_titled_and_quotes_the_designer() -> None:
    plan = recording_plan(item("designer-transcripts-all-1", DR).item, portal=DR)
    assert plan.title == "Design workshop recording, a workshop in Jaipur, Rajasthan, June 2026, 24 June 2026"
    assert [(s.role, s.quotable) for s in plan.segments] == [("DESIGNER", True), ("ARTISAN", True)]
    public = [(chunk.lang, chunk.locator) for chunk in plan.chunks if chunk.kind == PASSAGE]
    assert public == [("en", "0:00–0:20"), ("hi", "0:21–1:01"), ("en", "0:21–1:01")]


def test_long_turns_are_cut_at_sentence_ends() -> None:
    sentence = "The paste rests overnight. " * 80
    pieces = sentences_within(sentence.strip(), 300)
    assert all(len(piece) <= 300 for piece in pieces)
    assert all(piece.endswith(".") for piece in pieces)
    assert " ".join(pieces) == sentence.strip()


def test_photographs_are_grouped_by_step_product_and_prototype_and_credited() -> None:
    field_image = item("field-images-all-1", FR).item
    assert isinstance(field_image, ImageItem)
    plan = photo_plan(field_image, portal=FR)
    assert [(g.kind, g.key, g.label) for g in plan.groups] == [
        ("PROCESS_STEP", "step:fr-step-2", "Ajrakh printing · First resist printing"),
        ("PRODUCT", "product:fr-prod-1", "Ajrakh stole"),
    ]
    assert plan.credit == "Asha Demo · Ajrakh documentation visit, 14 March 2026 · Field Repository"
    designer_image = item("designer-images-all-1", DR).item
    assert isinstance(designer_image, ImageItem)
    designed = photo_plan(designer_image, portal=DR)
    assert [(g.kind, g.key, g.label) for g in designed.groups] == [
        ("PROTOTYPE", "prototype:dr-row-5", "Indigo dabu table runner")
    ]
    assert designed.credited == ("Ravi Demo", "Meera Demo")
    assert designed.alt == "Photograph of Bagru Hand Block Print: Second prototype after the colour trial"
