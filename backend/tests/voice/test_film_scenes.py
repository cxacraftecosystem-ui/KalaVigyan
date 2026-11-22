import hashlib
from datetime import datetime

import pytest

from app.core.errors import InvalidInput
from app.research.blocks_matter import ReactionPlayerBlock
from app.research.blocks_place import RegionStoryBlock
from app.research.explainer import Explainer
from app.services.naming import score_cue_file_name, score_key, score_manifest_key, score_music_file_name
from app.voice.film_scenes import FilmScene, bed_seconds, film_scenes, held_seconds, scene_cues, scenes_hash
from app.voice.score_prompts import SCORE_PROMPT_VERSION, cue_prompt

from ..contracts.golden import golden_json
from .listen_fakes import golden_explainer

HASH = "a" * 64


def scene(number: int, seconds: float, kind: str = "prose", discipline: str = "HISTORY") -> FilmScene:
    return FilmScene(
        number=number, block_id=f"s{number}.b1", kind=kind, discipline=discipline, seconds=seconds
    )


def golden_block(name: str, kind: str) -> dict:
    document = golden_json(name)
    return next(
        block for section in document["sections"] for block in section["blocks"] if block["kind"] == kind
    )


def test_the_phase_a_scenes_are_its_blocks_in_reading_order_timed_by_narration_or_holds() -> None:
    scenes = film_scenes(golden_explainer())
    assert [(s.number, s.block_id, s.kind, s.discipline) for s in scenes] == [
        (1, "s1.b1", "process_ladder", "PROCESS"),
        (2, "s1.b2", "images", "PROCESS"),
        (3, "s2.b1", "prose", "GEOGRAPHY"),
        (4, "s3.b1", "prose", "CHEMISTRY"),
    ]
    assert [s.seconds for s in scenes] == [39.0, 6.0, 18.0, 19.0]


def test_a_film_opens_on_its_lede_timed_by_its_narration_and_given_no_cue() -> None:
    scenes = film_scenes(Explainer.model_validate(golden_json("explainer.lede.golden.json")))
    assert [(s.number, s.block_id, s.kind, s.discipline, s.seconds) for s in scenes] == [
        (1, "lede", "lede", None, 17.0),
        (2, "s1.b1", "prose", "CHEMISTRY", 10.0),
        (3, "s2.b1", "prose", "MATERIALS", 14.0),
        (4, "s3.b1", "prose", "PROCESS", 12.0),
    ]
    assert cue_prompt("lede", None) is None


def test_sections_play_by_their_order_not_their_place_in_the_list() -> None:
    explainer = golden_explainer()
    shuffled = explainer.model_copy(update={"sections": list(reversed(explainer.sections))})
    assert [s.block_id for s in film_scenes(shuffled)] == ["s1.b1", "s1.b2", "s2.b1", "s3.b1"]


def test_the_scenes_hash_is_the_sha_256_of_their_ids_and_kinds_in_order() -> None:
    text = '[["s1.b1","process_ladder"],["s1.b2","images"],["s2.b1","prose"],["s3.b1","prose"]]'
    assert scenes_hash(film_scenes(golden_explainer())) == hashlib.sha256(text.encode()).hexdigest()


@pytest.mark.parametrize(
    ("seconds", "bed"),
    [([39, 6, 18, 19], 90.0), ([5], 30.0), ([29.9], 30.0), ([120], 120.0), ([120.1], 130.0), ([400], 180.0)],
)
def test_the_bed_is_the_film_rounded_up_to_ten_seconds_within_thirty_and_one_eighty(
    seconds: list[float], bed: float
) -> None:
    assert bed_seconds([scene(n, s) for n, s in enumerate(seconds, start=1)]) == bed


def test_unnarrated_scenes_hold_four_seconds_a_step_three_a_picture_and_six_otherwise() -> None:
    reaction = ReactionPlayerBlock.model_validate(
        golden_block("explainer.phase-b.golden.json", "reaction_player")
    )
    story = RegionStoryBlock.model_validate(golden_block("explainer.phase-b.golden.json", "region_story"))
    assert held_seconds(reaction) == 4.0 * len(reaction.steps)
    assert held_seconds(story) == 4.0 * len(story.steps)
    images = golden_explainer().sections[0].blocks[1]
    assert held_seconds(images) == 6.0 == 3.0 * 2
    assert held_seconds(golden_explainer().sections[1].blocks[0]) == 6.0


def test_a_cue_is_chosen_by_kind_and_field_and_at_most_twelve_play() -> None:
    assert cue_prompt("prose", "GEOGRAPHY") is not None
    assert cue_prompt("prose", "CHEMISTRY") is None
    assert cue_prompt("region_story", "CLIMATE") == cue_prompt("region_story", "GEOGRAPHY")
    ladders = [scene(n, 6, "process_ladder", "PROCESS") for n in range(1, 21)]
    assert [cue.scene.number for cue in scene_cues(ladders)] == list(range(1, 13))
    assert SCORE_PROMPT_VERSION == "film-score/v1"


@pytest.mark.parametrize(
    "row", golden_json("naming-golden.json")["scoreFiles"], ids=lambda row: row["fileName"]
)
def test_score_files_are_named_by_the_one_convention(row: dict) -> None:
    moment = datetime.fromisoformat(row["generatedAt"])
    made = (
        score_music_file_name(moment) if row["scene"] is None else score_cue_file_name(moment, row["scene"])
    )
    assert made == row["fileName"]
    assert score_key(HASH, made) == f"media/score/{HASH}/{made}"


def test_score_keys_need_a_cache_id_a_scene_and_an_answer_language() -> None:
    answer = golden_explainer().answer_id
    assert score_manifest_key(answer, "hi") == f"media/score/{answer}/hi/score.json"
    moment = datetime.fromisoformat("2026-11-18T05:00:00+00:00")
    with pytest.raises(InvalidInput):
        score_key("not-a-hash", score_music_file_name(moment))
    with pytest.raises(InvalidInput):
        score_cue_file_name(moment, 0)
    with pytest.raises(InvalidInput):
        score_manifest_key(answer, "../en")
