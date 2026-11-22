import hashlib
import re
import uuid
from dataclasses import replace
from pathlib import Path

from app.retrieval.eval_floors import FloorCheck, parse_floors
from app.retrieval.eval_runs import set_checks
from app.retrieval.evaluation import QuestionResult, RetrievalReport, SetReport
from app.retrieval.golden import GeneratedQuestion
from app.retrieval.release_check import (
    EXIT_BELOW_FLOOR,
    EXIT_PASSED,
    EXIT_WARNED,
    RELEASE_SECONDS,
    ReleaseCheck,
    ReleaseVerdict,
    release_sample,
    rerank_warnings,
)

REPO = Path(__file__).resolve().parents[3]
SWITCH = REPO / "infra" / "deploy" / "blue_green.sh"
HAND_WRITTEN = 77


def generated(craft: str, number: int, language: str = "en") -> GeneratedQuestion:
    fact = uuid.uuid5(uuid.NAMESPACE_URL, f"test-release/{craft}/{number}")
    return GeneratedQuestion(
        key=f"{fact}-{language}",
        craft_slug=craft,
        question=f"Question {number} on {craft}?",
        expected=((str(fact),),),
        fact=fact,
        language=language,
    )


def test_the_sample_takes_two_english_questions_per_craft_and_stays_within_four_hundred() -> None:
    questions = [generated(f"Craft-{c}", n) for c in range(300) for n in range(4)]
    questions += [generated("Craft-0", 9, "hi")]
    sample = release_sample(questions, hand_written=HAND_WRITTEN)
    assert len(sample) == 322
    assert HAND_WRITTEN + len(sample) <= 400
    per_craft: dict[str, int] = {}
    for question in sample:
        per_craft[question.craft_slug] = per_craft.get(question.craft_slug, 0) + 1
    assert set(per_craft.values()) == {2} and len(per_craft) == 161
    assert all(question.language == "en" for question in sample)
    assert release_sample(list(reversed(questions)), hand_written=HAND_WRITTEN) == sample


def test_a_craft_s_two_questions_are_those_first_by_the_hash_of_their_key() -> None:
    questions = [generated("Only-Craft", n) for n in range(5)]
    sample = release_sample(questions, hand_written=0, seed=11)
    expected = sorted(questions, key=lambda q: hashlib.sha256(f"11:{q.key}".encode()).hexdigest())[:2]
    assert sample == tuple(expected)


FOUND = uuid.uuid5(uuid.NAMESPACE_URL, "test-release/found")
NOISE = uuid.uuid5(uuid.NAMESPACE_URL, "test-release/noise")
FLOORS = parse_floors(
    {
        "version": 2,
        "retrieval": {
            "handWritten": {
                "reranked": {"recallAt5": 0.9, "meanReciprocalRank": 0.9},
                "fused": {"recallAt5": 0.5},
            }
        },
        "answers": {},
    }
)


def one_order(*ranked: tuple[uuid.UUID, ...], skipped: int = 0) -> RetrievalReport:
    return RetrievalReport((QuestionResult("q", ranked, ({FOUND: "f"},)),), skipped=skipped)


def report(*, skipped: int = 0, fell_back: tuple[str, ...] = ()) -> SetReport:
    found = one_order((FOUND,), skipped=skipped)
    return SetReport(reranked=found, fused=found, fell_back=fell_back)


def test_the_verdict_stops_only_a_complete_check_below_its_floor() -> None:
    held = (FloorCheck("handWritten.reranked.recallAt5", 0.82, 0.9),)
    low = (FloorCheck("handWritten.reranked.recallAt5", 0.82, 0.7),)
    assert ReleaseCheck({"handWritten": report()}, held).verdict is ReleaseVerdict.PASSED
    assert ReleaseCheck({"handWritten": report()}, low).exit_code == EXIT_BELOW_FLOOR
    assert ReleaseCheck({"handWritten": report(skipped=3)}, low).exit_code == EXIT_WARNED
    assert ReleaseCheck({"handWritten": report()}, held, warnings=("no generated",)).exit_code == EXIT_WARNED
    assert ReleaseCheck(error="ExternalFailure: the embedding route is down").exit_code == EXIT_WARNED
    assert ReleaseCheck({"handWritten": report()}, held).exit_code == EXIT_PASSED
    shown = ReleaseCheck({"handWritten": report(skipped=3)}, low).as_dict()
    assert shown["ok"] and not shown["complete"]
    assert shown["sets"]["handWritten"]["reranked"]["skipped"] == 3
    assert shown["sets"]["handWritten"]["fused"]["skipped"] == 3
    assert shown["warnings"][-1].startswith("the time budget ran out")


def test_a_rerank_that_failed_warns_and_never_passes() -> None:
    held = (FloorCheck("handWritten.fused.recallAt5", 0.5, 1.0),)
    low = (FloorCheck("handWritten.fused.recallAt5", 0.5, 0.0),)
    fell_back = ReleaseCheck({"handWritten": report(fell_back=("q",))}, held)
    assert (fell_back.verdict, fell_back.exit_code) == (ReleaseVerdict.WARNED, EXIT_WARNED)
    shown = fell_back.as_dict()
    assert shown["warnings"] == [
        "the rerank failed for 1 of 1 questions of handWritten, which kept the fused order, "
        "so the reranked floors of handWritten were not compared"
    ]
    assert shown["sets"]["handWritten"]["reranked"]["fellBackToFused"] == ["q"]
    assert shown["sets"]["handWritten"]["fused"].get("fellBackToFused") is None
    below = ReleaseCheck({"handWritten": report(fell_back=("q",))}, low)
    assert below.exit_code == EXIT_BELOW_FLOOR
    assert rerank_warnings({"handWritten": report()}) == ()


def test_each_order_meets_its_floors_and_the_reranked_only_when_every_question_was_reranked() -> None:
    both = SetReport(reranked=one_order((NOISE, FOUND)), fused=one_order((NOISE,), (FOUND,)))
    checks = set_checks({"handWritten": both}, FLOORS)
    assert [(check.measure, check.value, check.held) for check in checks] == [
        ("handWritten.reranked.recallAt5", 1.0, True),
        ("handWritten.reranked.meanReciprocalRank", 1.0, True),
        ("handWritten.fused.recallAt5", 1.0, True),
    ]
    fell_back = replace(both, fell_back=("q",))
    assert [check.measure for check in set_checks({"handWritten": fell_back}, FLOORS)] == [
        "handWritten.fused.recallAt5"
    ]
    unfolded = SetReport(reranked=one_order((NOISE,), (FOUND,)), fused=one_order((NOISE,), (FOUND,)))
    (recall, rank, _) = set_checks({"handWritten": unfolded}, FLOORS)
    assert (recall.value, recall.held, rank.value, rank.held) == (1.0, True, 0.5, False)


def shell_function(name: str) -> str:
    source = SWITCH.read_text(encoding="utf-8")
    found = re.search(rf"^{name}\(\) \{{\n(.*?)^\}}$", source, re.MULTILINE | re.DOTALL)
    assert found is not None, name
    return found.group(1)


def test_a_release_checks_retrieval_after_seeding_and_before_traffic_moves() -> None:
    release = shell_function("cmd_release")
    seed, check, promote = (
        release.find(call) for call in ('seed "$tree"', 'check_retrieval "$tree"', "start_and_promote")
    )
    assert 0 <= seed < check < promote
    assert 'check_retrieval "$tree" || die "retrieval fell below its floor.' in release


def test_the_release_check_stops_only_on_the_below_floor_exit_and_is_bounded_in_time() -> None:
    check = shell_function("check_retrieval")
    assert "app.scripts.eval_retrieval --release --seconds $CHECK_SECONDS" in check
    assert 'timeout "$((CHECK_SECONDS + EMBED_GRACE))"' in check
    stops = re.findall(r"^\s+(\S+)\) say \"::error::.*return 1 ;;$", check, re.MULTILINE)
    assert stops == [str(EXIT_BELOW_FLOOR)]
    assert re.search(rf"^\s+{EXIT_PASSED}\) say \"retrieval check passed", check, re.MULTILINE)
    assert re.search(rf"^\s+{EXIT_WARNED}\) say \"::warning::", check, re.MULTILINE)
    budget = re.search(r'^CHECK_SECONDS="\$\{CHECK_SECONDS:-(\d+)\}"$', SWITCH.read_text("utf-8"), re.M)
    assert budget is not None and int(budget.group(1)) == RELEASE_SECONDS == 180
