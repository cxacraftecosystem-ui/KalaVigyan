import re
from pathlib import Path

from app.retrieval.eval_floors import FLOORS_FILE

REPO = Path(__file__).resolve().parents[3]
WORKFLOWS = REPO / ".github" / "workflows"
FLOORS_PATH = FLOORS_FILE.relative_to(REPO).as_posix()


def workflow(name: str) -> str:
    return (WORKFLOWS / name).read_text(encoding="utf-8")


def triggers(text: str) -> set[str]:
    block = re.search(r"^on:\n(.*?)^\S", text, re.MULTILINE | re.DOTALL)
    assert block is not None
    return set(re.findall(r"^  ([a-z_]+):", block.group(1), re.MULTILINE))


def test_the_weekly_retrieval_run_keeps_one_issue_while_a_floor_is_broken() -> None:
    text = workflow("retrieval-eval.yml")
    assert triggers(text) == {"workflow_dispatch", "schedule"}
    assert "python -m app.scripts.eval_retrieval $EVAL_ARGS --out" in text
    assert "uses: ./.github/actions/release-issue" in text
    assert "title: Retrieval fell below its floor" in text
    assert "jq -e '.belowFloor == true'" in text and FLOORS_PATH in text
    assert re.search(
        r"^  alert:\n(?:.*\n)*?    permissions:\n      contents: read\n      issues: write$", text, re.M
    )


def test_a_weekly_run_whose_rerank_failed_warns_and_leaves_the_issue_as_it_is() -> None:
    text = workflow("retrieval-eval.yml")
    warned = text.index("elif jq -e '(.warnings // []) | length > 0'")
    assert text.index("if jq -e '.belowFloor == true'") < warned < text.index("else outcome=passing")
    assert "then outcome=warned" in text[warned:]
    assert re.search(r"^\s+warned\) headline=", text, re.M)
    assert ".value.fellBackToFused" in text and ".sets.handWritten.reranked.misses" in text


def test_the_answer_run_keeps_its_own_issue_and_compares_only_a_whole_run() -> None:
    text = workflow("answer-quality.yml")
    assert triggers(text) == {"workflow_dispatch"}
    assert "title: Answers fell below their floor" in text
    assert "jq -e '.floorsApplied == true'" in text and "jq -e '.belowFloor == true'" in text
    assert FLOORS_PATH in text


def test_the_question_generator_runs_only_by_hand_and_keeps_the_set_for_the_lead() -> None:
    text = workflow("eval-questions.yml")
    assert triggers(text) == {"workflow_dispatch"}
    assert "python -m app.scripts.generate_eval_questions $GENERATE_ARGS --out" in text
    assert "name: eval-questions-${{ github.run_id }}" in text
    assert "backend/app/data/eval/generated/retrieval_questions.json" in text
