import json
import uuid

import pytest

from app.core.errors import InvalidInput
from app.retrieval.eval_floors import HAND_WRITTEN
from app.retrieval.evaluation import GoldenQuestion
from app.retrieval.fusion import reciprocal_rank_fusion
from app.retrieval.fusion_settings import (
    FUSION_FILE,
    ClaimWeights,
    FusionSettings,
    fusion_settings,
    parse_fusion_settings,
    settings_text,
)
from app.retrieval.fusion_sweep import GENERATED_ENGLISH, picked_row, sweep_rows

D1, D2, D3, X = (uuid.UUID(int=n) for n in range(1, 5))
SHARED_WORDS = [D1, D2, D3]
PARAPHRASE = [SHARED_WORDS, [X], SHARED_WORDS]
EQUAL = FusionSettings()
VECTOR_HEAVY = FusionSettings(claims=ClaimWeights(vector=3.0))
VECTOR_ONLY = FusionSettings(claims=ClaimWeights(lexical=0.0, vector=1.0, entity=0.0))


def keys(rankings: list[list[uuid.UUID]], weights: tuple[float, ...] | None = None) -> list[uuid.UUID]:
    return [item.key for item in reciprocal_rank_fusion(rankings, weights=weights)]


def test_equal_weights_let_two_rankings_that_share_words_outvote_the_vector_ranking() -> None:
    assert keys(PARAPHRASE) == [D1, D2, D3, X]
    assert keys(PARAPHRASE, (1.0, 1.0, 1.0)) == keys(PARAPHRASE)


def test_a_vector_weight_of_three_puts_the_vector_ranking_s_first_item_first() -> None:
    fused = reciprocal_rank_fusion(PARAPHRASE, weights=(1.0, 3.0, 1.0))
    assert [item.key for item in fused] == [X, D1, D2, D3]
    assert fused[0].score == pytest.approx(3 / 61)
    assert fused[1].score == pytest.approx(2 / 61)


def test_a_ranking_weighted_zero_adds_nothing() -> None:
    fused = reciprocal_rank_fusion([[D1], [D2], [D2]], weights=(1.0, 0.0, 0.0))
    assert [(item.key, item.score) for item in fused] == [(D1, pytest.approx(1 / 61)), (D2, 0.0)]


@pytest.mark.parametrize("weights", [(1.0, 1.0), (1.0, -1.0, 1.0), (0.0, 0.0, 0.0), (1.0, float("nan"), 1.0)])
def test_weights_that_do_not_fit_the_rankings_are_refused(weights: tuple[float, ...]) -> None:
    with pytest.raises(InvalidInput):
        reciprocal_rank_fusion(PARAPHRASE, weights=weights)


def test_the_committed_fusion_is_the_weighting_the_production_sweep_picked_written_as_it_writes_it() -> None:
    settings = fusion_settings()
    assert (settings.k, settings.claims.ordered()) == (20, (0.5, 5.0, 0.25))
    assert settings_text(settings) == FUSION_FILE.read_text(encoding="utf-8")


def test_a_fusion_file_that_weighs_every_ranking_zero_is_refused() -> None:
    data = json.loads(FUSION_FILE.read_text(encoding="utf-8"))
    data["claims"] = {"lexical": 0, "vector": 0, "entity": 0}
    with pytest.raises(InvalidInput, match="above zero"):
        parse_fusion_settings(data)


def asked(key: str, expected: uuid.UUID) -> tuple[GoldenQuestion, tuple[dict[uuid.UUID, str], ...]]:
    question = GoldenQuestion(
        key=key, craft_slug=None, question=f"Question {key}?", expected=(str(expected),)
    )
    return question, ({expected: str(expected)},)


def test_the_sweep_picks_the_weighting_that_finds_paraphrases_and_keeps_the_hand_written() -> None:
    named = {HAND_WRITTEN: [asked("h1", D1)], GENERATED_ENGLISH: [asked("g1", X)]}
    rankings = {"h1": ([D1, D2], [D2, D1], [D1]), "g1": tuple(PARAPHRASE)}
    rows = sweep_rows(named, rankings, [EQUAL, VECTOR_ONLY, VECTOR_HEAVY])
    measured = [
        [
            (row.sets[name].recall_at5, row.sets[name].mean_reciprocal_rank)
            for name in (HAND_WRITTEN, GENERATED_ENGLISH)
        ]
        for row in rows
    ]
    assert measured == [[(1.0, 1.0), (1.0, 0.25)], [(1.0, 0.5), (1.0, 1.0)], [(1.0, 1.0), (1.0, 1.0)]]
    assert picked_row(rows).settings is VECTOR_HEAVY


def test_the_sweep_keeps_the_current_weighting_when_none_does_better() -> None:
    named = {HAND_WRITTEN: [asked("h1", D1)], GENERATED_ENGLISH: [asked("g1", D1)]}
    rankings = {"h1": ([D1, D2], [D2, D1], [D1]), "g1": ([D1, D2], [D2, D1], [D1])}
    rows = sweep_rows(named, rankings, [EQUAL, VECTOR_HEAVY])
    assert picked_row(rows).settings is EQUAL
