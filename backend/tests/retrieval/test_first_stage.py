import asyncio
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.errors import ExternalFailure
from app.models.crafts import EMBEDDING_DIMENSIONS
from app.retrieval.answer_embeddings import AnswerEmbeddings
from app.retrieval.glossary_words import named_by, slot_query, text_query
from app.retrieval.text import (
    GLOSSARY_WORD_MIN_CHARS,
    TSQUERY_SHORT_TERMS,
    context_title,
    document_text,
    is_short_term,
    or_tsquery,
    short_terms,
)

STAMP = "gemini-embedding-2#ctx1"
WORKFLOW = Path(__file__).resolve().parents[3] / ".github" / "workflows" / "embed-knowledge.yml"


def compiled(statement: Any) -> tuple[str, dict[str, Any]]:
    result = statement.compile(dialect=postgresql.dialect())
    return " ".join(result.string.split()), dict(result.params)


def test_a_claim_is_titled_with_its_craft_its_concept_and_its_field() -> None:
    title = context_title("Kutch Ajrakh", "Washing", "PROCESS")
    assert title == "Kutch Ajrakh · Washing · Process"
    assert document_text("It is then washed in the river.", title=title) == (
        "title: Kutch Ajrakh · Washing · Process | text: It is then washed in the river."
    )


def test_a_family_concept_named_as_its_category_is_named_once() -> None:
    assert context_title("Textiles", "Textiles", "CHEMISTRY") == "Textiles · Chemistry"
    assert context_title(None, " Alum  mordant ", None) == "Alum mordant"
    assert context_title(None, None, None) is None


def test_short_words_follow_the_long_ones_and_need_a_long_one_to_search_at_all() -> None:
    assert or_tsquery("What is a GI tag?") == "what | tag | is | gi"
    assert short_terms("What is a GI tag?") == ["is", "gi"]
    assert or_tsquery("GI?") is None
    assert (GLOSSARY_WORD_MIN_CHARS, TSQUERY_SHORT_TERMS) == (2, 8)
    assert is_short_term("gi") and not is_short_term("gum")
    many = " ".join(f"z{letter}" for letter in "abcdefghijk")
    assert short_terms(many) == [f"z{letter}" for letter in "abcdefgh"]


def test_a_short_word_reaches_the_search_only_through_the_glossary() -> None:
    named = named_by(["gi"]).subquery("glossary")
    sql, params = compiled(select(slot_query("gi", named)))
    assert "websearch_to_tsquery(" in sql and "concat_ws(" in sql and "NULL" in sql
    assert '"gi"' not in params.values() and "gi" in params.values()


def test_a_long_word_searches_itself_or_every_other_name_of_the_terms_it_names() -> None:
    named = named_by(["siyahi"]).subquery("glossary")
    sql, params = compiled(select(slot_query("siyahi", named)))
    assert '"siyahi"' in params.values() and " or " in params.values()
    assert "string_agg(concat(" in sql and "replace(glossary.name, " in sql
    assert ["siyahi"] in compiled(named_by(["siyahi"]))[1].values()


def test_the_words_query_ors_one_slot_per_word() -> None:
    sql, _ = compiled(select(text_query("alum | gi")))
    assert sql.count("websearch_to_tsquery(") == 2 and ") || websearch_to_tsquery(" in sql


class CountingEmbedder:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    async def __call__(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(list(texts))
        await asyncio.sleep(0)
        return [[float(len(text))] * EMBEDDING_DIMENSIONS for text in texts]


def stamps(*values: str) -> Any:
    told = list(values)

    async def read() -> str:
        return told.pop(0) if len(told) > 1 else told[0]

    return read


async def test_one_text_is_embedded_once_for_an_answer_however_many_seats_ask() -> None:
    inner = CountingEmbedder()
    embed = AnswerEmbeddings(inner, stamp=stamps(STAMP))
    asked = await asyncio.gather(*(embed(["question"]) for _ in range(4)))
    assert inner.calls == [["question"]]
    assert all(vectors == [[8.0] * EMBEDDING_DIMENSIONS] for vectors in asked)
    pair = await embed(["question", "craft", "question"])
    assert inner.calls == [["question"], ["craft"]]
    assert [vector[0] for vector in pair] == [8.0, 5.0, 8.0]


async def test_a_new_stamp_embeds_the_text_again() -> None:
    inner = CountingEmbedder()
    embed = AnswerEmbeddings(inner, stamp=stamps(STAMP, "other-model#ctx1"))
    await embed(["question"])
    await embed(["question"])
    assert inner.calls == [["question"], ["question"]]


async def test_a_failed_embedding_is_tried_again_by_the_next_call() -> None:
    failing = [True]

    async def flaky(texts: list[str]) -> list[list[float]]:
        if failing.pop() if failing else False:
            raise ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")
        return [[1.0] * EMBEDDING_DIMENSIONS for _ in texts]

    embed = AnswerEmbeddings(flaky, stamp=stamps(STAMP))
    with pytest.raises(ExternalFailure):
        await embed(["question"])
    assert await embed(["question"]) == [[1.0] * EMBEDDING_DIMENSIONS]


def test_the_re_embedding_runs_only_by_hand_until_every_vector_carries_the_current_stamp() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert "workflow_dispatch:" in workflow and "schedule:" not in workflow
    assert r"exec ./.venv/bin/python -m app.scripts.\$1 --seconds \$2" in workflow
    assert "run embed_craft_descriptors 300" in workflow and r"run embed_knowledge \$left" in workflow
    assert """*'"complete": true'*) echo "every vector is current"; break ;;""" in workflow
    assert '[ "$SECONDS_BUDGET" -ge 60 ] && [ "$SECONDS_BUDGET" -le 3300 ]' in workflow
