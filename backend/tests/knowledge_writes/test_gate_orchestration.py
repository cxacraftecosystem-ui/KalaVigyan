from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.models import Source
from app.models.crafts import EMBEDDING_DIMENSIONS
from app.research.candidate_gates import Candidate, CitedSource
from app.research.fetcher import FetchRefused
from app.research.knowledge_writes import FactProposal
from app.retrieval.text import document_text
from app.services.candidate_gates import first_gates, gate_run, later_gates
from app.services.candidate_sources import read_sources

from .fakes import (
    JUDGE_MODEL,
    PAGE_TEXT,
    PAGE_URL,
    QUOTE,
    STATEMENT,
    FakeEmbedder,
    FakeFetcher,
    FakeHeldFacts,
    FakeJudge,
    held,
    page,
)
from .judge_replies import added_reason, compared, verdict

DECLARED_TITLE = "Indigo dyeing in Ajrakh"
VECTOR = [1.0] + [0.0] * (EMBEDDING_DIMENSIONS - 1)
FIRST = Candidate(ref="c1", statement=STATEMENT, field="PROCESS")
SECOND = Candidate(ref="c2", statement="Ajrakh printers wash the cloth in running water.", field="PROCESS")
NEAR = held("near", "Ajrakh cloth goes into the vat four times.", 0.95)


class StoredSession:
    def __init__(self, source: Source | None = None) -> None:
        self.source = source

    async def scalar(self, statement: Any) -> Source | None:
        return self.source


def proposal(licence: str | None = None) -> FactProposal:
    source = {"url": PAGE_URL, "title": DECLARED_TITLE, "licence": licence, "quotes": [{"text": QUOTE}]}
    body = {"subject": {"kind": "craft", "slug": "Kutch-Ajrakh"}, "field": "PROCESS", "statement": STATEMENT}
    return FactProposal.model_validate(body | {"sources": [source]})


def comparison(candidate: str, relation: str) -> dict[str, Any]:
    return compared(candidate, NEAR.id, relation)


def test_the_first_gates_stop_at_a_failed_quote_check() -> None:
    bad = CitedSource(
        url=PAGE_URL, quotes=["The cloth is dipped in the vat nine times"], text=PAGE_TEXT, grade="B"
    )
    assert [outcome.gate for outcome in first_gates(FIRST, [bad])] == ["QUOTES"]
    good = CitedSource(url=PAGE_URL, quotes=[QUOTE], text=PAGE_TEXT, grade="B")
    assert [outcome.gate for outcome in first_gates(FIRST, [good])] == ["QUOTES", "SOURCE"]


async def test_a_held_twin_is_refused_without_a_judge_call() -> None:
    judge = FakeJudge()
    store = FakeHeldFacts(twins=[held("twin", STATEMENT + ".", 1.0)])
    later = await later_gates(store, [FIRST], embed=FakeEmbedder(VECTOR), judge=judge)
    (duplicate,) = later["c1"].outcomes
    assert (duplicate.gate, duplicate.passed) == ("DUPLICATE", False)
    assert judge.calls == []


async def test_one_judge_call_compares_a_batch_and_a_differing_fact_skips_the_novelty_call() -> None:
    judge = FakeJudge({"comparisons": [comparison("c1", "SAME"), comparison("c2", "DIFFERS")]})
    embed = FakeEmbedder(VECTOR)
    later = await later_gates(FakeHeldFacts(nearest=[NEAR]), [FIRST, SECOND], embed=embed, judge=judge)
    assert embed.calls == [[document_text(FIRST.statement), document_text(SECOND.statement)]]
    assert len(judge.calls) == 1
    (refused,) = later["c1"].outcomes
    assert (refused.passed, refused.related, refused.model) == (False, [NEAR.id], JUDGE_MODEL)
    duplicate, novelty = later["c2"].outcomes
    assert (duplicate.passed, duplicate.related, novelty.passed, novelty.model) == (
        True,
        [NEAR.id],
        True,
        None,
    )
    assert later["c2"].vector == VECTOR


async def test_a_distinct_fact_goes_to_the_novelty_judge_with_its_nearest_facts() -> None:
    covering = verdict("c1", adds=False, covered=[NEAR.id], reason="Already said.")
    judge = FakeJudge({"comparisons": [comparison("c1", "DISTINCT")]}, {"verdicts": [covering]})
    later = await later_gates(FakeHeldFacts(nearest=[NEAR]), [FIRST], embed=FakeEmbedder(VECTOR), judge=judge)
    run = gate_run(FIRST, (), later["c1"])
    assert [(o.gate, o.passed) for o in run.outcomes] == [("DUPLICATE", True), ("NOVELTY", False)]
    assert (run.passed, run.refused_at.gate, run.held_instead, run.differs_from) == (
        False,
        "NOVELTY",
        [NEAR.id],
        [],
    )
    assert run.refused_at.reasons == ["Already said."]
    assert f'ref="{NEAR.id}"' in judge.calls[1]["user"]


async def test_without_an_embedder_only_identical_texts_are_refused_and_novelty_is_not_judged() -> None:
    store = FakeHeldFacts(nearest=[NEAR])
    later = await later_gates(store, [FIRST], embed=None, judge=FakeJudge())
    (duplicate,) = later["c1"].outcomes
    assert duplicate.passed and duplicate.reasons[0].startswith("only identical texts were looked for")
    assert [kind for kind, _ in store.asked] == ["twins"]
    assert later["c1"].vector is None


async def test_a_far_neighbour_skips_the_comparison_but_not_the_novelty_judgement() -> None:
    far = held("far", "Ajrakh carries geometric patterns.", 0.4)
    judge = FakeJudge({"verdicts": [verdict("c1", adds=True, reason="It counts the dips.")]})
    later = await later_gates(FakeHeldFacts(nearest=[far]), [FIRST], embed=FakeEmbedder(VECTOR), judge=judge)
    duplicate, novelty = later["c1"].outcomes
    assert (duplicate.passed, novelty.passed, novelty.reasons, len(judge.calls)) == (
        True,
        True,
        [added_reason("It counts the dips.")],
        1,
    )


async def test_a_read_page_is_graded_as_the_research_pipeline_grades_a_web_page() -> None:
    fetcher = FakeFetcher({PAGE_URL: page(licence=None, title=None)})
    (read,) = await read_sources(StoredSession(), fetcher, proposal(licence="CC BY 4.0"))  # type: ignore[arg-type]
    assert (read.cited.grade, read.cited.text, read.cited.declared_licence) == ("C", PAGE_TEXT, "CC BY 4.0")
    assert read.document is not None
    assert (read.document.item.title, read.document.item.licence) == (DECLARED_TITLE, "CC BY 4.0")


async def test_a_stored_source_keeps_its_own_grade_and_restriction() -> None:
    stored = Source(url=PAGE_URL, title="Stored", kind="PAPER", reliability="A", sensitivity="RESTRICTED")
    fetcher = FakeFetcher({PAGE_URL: page(licence="All rights reserved")})
    (read,) = await read_sources(StoredSession(stored), fetcher, proposal())  # type: ignore[arg-type]
    assert (read.cited.grade, read.cited.restricted, read.cited.stated_licence) == (
        "A",
        True,
        "All rights reserved",
    )


async def test_a_refused_or_failed_fetch_becomes_the_unread_reason_and_an_outage_is_raised() -> None:
    refused = FakeFetcher({PAGE_URL: FetchRefused(PAGE_URL, "ROBOTS_DISALLOWED")})
    (read,) = await read_sources(StoredSession(), refused, proposal())  # type: ignore[arg-type]
    assert (read.cited.text, read.cited.unread, read.document) == (
        None,
        "Fetch refused (ROBOTS_DISALLOWED)",
        None,
    )
    gone = FakeFetcher({PAGE_URL: ExternalFailure("the page answered 404", kind="not_found")})
    (missing,) = await read_sources(StoredSession(), gone, proposal())  # type: ignore[arg-type]
    assert missing.cited.unread == "the page answered 404"
    blank = FakeFetcher({PAGE_URL: page(text="   ")})
    (empty,) = await read_sources(StoredSession(), blank, proposal())  # type: ignore[arg-type]
    assert empty.cited.unread == "the page has no readable text"
    down = FakeFetcher({PAGE_URL: ExternalFailure("no answer", kind="unavailable", retryable=True)})
    with pytest.raises(ExternalFailure):
        await read_sources(StoredSession(), down, proposal())  # type: ignore[arg-type]
