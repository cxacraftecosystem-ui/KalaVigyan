import json
import uuid
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, Source
from app.research.structured import StructuredReply
from app.retrieval.deadline import Deadline
from app.retrieval.eval_floors import parse_floors
from app.retrieval.eval_runs import EvalTools, QuestionSets, release_run, weekly_run
from app.retrieval.golden import GeneratedQuestion, GeneratedSet, golden_questions
from app.retrieval.indexing import embed_pending
from app.retrieval.miss_judging import JudgeTools
from app.retrieval.question_facts import FactSampling, craft_facts, eval_crafts
from app.retrieval.release_check import ReleaseVerdict
from app.scripts.eval_retrieval import golden_claim_id
from app.services.claim_seed import load_seed_claims, seed_claims, seed_id
from app.services.claim_seed_passages import store_seed_passages

from .field_voices_rows import rolled_back
from .test_retrieval_eval import word_embedder

pytestmark = pytest.mark.db

SLUG = "Measurement-Test-Craft"
FLOORS = parse_floors(
    {
        "version": 1,
        "retrieval": {
            "handWritten": {"recallAt5": 0.9, "meanReciprocalRank": 0.7},
            "generated": {"recallAt5": 0.5},
        },
        "answers": {},
    }
)


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-measurement/{name}")


async def add_fact(session: AsyncSession, name: str, text: str, status: str = "APPROVED") -> uuid.UUID:
    session.add(
        Claim(
            id=key(name),
            subjectType="CONCEPT",
            subjectId=key("concept"),
            predicate="states",
            text=text,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            status=status,
        )
    )
    await session.flush()
    session.add(ClaimSource(claimId=key(name), sourceId=key("source"), quoteCheck="NA"))
    await session.flush()
    return key(name)


async def test_a_craft_s_published_facts_carry_their_text_twins_as_restatements() -> None:
    async with rolled_back() as session:
        session.add(
            Craft(id=key("craft"), slug=SLUG, name="Measurement Test Craft", stateOfOrigin=["Gujarat"])
        )
        session.add(Source(id=key("source"), kind="BOOK", title="A book on mordants"))
        await session.flush()
        session.add(Concept(id=key("concept"), craftId=key("craft"), type="MATERIAL", name="Alum"))
        await session.flush()
        first = await add_fact(session, "first", "Alum fixes the red dye on cotton.")
        twin = await add_fact(session, "twin", "alum fixes the red dye on cotton")
        other = await add_fact(session, "other", "Iron darkens the tannin on the cloth.")
        await add_fact(session, "rejected", "Alum fixes the red dye on cotton.", status="REJECTED")
        (craft,) = [found for found in await eval_crafts(session) if found.slug == SLUG]
        sampling = FactSampling(seed=1, per_craft=20, state_languages={"Gujarat": ("gu",)})
        facts = await craft_facts(session, craft, sampling)
    assert craft.names == ("Measurement Test Craft",) and facts.second_language == "gu"
    assert {fact.id for fact in facts.facts} == {first, twin, other}
    restated = {fact.id: (fact.restatements, fact.field) for fact in facts.sampled}
    assert restated == {
        first: ((twin,), "MATERIALS"),
        twin: ((first,), "MATERIALS"),
        other: ((), "MATERIALS"),
    }


@asynccontextmanager
async def embedded_sessions() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            sessions = async_sessionmaker(bind=connection, expire_on_commit=False, autoflush=False)
            async with sessions() as session:
                data = load_seed_claims()
                await seed_claims(session, data)
                await store_seed_passages(session, data)
                await embed_pending(session, word_embedder, batch_size=500)
            yield sessions
        finally:
            await transaction.rollback()


def verbatim(seed_key: str, text: str, asked: str | None = None) -> GeneratedQuestion:
    fact = seed_id("claim", seed_key)
    return GeneratedQuestion(
        key=f"{fact}-en",
        craft_slug="Kutch-Ajrakh",
        question=asked or text,
        expected=((str(fact),),),
        fact=fact,
        language="en",
    )


def ajrakh_claims(count: int) -> list[Mapping[str, Any]]:
    rows = [row for row in load_seed_claims()["claims"] if row["craftSlug"] == "Kutch-Ajrakh"]
    distinct = {row["text"].casefold(): row for row in rows}
    return list(distinct.values())[:count]


def generated_of(*questions: GeneratedQuestion) -> GeneratedSet:
    return GeneratedSet.model_validate(
        {
            "version": 1,
            "revision": 1,
            "generatedAt": "2026-11-22T00:00:00Z",
            "seed": 1,
            "factsPerCraft": 20,
            "questions": questions,
        }
    )


async def test_the_release_check_passes_on_the_seeded_index_and_warns_without_generated_questions() -> None:
    async with embedded_sessions() as sessions:
        tools = EvalTools(sessions=sessions, embed=word_embedder, claim_id=golden_claim_id, concurrency=1)
        sets = QuestionSets(
            golden_questions(), generated_of(*(verbatim(r["id"], r["text"]) for r in ajrakh_claims(3)))
        )
        check = await release_run(tools, sets, floors=FLOORS, deadline=Deadline.after(3600))
        alone = await release_run(
            tools, QuestionSets(golden_questions(), None), floors=FLOORS, deadline=Deadline.after(3600)
        )
    assert check.verdict is ReleaseVerdict.PASSED, check.as_dict()
    assert check.reports["generated"].overall().questions == 2
    assert [one.measure for one in check.checks] == [
        "handWritten.recallAt5",
        "handWritten.meanReciprocalRank",
        "generated.recallAt5",
    ]
    assert alone.verdict is ReleaseVerdict.WARNED and alone.exit_code == 2, alone.as_dict()
    assert all(one.held for one in alone.checks)


class AgreeingJudge:
    def __init__(self) -> None:
        self.asked: list[str] = []

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.asked.append(user)
        decisions = [{"ref": str(ref), "answers": True} for ref in range(1, user.count("Question: ") + 1)]
        return StructuredReply(text=json.dumps({"decisions": decisions}), degraded=False, model="cheap")


async def test_a_question_answered_first_by_another_fact_is_judged_once_and_joins_the_next_revision() -> None:
    first, second = ajrakh_claims(2)
    misled = verbatim(first["id"], first["text"], asked=second["text"])
    judge = AgreeingJudge()

    async def nothing_spent() -> Decimal:
        return Decimal(0)

    async with embedded_sessions() as sessions:
        tools = EvalTools(sessions=sessions, embed=word_embedder, claim_id=golden_claim_id, concurrency=1)
        run = await weekly_run(
            tools,
            QuestionSets(golden_questions(), generated_of(misled)),
            judge=JudgeTools(judge=judge, spent=nothing_spent, tag="eval-misses-dbtest01"),
            floors=FLOORS,
        )
    (decision,) = run.decisions
    (scored,) = run.reports["generated"].results
    assert (decision.key, decision.claim, decision.answers) == (misled.key, scored.first, True)
    assert decision.claim != misled.fact
    assert len(judge.asked) == 1 and run.revised is not None and run.revised.revision == 2
    assert run.revised.questions[0].facts == ((str(misled.fact), str(decision.claim)),)
    assert run.reports["generated"].recall_at_depth == 1.0 and not run.below_floor
