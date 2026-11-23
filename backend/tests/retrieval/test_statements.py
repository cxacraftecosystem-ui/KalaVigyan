import re
import uuid
from typing import Any, cast

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.models.crafts import EMBEDDING_DIMENSIONS
from app.research.planning import MODE_POLICIES
from app.research.retrieval import (
    HIDDEN_CLAIM_STATUSES,
    MODE_CLAIM_LEVELS,
    MODE_CLAIM_STATUSES,
    KnowledgeQuery,
    KnowledgeRetriever,
)
from app.retrieval.citation_access import HELD_KEPT
from app.retrieval.hybrid import CORPUS_TIER, StoredKnowledgeSearch
from app.retrieval.nearest import INDEX_SCAN_OPTION, reads_every_craft
from app.retrieval.statements import (
    ENTITY_NAME_MIN_CHARS,
    EVERY_CRAFT,
    LEXICAL_CANDIDATES,
    NAME_GLOSS,
    NAME_GLOSS_OPEN,
    RANKING_DEPTH,
    REGEX_ESCAPED,
    REGEX_SPECIALS,
    WORD_AFTER,
    WORD_BEFORE,
    CraftScope,
    chunk_conditions,
    chunk_lexical_ranking,
    chunk_vector_ranking,
    cited_from_kinds,
    claim_conditions,
    claim_entity_ranking,
    claim_lexical_ranking,
    claim_vector_ranking,
)

from ..craft_fixtures import FixedEmbedder

CRAFT = uuid.uuid5(uuid.NAMESPACE_URL, "test-craft/Qorvane-Ikat")
FAMILY = uuid.uuid5(uuid.NAMESPACE_URL, "test-sub/qorvane")
SCOPE = CraftScope(craft_id=CRAFT, sub_category_id=FAMILY)
CATEGORY = uuid.uuid5(uuid.NAMESPACE_URL, "test-category/qorvane")
MERGED = uuid.uuid5(uuid.NAMESPACE_URL, "test-craft/Qorvane-Old-Ikat")
LINKED = uuid.uuid5(uuid.NAMESPACE_URL, "test-concept/qorvane-shared-alum")
VECTOR = [0.0] * EMBEDDING_DIMENSIONS


def compiled(statement: Select[Any]) -> tuple[str, dict[str, Any]]:
    result = statement.compile(dialect=postgresql.dialect())
    return " ".join(result.string.split()), dict(result.params)


def params_with(params: dict[str, Any], prefix: str) -> list[Any]:
    return [value for name, value in sorted(params.items()) if name.startswith(prefix)]


def test_verified_mode_reads_approved_reviewed_and_verified_claims_only() -> None:
    sql, params = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="VERIFIED"), "alum"))
    assert params_with(params, "status_") == [["APPROVED"]]
    assert params_with(params, "evidenceLevel_") == [["VERIFIED", "REVIEWED"]]
    assert '"Claim".status IN' in sql and '"Claim"."evidenceLevel" IN' in sql


def test_hybrid_mode_reads_every_level_and_every_status_but_the_hidden_ones() -> None:
    _, params = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum"))
    assert params_with(params, "status_") == [["PROPOSED", "IN_REVIEW", "APPROVED"]]
    assert params_with(params, "evidenceLevel_") == [["VERIFIED", "REVIEWED", "PROVISIONAL", "HYPOTHESIS"]]
    assert HIDDEN_CLAIM_STATUSES == ("DRAFT", "REJECTED", "RETRACTED", "SUPERSEDED", "WITHDRAWN")


def test_every_mode_has_claim_filters_and_only_the_corpus_modes_read_chunks() -> None:
    assert set(MODE_CLAIM_LEVELS) == set(MODE_CLAIM_STATUSES) == set(MODE_POLICIES)
    assert [mode for mode, policy in MODE_POLICIES.items() if CORPUS_TIER in policy.tiers] == [
        "HYBRID",
        "DEEP",
    ]


def test_claims_are_scoped_to_the_craft_and_its_family_and_need_a_visible_source() -> None:
    sql, params = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum"))
    assert '"Concept"."craftId" = %(craftId_1)s::UUID OR "Concept"."craftId" IS NULL' in sql
    assert '"Concept"."subCategoryId" = %(subCategoryId_1)s::UUID' in sql
    assert params["craftId_1"] == CRAFT and params["subCategoryId_1"] == FAMILY
    assert '"Claim"."subjectType" = %(subjectType_1)s::VARCHAR' in sql
    assert params["subjectType_1"] == "CONCEPT" and params["subjectType_2"] == "EDGE"
    assert '"ConceptEdge"."srcId" IN' in sql and '"ConceptEdge"."dstId" IN' in sql
    assert 'reader_cite."claimId" = "Claim".id' in sql
    assert "reader_source.sensitivity != %(sensitivity_5)s" in sql
    assert params_with(params, "sensitivity_") == ["OPEN", "OPEN", "OPEN", "OPEN", "RESTRICTED"]


def test_a_craft_without_a_family_reads_only_its_own_concepts() -> None:
    sql, _ = compiled(claim_lexical_ranking(claim_conditions(CraftScope(CRAFT, None), mode="HYBRID"), "alum"))
    assert "subCategoryId" not in sql


def test_facets_filter_the_concept_types() -> None:
    conditions = claim_conditions(SCOPE, mode="HYBRID", facets=("MATERIAL", "MECHANISM"))
    sql, params = compiled(claim_lexical_ranking(conditions, "alum"))
    assert '"Concept".type IN' in sql
    assert params_with(params, "type_") == [["MATERIAL", "MECHANISM"]]


def test_fields_keep_the_fields_claims_their_secondary_fields_and_the_unfielded() -> None:
    sql, params = compiled(
        claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID", fields=("CHEMISTRY",)), "alum")
    )
    assert '("Claim".field IS NULL OR "Claim".field IN (__[POSTCOMPILE_field_1]) OR "Claim".fields && ' in sql
    assert params["field_1"] == ["CHEMISTRY"] and params["fields_1"] == ["CHEMISTRY"]
    unfiltered, _ = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum"))
    assert '"Claim".field' not in unfiltered


def test_chunks_follow_the_claims_of_the_asked_fields() -> None:
    conditions = chunk_conditions(
        SCOPE, mode="HYBRID", fields=("HISTORY",), acls=("PUBLIC",), kinds=("PASSAGE",)
    )
    sql, params = compiled(chunk_lexical_ranking(conditions, "alum"))
    assert '"Claim".fields && ' in sql and params["fields_1"] == ["HISTORY"]


def test_the_entity_ranking_reads_concepts_named_by_name_head_gloss_or_glossary_term_longest_first() -> None:
    statement = claim_entity_ranking(claim_conditions(SCOPE, mode="HYBRID"), SCOPE, "Why is syahi used?")
    sql, params = compiled(statement)
    assert sql.startswith(
        "WITH named AS (SELECT names.id AS id, max(length(lower(trim(names.name)))) AS weight"
    )
    assert 'split_part("Concept".name, ' in sql and 'SUBSTRING("Concept".name FROM ' in sql
    assert "termed.label" in sql and "unnest(termed.aliases)" in sql and 'unnest(termed."localNames")' in sql
    assert re.search(
        r"strpos\(lower\(%\(param_\d+\)s::VARCHAR\), lower\(trim\(names\.name\)\)\) > %\(strpos_1\)s::INTEGER",
        sql,
    )
    assert '"ConceptEdge"."srcId" = named.id OR "ConceptEdge"."dstId" = named.id' in sql
    assert re.search(
        r'GROUP BY "Claim"\.id ORDER BY max\(subjects\.weight\) DESC, "Claim"\.id LIMIT %\(param_\d+\)s::INTEGER$',
        sql,
    )
    values = list(params.values())
    assert NAME_GLOSS_OPEN == " (" and NAME_GLOSS == r"\(([^)]*)\)"
    assert NAME_GLOSS_OPEN in values and NAME_GLOSS in values and ENTITY_NAME_MIN_CHARS in values
    assert "Why is syahi used?" in values and RANKING_DEPTH in values and ENTITY_NAME_MIN_CHARS == 4


def test_the_lexical_ranking_weighs_each_matched_term_by_its_rarity_among_the_candidates() -> None:
    sql, params = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum | madder"))
    assert sql.startswith("WITH glossary AS (SELECT lower(btrim(asked_names.name)) AS word, ")
    assert ", asked AS (SELECT websearch_to_tsquery(" in sql
    assert 'lexical AS MATERIALIZED (SELECT "Claim".id AS id, ts_rank_cd("Claim".tsv, (SELECT ' in sql
    assert "asked.slot_0 || asked.slot_1" in sql
    assert '"Claim".tsv @@ (SELECT asked.slot_0 FROM asked) AS term_0' in sql
    assert "AS term_0" in sql and "AS term_1" in sql and "term_2" not in sql
    assert sql.count("ln(") == 2 and sql.count("greatest(") == 2
    assert re.search(r"DESC, lexical\.density DESC, lexical\.id LIMIT %\(param_\d+\)s::INTEGER$", sql)
    words = [value for value in params.values() if isinstance(value, str)]
    assert {"english", '"alum"', '"madder"', " or "} <= set(words)
    assert ["alum", "madder"] in params.values()
    assert LEXICAL_CANDIDATES in params.values() and RANKING_DEPTH in params.values()
    assert (LEXICAL_CANDIDATES, RANKING_DEPTH) == (400, 60)


def test_the_vector_ranking_is_an_exact_cosine_scan_of_the_scoped_rows() -> None:
    sql, params = compiled(claim_vector_ranking(claim_conditions(SCOPE, mode="HYBRID"), VECTOR, depth=7))
    assert sql.startswith('WITH scoped AS MATERIALIZED (SELECT "Claim".id AS id, "Claim".embedding <=> ')
    assert '"Claim".embedding IS NOT NULL' in sql
    assert sql.endswith(
        "SELECT scoped.id FROM scoped ORDER BY scoped.distance, scoped.id LIMIT %(param_1)s::INTEGER"
    )
    assert params["param_1"] == 7


def test_a_search_of_no_single_craft_orders_by_the_vector_index_then_filters_by_the_claim_conditions() -> (
    None
):
    statement = claim_vector_ranking(claim_conditions(EVERY_CRAFT, mode="HYBRID"), VECTOR, depth=7)
    sql, params = compiled(statement)
    assert sql.startswith('WITH nearest AS MATERIALIZED (SELECT "Claim".id AS id, "Claim".embedding <=> ')
    assert 'SELECT nearest.id FROM nearest JOIN "Claim" ON "Claim".id = nearest.id WHERE ' in sql
    assert sql.endswith("ORDER BY nearest.distance, nearest.id LIMIT %(param_2)s::INTEGER")
    assert (params["param_1"], params["param_2"]) == (56, 7)
    assert statement.get_execution_options()[INDEX_SCAN_OPTION] is True
    chunks = chunk_vector_ranking(
        chunk_conditions(EVERY_CRAFT, mode="HYBRID", acls=("PUBLIC",), kinds=("PASSAGE",)), VECTOR
    )
    assert compiled(chunks)[0].startswith('WITH nearest AS MATERIALIZED (SELECT "Chunk".id AS id, ')


def test_only_a_search_of_no_single_craft_takes_the_index_even_when_more_conditions_follow() -> None:
    kinds = cited_from_kinds(("BOOK",))
    assert reads_every_craft([*claim_conditions(EVERY_CRAFT, mode="HYBRID"), kinds])
    assert not reads_every_craft([*claim_conditions(SCOPE, mode="HYBRID"), kinds])
    assert not reads_every_craft(chunk_conditions(SCOPE, mode="HYBRID", acls=("PUBLIC",), kinds=("PASSAGE",)))
    exact = compiled(claim_vector_ranking(claim_conditions(SCOPE, mode="HYBRID"), VECTOR))[0]
    assert exact.startswith("WITH scoped AS MATERIALIZED") and "nearest" not in exact


def test_chunks_come_from_sources_cited_by_scoped_claims_or_shown_field_interviews_within_the_reader_acl() -> (
    None
):
    conditions = chunk_conditions(SCOPE, mode="HYBRID", acls=("PUBLIC",), kinds=("PASSAGE",))
    sql, params = compiled(chunk_lexical_ranking(conditions, "alum"))
    assert sql.startswith("WITH glossary AS ")
    assert 'lexical AS MATERIALIZED (SELECT "Chunk".id AS id, ts_rank_cd("Chunk".tsv, ' in sql
    assert 'WHERE ("Chunk"."sourceId" IN (SELECT "Source".id' in sql
    assert '"ClaimSource"."claimId" IN (SELECT "Claim".id FROM "Claim"' in sql
    assert ' OR "Chunk"."sourceId" IN (SELECT "FieldRecording"."sourceId" FROM "FieldRecording"' in sql
    assert '"FieldRecording"."hiddenAt" IS NULL' in sql
    assert '"FieldRecordingCraft"."craftId" = ' in sql
    assert '"Chunk".acl IN' in sql and params_with(params, "acl_") == [["PUBLIC"]]
    assert '"Chunk".kind IN' in sql and params_with(params, "kind_") == [["PASSAGE"]]
    assert '"Chunk".sensitivity != ' in sql
    assert params_with(params, "sensitivity_").count("RESTRICTED") == 3
    vector_sql, _ = compiled(chunk_vector_ranking(conditions, VECTOR))
    assert vector_sql.startswith(
        'WITH scoped AS MATERIALIZED (SELECT "Chunk".id AS id, "Chunk".embedding <=> '
    )


def test_held_facts_are_left_out_of_every_mode_unless_kept_for_contributors() -> None:
    for mode in MODE_CLAIM_STATUSES:
        sql, params = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode=mode), "alum"))
        assert '"ClaimSource"."quoteCheck" != ' in sql and params_with(params, "quoteCheck_") == ["FAIL"]
        assert '"ClaimSource".quote IS NOT NULL' in sql
    kept = claim_conditions(SCOPE, mode="HYBRID", held=HELD_KEPT)
    sql, _ = compiled(claim_lexical_ranking(kept, "alum"))
    assert "quoteCheck" not in sql


def test_the_query_contract_refuses_repeats_and_out_of_range_limits() -> None:
    with pytest.raises(ValueError):
        KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID", facets=("MATERIAL", "MATERIAL"))
    with pytest.raises(ValueError):
        KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID", limit=51)
    with pytest.raises(ValueError):
        KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID", chunk_acls=("EVERYONE",))
    query = KnowledgeQuery.model_validate({"craftSlug": "Kutch-Ajrakh", "text": " alum ", "mode": "VERIFIED"})
    assert query.text == "alum" and query.chunk_acls == ("PUBLIC", "SIGNED_IN") and query.limit == 12
    assert query.chunk_kinds == ("PASSAGE",)
    with pytest.raises(ValueError):
        KnowledgeQuery(
            craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID", chunk_kinds=("WINDOW", "WINDOW")
        )


def test_the_stored_search_implements_the_retriever_contract() -> None:
    search = StoredKnowledgeSearch(cast(AsyncSession, object()), embed=FixedEmbedder())
    assert isinstance(search, KnowledgeRetriever)


def test_any_craft_reads_every_visible_concept() -> None:
    sql, params = compiled(claim_lexical_ranking(claim_conditions(EVERY_CRAFT, mode="HYBRID"), "alum"))
    assert "craftId" not in sql and "subCategoryId" not in sql
    assert '"Concept".sensitivity = %(sensitivity_1)s' in sql
    assert params_with(params, "sensitivity_") == ["OPEN", "OPEN", "OPEN", "OPEN", "RESTRICTED"]


def test_a_craft_scope_reads_its_family_science_and_the_crafts_merged_into_it() -> None:
    scope = CraftScope(CRAFT, FAMILY, category_id=CATEGORY, merged_ids=(MERGED,))
    sql, params = compiled(claim_lexical_ranking(claim_conditions(scope, mode="HYBRID"), "alum"))
    merged = re.search(r'"Concept"\."craftId" IN \(__\[POSTCOMPILE_(craftId_\d+)\]\)', sql)
    assert merged is not None and params[merged.group(1)] == [MERGED]
    assert (
        'SELECT family_claim."subjectId" FROM "Claim" AS family_claim JOIN "CuratedCategoryClaim" '
        'ON "CuratedCategoryClaim"."claimId" = family_claim.id WHERE "CuratedCategoryClaim"."categoryId" = '
    ) in sql
    assert 'family_claim."subjectType" = ' in sql
    assert (
        '"Concept"."subCategoryId" IS NULL AND lower("Concept".name) = (SELECT lower("CraftCategory".name)'
        in sql
    )
    assert [value for value in params.values() if value == CATEGORY] == [CATEGORY, CATEGORY]
    plain, _ = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum"))
    assert (
        "CuratedCategoryClaim" not in plain
        and "CraftCategory" not in plain
        and " IN (__[POSTCOMPILE_craftId" not in plain
    )


def test_a_craft_scope_reads_the_shared_concepts_linked_to_it_and_no_other() -> None:
    scope = CraftScope(CRAFT, FAMILY, linked_ids=(LINKED,))
    sql, params = compiled(claim_lexical_ranking(claim_conditions(scope, mode="HYBRID"), "alum"))
    linked = re.search(r'OR "Concept"\.id IN \(__\[POSTCOMPILE_(id_\d+)\]\)', sql)
    assert linked is not None and params[linked.group(1)] == [LINKED]
    plain, _ = compiled(claim_lexical_ranking(claim_conditions(SCOPE, mode="HYBRID"), "alum"))
    assert re.search(r'"Concept"\.id IN \(__\[POSTCOMPILE_id_', plain) is None


def test_a_search_kept_to_source_kinds_reads_claims_citing_a_visible_source_of_those_kinds() -> None:
    conditions = [*claim_conditions(SCOPE, mode="HYBRID"), cited_from_kinds(("GI_JOURNAL", "OTHER"))]
    sql, params = compiled(claim_lexical_ranking(conditions, "alum"))
    assert '"Source".kind IN (__[POSTCOMPILE_kind_1])' in sql and params["kind_1"] == ["GI_JOURNAL", "OTHER"]
    assert '"ClaimSource"."sourceId" = "Source".id AND "Source".kind IN (__[POSTCOMPILE_kind_1])' in sql
    assert '"Source".sensitivity != ' in sql.split('"Source".kind IN', 1)[1]


def test_a_concept_is_named_only_by_whole_words_or_their_plural() -> None:
    statement = claim_entity_ranking(claim_conditions(SCOPE, mode="HYBRID"), SCOPE, "Which blocks need alum?")
    sql, params = compiled(statement)
    bound = r"%\(\w+\)s(?:::VARCHAR)?"
    assert re.search(
        rf"lower\({bound}\) ~ concat\({bound}, regexp_replace\(lower\(trim\(names\.name\)\), "
        rf"{bound}, {bound}, {bound}\), {bound}\)",
        sql,
    )
    assert (WORD_BEFORE, WORD_AFTER) == (r"(?<!\w)", r"(?:e?s)?(?!\w)")
    assert (REGEX_SPECIALS, REGEX_ESCAPED) == (r"([.^$*+?(){}|\\\[\]])", r"\\\1")
    values = list(params.values())
    assert all(value in values for value in (WORD_BEFORE, WORD_AFTER, REGEX_SPECIALS, REGEX_ESCAPED, "g"))


def test_the_query_contract_keeps_source_kinds_once_each_and_reads_passages_unless_told_not_to() -> None:
    with pytest.raises(ValueError):
        KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID", source_kinds=("OTHER", "OTHER"))
    query = KnowledgeQuery(craft_slug="Kutch-Ajrakh", text="alum", mode="HYBRID")
    assert (query.source_kinds, query.passages) == ((), True)
    kept = KnowledgeQuery.model_validate(
        {
            "craftSlug": None,
            "text": "alum",
            "mode": "DEEP",
            "sourceKinds": ["BOOK_CHAPTER"],
            "passages": False,
        }
    )
    assert (kept.source_kinds, kept.passages) == (("BOOK_CHAPTER",), False)
