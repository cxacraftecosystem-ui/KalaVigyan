import uuid

from app.services.differ_rejudge import FlaggedPair, rejudged_pairs

from .fakes import JUDGE_MODEL, FakeJudge
from .judge_replies import compared


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-differ-rejudge/{name}")


HARI_SARANA, DRYING, THREE, FOUR = key("hari-sarana"), key("drying"), key("three"), key("four")
PAIRS = [
    FlaggedPair(
        HARI_SARANA,
        "Hari Sarana takes 3-5 days depending on the weather.",
        "CLIMATE",
        DRYING,
        "Drying takes a day or longer in the monsoon.",
    ),
    FlaggedPair(
        THREE,
        "Ajrakh cloth is dipped in the indigo vat three times.",
        "PROCESS",
        FOUR,
        "Ajrakh cloth goes into the vat four times.",
    ),
]


async def test_a_flagged_pair_the_structural_judge_finds_compatible_would_clear_and_a_real_clash_would_not() -> (
    None
):
    judge = FakeJudge(
        {
            "comparisons": [
                compared(str(HARI_SARANA), DRYING, "DISTINCT"),
                compared(str(THREE), FOUR, "DIFFERS"),
            ]
        }
    )
    found = {row["claim"]: row for row in await rejudged_pairs(PAIRS, (judge,))}
    assert (found[str(HARI_SARANA)]["wouldClear"], found[str(THREE)]["wouldClear"]) == (True, False)
    assert [pair["relation"] for pair in found[str(THREE)]["pairs"]] == ["DIFFERS"]
    assert found[str(THREE)]["model"] == JUDGE_MODEL
    assert len(judge.calls) == 1 and "Hari Sarana" in judge.calls[0]["user"]


async def test_no_flagged_pair_asks_no_judge() -> None:
    judge = FakeJudge()
    assert await rejudged_pairs([], (judge,)) == []
    assert judge.calls == []
